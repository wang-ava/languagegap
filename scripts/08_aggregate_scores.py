#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Tuple

from common import write_json


DIMENSIONS: List[Tuple[str, str]] = [
    ("维度1_主诉与核心问题保真度(1-5)", "chief_complaint_fidelity"),
    ("维度2_关键信息完整性(1-5)", "information_completeness"),
    ("维度3_医学事实准确性(1-5)", "medical_accuracy"),
    ("维度4_时序与逻辑一致性(1-5)", "temporal_logical_consistency"),
    ("维度5_安全性与风险识别(1-5)", "safety_risk_awareness"),
    ("维度6_临床可操作性(1-5)", "clinical_actionability"),
    ("维度7_表达清晰与结构化(1-5)", "clarity_and_structure"),
]
TOTAL_COLUMN = "总分(7-35)"
RECOMMENDATION_COLUMN = "处理建议(采纳/需修改/不采纳)"


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader)


def normalize_recommendation(value: str) -> str:
    text = (value or "").strip()
    mapping = {
        "采纳": "accept",
        "需修改": "needs_revision",
        "不采纳": "reject",
        "accept": "accept",
        "needs_revision": "needs_revision",
        "reject": "reject",
    }
    return mapping.get(text, text or "blank")


def parse_scored_row(row: Dict[str, str], path: Path, row_number: int) -> Dict[str, Any] | None:
    raw_scores = [(label, (row.get(label) or "").strip()) for label, _ in DIMENSIONS]
    present = [value for _, value in raw_scores if value]
    if not present:
        return None
    if len(present) != len(raw_scores):
        raise ValueError(f"Incomplete scoring row at {path}:{row_number}. Either fill all 7 dimensions or leave all blank.")

    parsed_scores: Dict[str, int] = {}
    score_sum = 0
    for label, key in DIMENSIONS:
        try:
            value = int((row.get(label) or "").strip())
        except ValueError as exc:
            raise ValueError(f"Invalid integer score in {path}:{row_number} column {label!r}.") from exc
        if value < 1 or value > 5:
            raise ValueError(f"Score out of range in {path}:{row_number} column {label!r}: {value}")
        parsed_scores[key] = value
        score_sum += value

    total_text = (row.get(TOTAL_COLUMN) or "").strip()
    if total_text:
        try:
            provided_total = int(total_text)
        except ValueError as exc:
            raise ValueError(f"Invalid total score in {path}:{row_number}.") from exc
        if provided_total != score_sum:
            raise ValueError(
                f"Total score mismatch in {path}:{row_number}. Expected {score_sum}, found {provided_total}."
            )

    return {
        "patient_id": (row.get("patient_id") or "").strip(),
        "scores": parsed_scores,
        "total_score": score_sum,
        "recommendation": normalize_recommendation(row.get(RECOMMENDATION_COLUMN) or ""),
    }


def summarize_file(path: Path) -> Dict[str, Any]:
    rows = read_rows(path)
    scored_rows: List[Dict[str, Any]] = []
    for row_number, row in enumerate(rows, start=2):
        parsed = parse_scored_row(row, path, row_number)
        if parsed is not None:
            scored_rows.append(parsed)

    per_dimension: Dict[str, float] = {}
    for _, key in DIMENSIONS:
        values = [row["scores"][key] for row in scored_rows]
        per_dimension[key] = round(mean(values), 4) if values else 0.0

    recommendation_counts: Dict[str, int] = {}
    for row in scored_rows:
        recommendation = row["recommendation"]
        recommendation_counts[recommendation] = recommendation_counts.get(recommendation, 0) + 1

    total_scores = [row["total_score"] for row in scored_rows]
    return {
        "file": path.name,
        "n_rows": len(rows),
        "n_scored_rows": len(scored_rows),
        "n_unscored_rows": len(rows) - len(scored_rows),
        "mean_total_score": round(mean(total_scores), 4) if total_scores else 0.0,
        "mean_dimension_scores": per_dimension,
        "recommendation_counts": recommendation_counts,
    }


def build_markdown(file_summaries: List[Dict[str, Any]]) -> str:
    lines = [
        "# Doctor Score Summary",
        "",
        "## File-Level Summary",
        "",
        "| File | Scored Rows | Mean Total Score |",
        "|---|---:|---:|",
    ]
    for summary in file_summaries:
        lines.append(
            f"| {summary['file']} | {summary['n_scored_rows']}/{summary['n_rows']} | {summary['mean_total_score']:.2f} |"
        )

    if file_summaries:
        lines.extend(["", "## Dimension Means", ""])
        for summary in file_summaries:
            lines.append(f"### {summary['file']}")
            lines.append("")
            lines.append("| Dimension | Mean Score |")
            lines.append("|---|---:|")
            for _, key in DIMENSIONS:
                lines.append(f"| {key} | {summary['mean_dimension_scores'][key]:.2f} |")
            lines.append("")
            lines.append("Recommendation counts:")
            for recommendation, count in sorted(summary["recommendation_counts"].items()):
                lines.append(f"- {recommendation}: {count}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate completed DoctorPeng 7-dimension scoring CSVs."
    )
    parser.add_argument("--inputs", nargs="+", required=True, help="One or more completed scoring CSV files.")
    parser.add_argument("--output", required=True, help="Output JSON summary.")
    parser.add_argument(
        "--markdown-output",
        default=None,
        help="Optional markdown summary. Defaults to <output>.md",
    )
    args = parser.parse_args()

    file_summaries = [summarize_file(Path(path)) for path in args.inputs]
    payload = {"files": file_summaries}
    write_json(Path(args.output), payload)

    markdown_path = Path(args.markdown_output) if args.markdown_output else Path(f"{args.output}.md")
    markdown_path.write_text(build_markdown(file_summaries), encoding="utf-8")


if __name__ == "__main__":
    main()
