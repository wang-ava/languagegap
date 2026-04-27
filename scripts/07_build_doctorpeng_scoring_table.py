#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from common import read_json_objects


EXCLUDED_REPORT_KEYS = {
    "physical_exam",
    "specialist_exam_summary",
    "preliminary_diagnosis",
}

SCORE_COLUMNS = [
    "维度1_主诉与核心问题保真度(1-5)",
    "维度2_关键信息完整性(1-5)",
    "维度3_医学事实准确性(1-5)",
    "维度4_时序与逻辑一致性(1-5)",
    "维度5_安全性与风险识别(1-5)",
    "维度6_临床可操作性(1-5)",
    "维度7_表达清晰与结构化(1-5)",
]

OUTPUT_COLUMNS = [
    "序号",
    "patient_id",
    "patient_label",
    "section",
    "section_title",
    "dialogue_quality_raw",
    "原始对话信息",
    "对应翻译后对话",
    "原始报告",
    "模型回答报告",
    *SCORE_COLUMNS,
    "总分(7-35)",
    "处理建议(采纳/需修改/不采纳)",
    "主要问题定位",
    "医生总体评语",
]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def clean_report_obj(obj: Any) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    return {key: value for key, value in obj.items() if key not in EXCLUDED_REPORT_KEYS}


def format_turns(turns: Any) -> str:
    lines: List[str] = []
    if not isinstance(turns, list):
        return ""
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        speaker = normalize_text(turn.get("speaker_label")).strip()
        if not speaker:
            speaker_id = normalize_text(turn.get("speaker_id")).strip()
            speaker = f"说话人 {speaker_id}" if speaker_id else "说话人"
        text = normalize_text(turn.get("text")).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def row_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (
        normalize_text(row.get("patient_id")).strip(),
        normalize_text(row.get("section")).strip(),
    )


def predicted_record(row: Dict[str, Any]) -> Dict[str, Any]:
    predicted = row.get("predicted_medical_record")
    if isinstance(predicted, dict):
        return clean_report_obj(predicted)
    return clean_report_obj(row.get("medical_record"))


def load_rows(path: Path) -> List[Dict[str, Any]]:
    return [row for row in read_json_objects(path) if isinstance(row, dict)]


def build_predicted_index(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, Any]]:
    index: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        key = row_key(row)
        index[key] = row
    return index


def build_output_rows(reference_rows: List[Dict[str, Any]], predicted_rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    predicted_index = build_predicted_index(predicted_rows)
    output_rows: List[Dict[str, str]] = []

    for order, reference_row in enumerate(reference_rows, start=1):
        key = row_key(reference_row)
        predicted_row = predicted_index.get(key)
        if predicted_row is None:
            raise ValueError(
                f"Missing predicted row for patient_id={key[0]!r}, section={key[1]!r}."
            )

        reference_dialogue = format_turns(reference_row.get("conversation_turns"))
        current_dialogue = format_turns(predicted_row.get("conversation_turns"))
        reference_report = json.dumps(clean_report_obj(reference_row.get("medical_record")), ensure_ascii=False)
        model_report = json.dumps(predicted_record(predicted_row), ensure_ascii=False)

        output_rows.append(
            {
                "序号": str(order),
                "patient_id": normalize_text(reference_row.get("patient_id")).strip(),
                "patient_label": normalize_text(reference_row.get("patient_label")).strip(),
                "section": normalize_text(reference_row.get("section")).strip(),
                "section_title": normalize_text(reference_row.get("section_title")).strip(),
                "dialogue_quality_raw": normalize_text(reference_row.get("dialogue_quality_raw")).strip(),
                "原始对话信息": reference_dialogue,
                "对应翻译后对话": current_dialogue or reference_dialogue,
                "原始报告": reference_report,
                "模型回答报告": model_report,
                "维度1_主诉与核心问题保真度(1-5)": "",
                "维度2_关键信息完整性(1-5)": "",
                "维度3_医学事实准确性(1-5)": "",
                "维度4_时序与逻辑一致性(1-5)": "",
                "维度5_安全性与风险识别(1-5)": "",
                "维度6_临床可操作性(1-5)": "",
                "维度7_表达清晰与结构化(1-5)": "",
                "总分(7-35)": "",
                "处理建议(采纳/需修改/不采纳)": "",
                "主要问题定位": "",
                "医生总体评语": "",
            }
        )

    return output_rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a DoctorPeng 7-dimension scoring CSV from reference rows and model summaries."
    )
    parser.add_argument("--reference-input", required=True, help="Original DoctorPeng JSON/JSONL file.")
    parser.add_argument(
        "--predicted-input",
        required=True,
        help="Summary JSON/JSONL file keyed by patient_id and section.",
    )
    parser.add_argument("--output", required=True, help="Output scoring CSV.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    reference_rows = load_rows(Path(args.reference_input))
    predicted_rows = load_rows(Path(args.predicted_input))
    if args.limit is not None:
        reference_rows = reference_rows[: args.limit]

    output_rows = build_output_rows(reference_rows, predicted_rows)
    write_csv(Path(args.output), output_rows)


if __name__ == "__main__":
    main()
