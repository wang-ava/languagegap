#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from common import read_json_objects, write_json


REVIEW_FIELDS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_history",
    "personal_history",
    "allergy_history",
    "genetic_history",
]

REVIEW_TABLE_LABELS = {
    "table2": "English Summary",
    "table4": "English-to-Chinese Back-Translation",
}


def private_realworld_root(repo_root: Path) -> Path:
    return repo_root / ("doctor" + "peng")


def sanitized_source_path(path_text: str) -> str:
    normalized = str(path_text).replace("\\", "/")
    needle = "/" + "doctor" + "peng" + "/"
    if needle in normalized:
        return "path/to/realworld/" + normalized.split(needle, 1)[1]
    if normalized.startswith("doctor" + "peng" + "/"):
        return "path/to/realworld/" + normalized.split("/", 1)[1]
    return normalized


def sanitize_review_case(row: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = copy.deepcopy(row)
    if isinstance(sanitized.get("source_jsonl"), str):
        sanitized["source_jsonl"] = sanitized_source_path(sanitized["source_jsonl"])
    return sanitized


def find_by_key(rows: Iterable[Dict[str, Any]], key: str, value: Any) -> Optional[Dict[str, Any]]:
    for row in rows:
        if isinstance(row, dict) and row.get(key) == value:
            return row
    return None


def find_required_by_key(rows: Iterable[Dict[str, Any]], key: str, value: Any, label: str) -> Dict[str, Any]:
    row = find_by_key(rows, key, value)
    if row is None:
        raise ValueError(f"Could not find {label} where {key}={value!r}.")
    return row


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def normalize_realworld_summary_case(original_case: Dict[str, Any], summary_case: Dict[str, Any]) -> Dict[str, Any]:
    normalized = copy.deepcopy(original_case)
    predicted = summary_case.get("medical_record")
    if not isinstance(predicted, dict):
        raise ValueError(
            f"Real-world summary row for patient_id={original_case.get('patient_id')} is missing dict medical_record."
        )
    normalized["predicted_medical_record"] = predicted
    normalized["summary_output_layout"] = "production_summary_replaces_medical_record"
    return normalized


def compute_review_table_summary(table_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    changed_field_count = 0
    modified_record_count = 0
    per_field_counts = {field: 0 for field in REVIEW_FIELDS}
    record_summaries = []

    for row in rows:
        edited = row.get("edited_report") or {}
        original = row.get("original_current_report") or {}
        changed_fields_for_record = 0
        for field in REVIEW_FIELDS:
            edited_value = str(edited.get(field) or "").strip()
            original_value = str(original.get(field) or "").strip()
            if edited_value != original_value:
                changed_field_count += 1
                changed_fields_for_record += 1
                per_field_counts[field] += 1
        modified = changed_fields_for_record > 0
        if modified:
            modified_record_count += 1
        record_summaries.append(
            {
                "uid": row.get("uid"),
                "row_index": row.get("row_index"),
                "patient_id": row.get("patient_id"),
                "changed_field_count": changed_fields_for_record,
                "record_score": round(changed_fields_for_record / len(REVIEW_FIELDS), 6),
                "modified": modified,
            }
        )

    sample_count = len(rows)
    total_field_slots = sample_count * len(REVIEW_FIELDS)
    modification_score = changed_field_count / total_field_slots if total_field_slots else 0.0
    modification_rate = modified_record_count / sample_count if sample_count else 0.0
    return {
        "table_id": table_id,
        "title": REVIEW_TABLE_LABELS.get(table_id, table_id),
        "sample_count": sample_count,
        "changed_field_count": changed_field_count,
        "total_field_slots": total_field_slots,
        "modification_score": round(modification_score, 6),
        "modification_score_percent": round(modification_score * 100, 2),
        "modified_record_count": modified_record_count,
        "modified_rate": round(modification_rate, 6),
        "modified_rate_percent": round(modification_rate * 100, 2),
        "per_field_counts": per_field_counts,
        "records": record_summaries,
    }


def build_example_modification_summary(table_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    overall_changed_field_count = sum(table["changed_field_count"] for table in table_summaries)
    overall_total_field_slots = sum(table["total_field_slots"] for table in table_summaries)
    overall_modified_record_count = sum(table["modified_record_count"] for table in table_summaries)
    overall_record_count = sum(table["sample_count"] for table in table_summaries)
    overall_per_field_counts = {field: 0 for field in REVIEW_FIELDS}
    for table in table_summaries:
        for field in REVIEW_FIELDS:
            overall_per_field_counts[field] += table["per_field_counts"][field]

    overall_modification_score = (
        overall_changed_field_count / overall_total_field_slots if overall_total_field_slots else 0.0
    )
    overall_modification_rate = (
        overall_modified_record_count / overall_record_count if overall_record_count else 0.0
    )
    return {
        "score_definition": "Real-world doctor-edit modification score over 6 editable fields.",
        "editable_field_count": len(REVIEW_FIELDS),
        "note": "Reviewer example summary includes only the exported table2 and table4 review files.",
        "overall": {
            "record_count": overall_record_count,
            "changed_field_count": overall_changed_field_count,
            "total_field_slots": overall_total_field_slots,
            "modification_score": round(overall_modification_score, 6),
            "modification_score_percent": round(overall_modification_score * 100, 2),
            "modified_record_count": overall_modified_record_count,
            "modified_rate": round(overall_modification_rate, 6),
            "modified_rate_percent": round(overall_modification_rate * 100, 2),
            "per_field_counts": overall_per_field_counts,
        },
        "tables": table_summaries,
    }


def export_healthbench(repo_root: Path, output_root: Path) -> Dict[str, Any]:
    original_rows = [
        row for row in read_json_objects(repo_root / "Healthbench/dataset/hard_2025-05-08-21-00-10_english_only_sample_100.jsonl")
        if isinstance(row, dict)
    ]
    translation_rows = [
        row for row in read_json_objects(repo_root / "Healthbench/result/translate/google_gemini-3-pro-preview/chinese_translation.jsonl")
        if isinstance(row, dict)
    ]
    back_rows = [
        row for row in read_json_objects(repo_root / "Healthbench/result/translate_back/google_gemini-3-pro-preview/chinese_back_translation.jsonl")
        if isinstance(row, dict)
    ]
    response_rows = json.loads(
        (repo_root / "Healthbench/result/response/google_gemini-3-pro-preview/ZH/round1.json").read_text(encoding="utf-8")
    )
    response_case = next(row for row in response_rows if row.get("response"))
    prompt_id = response_case["prompt_id"]

    original_case = find_required_by_key(original_rows, "prompt_id", prompt_id, "HealthBench original case")
    translation_case = find_required_by_key(translation_rows, "prompt_id", prompt_id, "HealthBench translation case")
    back_case = find_required_by_key(back_rows, "prompt_id", prompt_id, "HealthBench back-translation case")

    case_dir = output_root / "healthbench"
    write_json(
        case_dir / "original_case.json",
        {
            "prompt_id": prompt_id,
            "prompt": original_case.get("prompt"),
            "ideal_completions_data": original_case.get("ideal_completions_data"),
            "rubrics_preview": (original_case.get("rubrics") or [])[:3],
        },
    )
    write_json(
        case_dir / "zh_translation_case.json",
        {
            "prompt_id": prompt_id,
            "translation": translation_case.get("translation"),
            "translation_meta": translation_case.get("translation_meta"),
        },
    )
    write_json(
        case_dir / "zh_back_translation_case.json",
        {
            "prompt_id": prompt_id,
            "back_translation": back_case.get("prompt"),
        },
    )
    write_json(
        case_dir / "zh_model_response_round1.json",
        {
            "prompt_id": response_case.get("prompt_id"),
            "language": response_case.get("language"),
            "round": response_case.get("round"),
            "response": response_case.get("response"),
            "error": response_case.get("error"),
        },
    )
    return {"prompt_id": prompt_id}


def export_mimic_iii(repo_root: Path, output_root: Path) -> Dict[str, Any]:
    translation_rows = [
        row
        for row in read_json_objects(
            repo_root / "MIMIC-III/result/translate/google_gemini-3-pro-preview/Chinese&Malay/chinese_translation.jsonl"
        )
        if isinstance(row, dict)
    ]
    back_translation_rows = [
        row
        for row in read_json_objects(
            repo_root / "MIMIC-III/result/translate_back/google_gemini-3-pro-preview/chinese_back_to_english.jsonl"
        )
        if isinstance(row, dict)
    ]

    zh_responses = json.loads(
        (repo_root / "MIMIC-III/result/response copy/openai_gpt-5.2_1/Chinese/round1.json").read_text(encoding="utf-8")
    )
    zh_case = zh_responses[0]
    fig_idx = int(str(zh_case["patient_id"]).split("_")[-1])

    original_meta = json.loads(
        (repo_root / f"MIMIC-III/dataset/data/figure/patient/patient_{fig_idx}_meta.json").read_text(encoding="utf-8")
    )
    patient_id = original_meta["patient_id"]

    translation_example = find_required_by_key(
        translation_rows,
        "patient_id",
        patient_id,
        "MIMIC-III diagnosis translation example",
    )

    back_translation_example = find_by_key(back_translation_rows, "patient_id", patient_id)
    back_en_meta = json.loads(
        (
            repo_root
            / f"MIMIC-III/result/translate_back/google_gemini-3-pro-preview/figures/chinese/patient/patient_{fig_idx}_meta.json"
        ).read_text(encoding="utf-8")
    )
    if back_translation_example is None:
        back_translation_example = {
            "patient_id": patient_id,
            "language": "English",
            "source_language": "Mandarin Chinese",
            "source_language_key": "chinese",
            "source_diagnosis": translation_example.get("diagnosis"),
            "diagnosis": back_en_meta.get("diagnosis"),
            "fig_idx": fig_idx,
            "derived_from": (
                "MIMIC-III/result/translate_back/google_gemini-3-pro-preview/figures/chinese/"
                f"patient/patient_{fig_idx}_meta.json"
            ),
            "note": (
                "This repository snapshot does not contain a matching row for this patient in "
                "chinese_back_to_english.jsonl, so the pivot diagnosis is recovered from the generated English figure metadata."
            ),
        }

    back_en_responses = json.loads(
        (repo_root / "MIMIC-III/result/response_back_in_english copy/openai_gpt-4o/Chinese/round1.json").read_text(
            encoding="utf-8"
        )
    )
    back_en_case = next(row for row in back_en_responses if row.get("patient_id") == f"patient_{fig_idx}")

    zh_image_path = repo_root / f"MIMIC-III/dataset/data/figure/chinese/patient_{fig_idx}_chinese.jpg"
    back_en_image_path = (
        repo_root / f"MIMIC-III/result/translate_back/google_gemini-3-pro-preview/figures/chinese/patient_{fig_idx}_english.jpg"
    )
    if not back_en_image_path.exists():
        back_en_image_path = repo_root / f"MIMIC-III/dataset/data/figure/english/patient_{fig_idx}_english.jpg"

    zh_case = copy.deepcopy(zh_case)
    zh_case["image_path"] = repo_relative_path(repo_root, zh_image_path)
    back_en_case = copy.deepcopy(back_en_case)
    back_en_case["image_path"] = repo_relative_path(repo_root, back_en_image_path)

    case_dir = output_root / "mimic_iii"
    write_json(case_dir / "diagnosis_translation_example.json", translation_example)
    write_json(case_dir / "diagnosis_back_translation_example.json", back_translation_example)
    write_json(case_dir / "original_figure_meta.json", original_meta)
    write_json(case_dir / "back_translated_figure_meta.json", back_en_meta)
    write_json(case_dir / "zh_model_response_round1.json", zh_case)
    write_json(case_dir / "zh_back_in_english_response_round1.json", back_en_case)
    return {"fig_idx": fig_idx, "patient_id": patient_id}


def export_realworld(repo_root: Path, output_root: Path) -> Dict[str, Any]:
    dataset_root = private_realworld_root(repo_root)
    original_rows = [
        row for row in read_json_objects(dataset_root / "data/dialogue_quality_sample_50.jsonl") if isinstance(row, dict)
    ]
    en_translation_rows = [
        row
        for row in read_json_objects(dataset_root / "result/translate/google_gemini-3-pro-preview/english_translation.jsonl")
        if isinstance(row, dict)
    ]
    en_summary_rows = [
        row
        for row in read_json_objects(
            dataset_root / "result/summary/qwen_qwen3-vl-235b-a22b-thinking/english_summary.jsonl"
        )
        if isinstance(row, dict)
    ]
    en_back_rows = [
        row
        for row in read_json_objects(
            dataset_root / "result/translate_back/google_gemini-3-pro-preview/english_back_to_chinese.jsonl"
        )
        if isinstance(row, dict)
    ]
    en_back_summary_rows = [
        row
        for row in read_json_objects(
            dataset_root / "result/summary_back/qwen_qwen3-vl-235b-a22b-thinking/english_back_to_chinese_summary.jsonl"
        )
        if isinstance(row, dict)
    ]
    english_review_rows = json.loads(
        (
            dataset_root
            / "result/translated_non_chinese_to_chinese/qwen_qwen3-vl-235b-a22b-thinking/result/edits_table2_english_summary_doctor_review (1).json"
        ).read_text(encoding="utf-8")
    )
    english_back_review_rows = json.loads(
        (
            dataset_root
            / "result/translated_non_chinese_to_chinese/qwen_qwen3-vl-235b-a22b-thinking/result/edits_table4_english_back_to_chinese_summary_doctor_review (1).json"
        ).read_text(encoding="utf-8")
    )
    patient_id = original_rows[0]["patient_id"]
    original_case = find_required_by_key(original_rows, "patient_id", patient_id, "real-world original case")
    translation_case = find_required_by_key(
        en_translation_rows,
        "patient_id",
        patient_id,
        "real-world English translation case",
    )
    summary_case = find_required_by_key(en_summary_rows, "patient_id", patient_id, "real-world English summary case")
    back_case = find_required_by_key(en_back_rows, "patient_id", patient_id, "real-world English back-translation case")
    back_summary_case = find_required_by_key(
        en_back_summary_rows,
        "patient_id",
        patient_id,
        "real-world English back-to-Chinese summary case",
    )
    english_review_case = find_required_by_key(
        english_review_rows,
        "patient_id",
        str(patient_id),
        "real-world English doctor-review case",
    )
    english_back_review_case = find_required_by_key(
        english_back_review_rows,
        "patient_id",
        str(patient_id),
        "real-world English back-to-Chinese doctor-review case",
    )

    case_dir = output_root / "realworld"
    write_json(case_dir / "original_dialogue_case.json", original_case)
    write_json(case_dir / "english_translation_case.json", translation_case)
    write_json(case_dir / "english_summary_case.json", normalize_realworld_summary_case(original_case, summary_case))
    write_json(case_dir / "english_back_to_chinese_case.json", back_case)
    write_json(
        case_dir / "english_back_to_chinese_summary_case.json",
        normalize_realworld_summary_case(original_case, back_summary_case),
    )
    write_json(case_dir / "english_summary_doctor_review_case.json", sanitize_review_case(english_review_case))
    write_json(case_dir / "english_back_to_chinese_doctor_review_case.json", sanitize_review_case(english_back_review_case))
    write_json(
        case_dir / "modification_score_summary.json",
        build_example_modification_summary(
            [
                compute_review_table_summary("table2", english_review_rows),
                compute_review_table_summary("table4", english_back_review_rows),
            ]
        ),
    )
    return {
        "patient_id": patient_id,
        "english_review_uid": english_review_case.get("uid"),
        "english_back_review_uid": english_back_review_case.get("uid"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a few reviewer-friendly examples from the full repository.")
    parser.add_argument("--repo-root", default=".", help="Path to the full repository root.")
    parser.add_argument(
        "--output-root",
        default=None,
        help="Defaults to examples under the current script's parent directory.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    default_output = Path(__file__).resolve().parent.parent / "examples"
    output_root = Path(args.output_root).resolve() if args.output_root else default_output

    for stale_dir in ("healthbench", "mimic_iii", "realworld"):
        shutil.rmtree(output_root / stale_dir, ignore_errors=True)

    manifest = {
        "healthbench": export_healthbench(repo_root, output_root),
        "mimic_iii": export_mimic_iii(repo_root, output_root),
        "realworld": export_realworld(repo_root, output_root),
    }
    write_json(output_root / "manifest.json", manifest)


if __name__ == "__main__":
    main()
