#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from common import normalized_text, read_json_objects, write_json, write_jsonl


FIELDS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_history",
    "personal_history",
    "allergy_history",
    "genetic_history",
]
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")


def similarity(a: Any, b: Any) -> float:
    return round(difflib.SequenceMatcher(None, normalized_text(a), normalized_text(b)).ratio(), 4)


def contains_chinese(text: str) -> bool:
    return bool(CHINESE_RE.search(text))


def combined_record_text(record: Dict[str, Any]) -> str:
    return "\n".join(str(record.get(field) or "") for field in FIELDS)


def row_identifier(row: Dict[str, Any]) -> str:
    for key in ("patient_id", "heading", "source_file"):
        value = row.get(key)
        if value not in (None, ""):
            return f"{key}={value}"
    return "unknown_row"


def require_record(row: Dict[str, Any], field_name: str) -> Dict[str, Any]:
    value = row.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"Row {row_identifier(row)} is missing a dict field '{field_name}'.")
    return value


def extract_predicted_record(row: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    predicted = row.get("predicted_medical_record")
    if isinstance(predicted, dict):
        return predicted, "predicted_medical_record"
    medical_record = row.get("medical_record")
    if isinstance(medical_record, dict):
        return medical_record, "medical_record"
    raise ValueError(
        f"Row {row_identifier(row)} is missing both 'predicted_medical_record' and dict 'medical_record'."
    )


def load_rows(path: Path) -> List[Dict[str, Any]]:
    return [row for row in read_json_objects(path) if isinstance(row, dict)]


def build_single_file_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    paired_rows: List[Dict[str, Any]] = []
    for row in rows:
        reference = require_record(row, "medical_record")
        predicted = row.get("predicted_medical_record")
        if not isinstance(predicted, dict):
            raise ValueError(
                "Single-file mode requires every row to contain 'predicted_medical_record'. "
                f"Problem row: {row_identifier(row)}."
            )
        paired_rows.append(
            {
                "patient_id": row.get("patient_id"),
                "heading": row.get("heading"),
                "reference": reference,
                "predicted": predicted,
                "predicted_source_field": "predicted_medical_record",
            }
        )
    return paired_rows


def build_two_file_rows(reference_rows: List[Dict[str, Any]], predicted_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    predicted_by_id: Dict[str, Dict[str, Any]] = {}
    for row in predicted_rows:
        patient_id = row.get("patient_id")
        if patient_id in (None, ""):
            raise ValueError("Every predicted row must contain 'patient_id' in two-file mode.")
        predicted_by_id[str(patient_id)] = row

    paired_rows: List[Dict[str, Any]] = []
    missing_predictions: List[str] = []
    for row in reference_rows:
        patient_id = row.get("patient_id")
        if patient_id in (None, ""):
            raise ValueError("Every reference row must contain 'patient_id' in two-file mode.")
        matched = predicted_by_id.get(str(patient_id))
        if matched is None:
            missing_predictions.append(str(patient_id))
            continue
        predicted_record, predicted_source_field = extract_predicted_record(matched)
        paired_rows.append(
            {
                "patient_id": patient_id,
                "heading": row.get("heading") or matched.get("heading"),
                "reference": require_record(row, "medical_record"),
                "predicted": predicted_record,
                "predicted_source_field": predicted_source_field,
            }
        )
    if missing_predictions:
        preview = ", ".join(missing_predictions[:10])
        raise ValueError(f"Missing predicted rows for patient_id(s): {preview}")
    return paired_rows


def validate_language_compatibility(rows: List[Dict[str, Any]]) -> None:
    for row in rows:
        reference_text = combined_record_text(row["reference"])
        predicted_text = combined_record_text(row["predicted"])
        if contains_chinese(reference_text) and not contains_chinese(predicted_text):
            raise ValueError(
                "Predicted summary does not look Chinese while the reference medical_record does. "
                f"Problem row: patient_id={row.get('patient_id')}. "
                "In the reviewer package, English and Thai DoctorPeng outputs are primarily evaluated through "
                "doctor review plus modification score, not raw cross-language string similarity. Build a review "
                "file with scripts/07_build_doctorpeng_review_file.py and evaluate the edited export with "
                "scripts/08_evaluate_doctorpeng_modification.py, or compare only same-language outputs such as "
                "Chinese summaries and back-translated Chinese summaries."
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auxiliary same-language field-level comparison between DoctorPeng model summaries and reference records."
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Single-file mode: JSON/JSONL where each row contains both medical_record and predicted_medical_record.",
    )
    parser.add_argument(
        "--reference-input",
        default=None,
        help="Two-file mode: reference JSON/JSONL with medical_record, typically the original DoctorPeng dataset.",
    )
    parser.add_argument(
        "--predicted-input",
        default=None,
        help="Two-file mode: summary JSON/JSONL keyed by patient_id. The predicted summary can live in either medical_record or predicted_medical_record.",
    )
    parser.add_argument("--output", required=True, help="Per-case comparison JSONL.")
    parser.add_argument(
        "--summary-output",
        default=None,
        help="Optional aggregate summary JSON. Defaults to <output>.summary.json",
    )
    parser.add_argument(
        "--allow-cross-language",
        action="store_true",
        help="Skip the default language compatibility check. Use only if you intentionally want raw cross-language string similarity.",
    )
    args = parser.parse_args()

    using_single = args.input is not None
    using_pair = args.reference_input is not None or args.predicted_input is not None
    if using_single == using_pair:
        raise ValueError(
            "Provide either --input for single-file mode, or both --reference-input and --predicted-input for two-file mode."
        )
    if using_pair and not (args.reference_input and args.predicted_input):
        raise ValueError("Two-file mode requires both --reference-input and --predicted-input.")

    if using_single:
        rows = build_single_file_rows(load_rows(Path(args.input)))
        comparison_mode = "single_file"
    else:
        rows = build_two_file_rows(
            load_rows(Path(args.reference_input)),
            load_rows(Path(args.predicted_input)),
        )
        comparison_mode = "reference_plus_prediction"

    if not args.allow_cross_language:
        validate_language_compatibility(rows)

    comparisons: List[Dict[str, Any]] = []

    field_exact_counts = {field: 0 for field in FIELDS}
    field_similarity_totals = {field: 0.0 for field in FIELDS}

    for row in rows:
        reference = row["reference"]
        predicted = row["predicted"]
        field_results: Dict[str, Any] = {}
        for field in FIELDS:
            ref_value = reference.get(field)
            pred_value = predicted.get(field)
            exact = normalized_text(ref_value) == normalized_text(pred_value)
            sim = similarity(ref_value, pred_value)
            field_results[field] = {
                "reference": ref_value,
                "predicted": pred_value,
                "exact_match": exact,
                "similarity": sim,
            }
            field_exact_counts[field] += int(exact)
            field_similarity_totals[field] += sim

        comparisons.append(
            {
                "patient_id": row.get("patient_id"),
                "heading": row.get("heading"),
                "comparison_mode": comparison_mode,
                "predicted_source_field": row.get("predicted_source_field"),
                "field_results": field_results,
            }
        )

    write_jsonl(Path(args.output), comparisons)

    n = max(len(comparisons), 1)
    summary = {
        "comparison_mode": comparison_mode,
        "n_cases": len(comparisons),
        "field_exact_match_rate": {field: round(field_exact_counts[field] / n, 4) for field in FIELDS},
        "field_mean_similarity": {field: round(field_similarity_totals[field] / n, 4) for field in FIELDS},
    }
    summary_path = Path(args.summary_output) if args.summary_output else Path(f"{args.output}.summary.json")
    write_json(summary_path, summary)


if __name__ == "__main__":
    main()
