#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from common import write_json


SUMMARY_FIELDS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_history",
    "personal_history",
    "allergy_history",
    "genetic_history",
]

FIELD_LABELS = {
    "chief_complaint": "Chief complaint",
    "history_of_present_illness": "History of present illness",
    "past_history": "Past history",
    "personal_history": "Personal history",
    "allergy_history": "Allergy history",
    "genetic_history": "Family history",
}

TABLE_LABELS = {
    "table1": "Chinese Summary",
    "table2": "English Summary",
    "table3": "Thai Summary",
    "table4": "English-to-Chinese Back-Translation",
    "table5": "Thai-to-Chinese Back-Translation",
}


@dataclass
class FileMetrics:
    path: Path
    table_id: str
    title: str
    sample_count: int
    changed_field_count: int
    total_field_slots: int
    modified_record_count: int
    modification_score: float
    modification_rate: float
    per_field_counts: Dict[str, int]
    sample_level_scores: List[float]
    score_standard_error: float
    score_ci_halfwidth: float
    records: List[Dict[str, Any]]


def load_json_records(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise SystemExit(f"{path} does not contain a JSON list.")
    return [row for row in data if isinstance(row, dict)]


def normalize_text(value: Any, collapse_whitespace: bool) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").strip()
    if collapse_whitespace:
        text = re.sub(r"\s+", " ", text)
    return text


def infer_table_id(path: Path, records: List[Dict[str, Any]]) -> str:
    if records:
        source_id = str(records[0].get("source_id") or "")
        match = re.search(r"(table\d+)", source_id.lower())
        if match:
            return match.group(1)
    match = re.search(r"(table\d+)", path.name.lower())
    if match:
        return match.group(1)
    return path.stem


def compute_score_uncertainty(sample_level_scores: List[float]) -> tuple[float, float]:
    if len(sample_level_scores) < 2:
        return 0.0, 0.0
    mean_value = sum(sample_level_scores) / len(sample_level_scores)
    variance = sum((value - mean_value) ** 2 for value in sample_level_scores) / (len(sample_level_scores) - 1)
    standard_error = math.sqrt(variance) / math.sqrt(len(sample_level_scores))
    ci_halfwidth = 1.96 * standard_error
    return standard_error, ci_halfwidth


def filter_reviewed_records(records: List[Dict[str, Any]], reviewed_only: bool) -> List[Dict[str, Any]]:
    if not reviewed_only:
        return records
    return [row for row in records if bool(row.get("reviewed"))]


def compute_file_metrics(
    path: Path,
    records: List[Dict[str, Any]],
    collapse_whitespace: bool,
) -> FileMetrics:
    table_id = infer_table_id(path, records)
    title = TABLE_LABELS.get(table_id, table_id)
    changed_field_count = 0
    modified_record_count = 0
    per_field_counts = {field: 0 for field in SUMMARY_FIELDS}
    sample_level_scores: List[float] = []
    record_summaries: List[Dict[str, Any]] = []

    for record in records:
        edited = record.get("edited_report") or {}
        original = record.get("original_current_report") or {}
        if not isinstance(edited, dict) or not isinstance(original, dict):
            raise SystemExit(
                f"{path} contains a row without dict 'edited_report' and 'original_current_report' fields."
            )

        changed_fields_for_record = 0
        for field in SUMMARY_FIELDS:
            edited_value = normalize_text(edited.get(field, ""), collapse_whitespace)
            original_value = normalize_text(original.get(field, ""), collapse_whitespace)
            if edited_value != original_value:
                changed_field_count += 1
                changed_fields_for_record += 1
                per_field_counts[field] += 1

        modified = changed_fields_for_record > 0
        if modified:
            modified_record_count += 1

        record_score = changed_fields_for_record / len(SUMMARY_FIELDS)
        sample_level_scores.append(record_score)
        record_summaries.append(
            {
                "uid": record.get("uid"),
                "row_index": record.get("row_index"),
                "patient_id": record.get("patient_id"),
                "changed_field_count": changed_fields_for_record,
                "record_score": round(record_score, 6),
                "modified": modified,
            }
        )

    sample_count = len(records)
    total_field_slots = sample_count * len(SUMMARY_FIELDS)
    modification_score = changed_field_count / total_field_slots if total_field_slots else 0.0
    modification_rate = modified_record_count / sample_count if sample_count else 0.0
    score_standard_error, score_ci_halfwidth = compute_score_uncertainty(sample_level_scores)

    return FileMetrics(
        path=path,
        table_id=table_id,
        title=title,
        sample_count=sample_count,
        changed_field_count=changed_field_count,
        total_field_slots=total_field_slots,
        modified_record_count=modified_record_count,
        modification_score=modification_score,
        modification_rate=modification_rate,
        per_field_counts=per_field_counts,
        sample_level_scores=sample_level_scores,
        score_standard_error=score_standard_error,
        score_ci_halfwidth=score_ci_halfwidth,
        records=record_summaries,
    )


def combine_metrics(metrics: List[FileMetrics]) -> Dict[str, Any]:
    per_field_counts = {field: 0 for field in SUMMARY_FIELDS}
    record_count = 0
    changed_field_count = 0
    total_field_slots = 0
    modified_record_count = 0
    sample_level_scores: List[float] = []

    for metric in metrics:
        record_count += metric.sample_count
        changed_field_count += metric.changed_field_count
        total_field_slots += metric.total_field_slots
        modified_record_count += metric.modified_record_count
        sample_level_scores.extend(metric.sample_level_scores)
        for field in SUMMARY_FIELDS:
            per_field_counts[field] += metric.per_field_counts[field]

    score_standard_error, score_ci_halfwidth = compute_score_uncertainty(sample_level_scores)
    modification_score = changed_field_count / total_field_slots if total_field_slots else 0.0
    modification_rate = modified_record_count / record_count if record_count else 0.0

    return {
        "record_count": record_count,
        "changed_field_count": changed_field_count,
        "total_field_slots": total_field_slots,
        "modification_score": round(modification_score, 6),
        "modification_score_percent": round(modification_score * 100, 2),
        "modified_record_count": modified_record_count,
        "modified_rate": round(modification_rate, 6),
        "modified_rate_percent": round(modification_rate * 100, 2),
        "per_field_counts": per_field_counts,
        "score_standard_error": round(score_standard_error, 6),
        "score_ci_halfwidth": round(score_ci_halfwidth, 6),
    }


def serialize_metric(metric: FileMetrics) -> Dict[str, Any]:
    return {
        "table_id": metric.table_id,
        "title": metric.title,
        "sample_count": metric.sample_count,
        "changed_field_count": metric.changed_field_count,
        "total_field_slots": metric.total_field_slots,
        "modification_score": round(metric.modification_score, 6),
        "modification_score_percent": round(metric.modification_score * 100, 2),
        "modified_record_count": metric.modified_record_count,
        "modified_rate": round(metric.modification_rate, 6),
        "modified_rate_percent": round(metric.modification_rate * 100, 2),
        "per_field_counts": metric.per_field_counts,
        "score_standard_error": round(metric.score_standard_error, 6),
        "score_ci_halfwidth": round(metric.score_ci_halfwidth, 6),
        "records": metric.records,
    }


def field_label(field_name: str) -> str:
    return FIELD_LABELS.get(field_name, field_name.replace("_", " ").title())


def build_markdown_report(metrics: List[FileMetrics], overall: Dict[str, Any]) -> str:
    lines = [
        "# Real-World Modification Score Report",
        "",
        "## Metric Definition",
        "- `modification_score = changed_field_count / total_editable_field_slots`",
        "- `modification_rate = changed_sample_count / total_samples`",
        f"- Editable field count per sample: `{len(SUMMARY_FIELDS)}`",
        "",
        "## Overall",
        f"- Records: `{overall['record_count']}`",
        f"- Changed field slots: `{overall['changed_field_count']} / {overall['total_field_slots']}`",
        f"- Modification score: `{overall['modification_score_percent']:.2f}%`",
        f"- Modified records: `{overall['modified_record_count']} / {overall['record_count']}`",
        f"- Modification rate: `{overall['modified_rate_percent']:.2f}%`",
        "",
        "## Per Table",
    ]

    for metric in metrics:
        lines.append(
            f"- `{metric.title}`: score `{metric.modification_score * 100:.2f}%`, rate `{metric.modification_rate * 100:.2f}%`, changed `{metric.changed_field_count} / {metric.total_field_slots}` field slots."
        )

    lines.extend(["", "## Field Edit Counts"])
    for field in SUMMARY_FIELDS:
        lines.append(f"- `{field_label(field)}`: `{overall['per_field_counts'][field]}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute real-world modification score and modification rate from doctor-edited JSON files."
    )
    parser.add_argument("--inputs", nargs="+", required=True, help="One or more doctor-review JSON files.")
    parser.add_argument("--output", required=True, help="Summary JSON output path.")
    parser.add_argument("--markdown-output", default=None, help="Optional Markdown report output path.")
    parser.add_argument("--reviewed-only", action="store_true", help="Only include rows where reviewed=true.")
    parser.add_argument(
        "--collapse-whitespace",
        action="store_true",
        help="Ignore pure whitespace formatting differences inside field values.",
    )
    args = parser.parse_args()

    metrics: List[FileMetrics] = []
    for raw_path in args.inputs:
        path = Path(raw_path)
        records = filter_reviewed_records(load_json_records(path), args.reviewed_only)
        if not records:
            raise SystemExit(f"{path} has no records left after filtering.")
        metrics.append(compute_file_metrics(path, records, args.collapse_whitespace))

    overall = combine_metrics(metrics)
    write_json(
        Path(args.output),
        {
            "score_definition": "Real-world doctor-edit modification score over 6 editable fields.",
            "editable_field_count": len(SUMMARY_FIELDS),
            "overall": overall,
            "tables": [serialize_metric(metric) for metric in metrics],
        },
    )

    if args.markdown_output:
        Path(args.markdown_output).write_text(build_markdown_report(metrics, overall), encoding="utf-8")


if __name__ == "__main__":
    main()
