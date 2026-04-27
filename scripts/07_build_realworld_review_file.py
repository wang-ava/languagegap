#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from common import read_json_objects, write_json


SUMMARY_FIELDS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_history",
    "personal_history",
    "allergy_history",
    "genetic_history",
]

FIELD_LABELS_ZH = {
    "chief_complaint": "主诉",
    "history_of_present_illness": "现病史",
    "past_history": "既往史",
    "personal_history": "个人史",
    "allergy_history": "过敏史",
    "genetic_history": "家族史",
}

SOURCE_ID_MAP = {
    "chinese_summary.jsonl": "table1_chinese_summary",
    "english_summary.jsonl": "table2_english_summary",
    "thai_summary.jsonl": "table3_thai_summary",
    "english_back_to_chinese_summary.jsonl": "table4_english_back_to_chinese_summary",
    "thai_back_to_chinese_summary.jsonl": "table5_thai_back_to_chinese_summary",
}

TRANSCRIPT_MARKERS = {"语音转文字内容（对话记录）"}
SEPARATOR_RE = re.compile(r"^[\-\u2500\u2501\u2504\u2508\u2550\u2014]{6,}$")
SPEAKER_RE = re.compile(r"^说话人\s*\d+$")


def to_text(value: Any) -> str:
    return "" if value is None else str(value)


def sha256sum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_source_id(path: Path) -> str:
    return SOURCE_ID_MAP.get(path.name, path.stem)


def normalize_predicted_record(row: Dict[str, Any]) -> Dict[str, str]:
    for field_name in ("predicted_medical_record", "medical_record"):
        value = row.get(field_name)
        if isinstance(value, dict):
            return {field: to_text(value.get(field)).strip() for field in SUMMARY_FIELDS}
    raise ValueError(
        "Could not find a predicted summary dict in either 'predicted_medical_record' or 'medical_record'."
    )


def format_turns(turns: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        speaker = to_text(turn.get("speaker_label")).strip()
        if not speaker:
            speaker_id = to_text(turn.get("speaker_id")).strip()
            speaker = f"说话人 {speaker_id}" if speaker_id else f"turn_{index}"
        text = to_text(turn.get("text")).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def format_report(report_obj: Dict[str, Any]) -> str:
    blocks: List[str] = []
    for field in SUMMARY_FIELDS:
        blocks.append(f"{FIELD_LABELS_ZH[field]}：\n{to_text(report_obj.get(field)).strip()}")
    return "\n\n".join(blocks).strip()


def format_raw_dialogue_lines(lines: List[str]) -> str:
    if not lines:
        return ""

    formatted: List[str] = []
    current_speaker: str | None = None
    current_parts: List[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_parts
        if current_speaker and current_parts:
            formatted.append(f"{current_speaker}: {' '.join(current_parts).strip()}")
        elif current_parts:
            formatted.extend(part for part in current_parts if part.strip())
        current_speaker = None
        current_parts = []

    for line in lines:
        if SPEAKER_RE.match(line):
            flush()
            current_speaker = line
            continue
        current_parts.append(line)
    flush()
    return "\n".join(formatted) if formatted else "\n".join(lines)


def extract_original_report_and_dialogue(
    raw_lines: List[Any],
    heading: str,
    patient_label: str,
) -> Tuple[str, str]:
    lines = [to_text(line).strip() for line in raw_lines if to_text(line).strip()]

    report_lines: List[str] = []
    dialogue_lines: List[str] = []
    in_dialogue = False

    for line in lines:
        if SEPARATOR_RE.match(line):
            break
        if line in TRANSCRIPT_MARKERS:
            in_dialogue = True
            continue
        if not in_dialogue:
            if (
                line == heading
                or line == patient_label
                or line == "图片信息"
                or line.startswith("来源文件：")
                or line.startswith("对话质量：")
            ):
                continue
            report_lines.append(line)
        else:
            if line == patient_label:
                break
            dialogue_lines.append(line)

    return "\n".join(report_lines).strip(), format_raw_dialogue_lines(dialogue_lines)


def build_review_rows(
    rows: List[Dict[str, Any]],
    input_path: Path,
    source_id: str,
    edited_report_language: str,
) -> List[Dict[str, Any]]:
    source_sha256 = sha256sum(input_path)
    review_rows: List[Dict[str, Any]] = []

    for row_index, row in enumerate(rows, start=1):
        predicted_record = normalize_predicted_record(row)
        raw_lines = row.get("raw_lines")
        if not isinstance(raw_lines, list):
            raw_lines = []
        original_report_text, original_dialogue = extract_original_report_and_dialogue(
            raw_lines=raw_lines,
            heading=to_text(row.get("heading")).strip(),
            patient_label=to_text(row.get("patient_label")).strip(),
        )
        editable_report_text = format_report(predicted_record)

        review_rows.append(
            {
                "uid": f"{source_id}:{row_index}",
                "row_index": row_index,
                "patient_id": to_text(row.get("patient_id")).strip(),
                "patient_label": to_text(row.get("patient_label")).strip(),
                "source_id": source_id,
                "source_jsonl": input_path.as_posix(),
                "source_line_number": row_index,
                "source_sha256": source_sha256,
                "reviewed": False,
                "edited_report_language": edited_report_language,
                "edited_report_text": editable_report_text,
                "edited_report": dict(predicted_record),
                "original_current_report_text": editable_report_text,
                "original_current_report": dict(predicted_record),
                "original_report_text_from_raw_lines": original_report_text,
                "original_dialogue_from_raw_lines": original_dialogue,
                "current_dialogue": format_turns(list(row.get("conversation_turns") or [])),
                "raw_record": row,
            }
        )

    return review_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a real-world doctor-review JSON file aligned to the exported edit schema."
    )
    parser.add_argument("--input", required=True, help="Summary JSON/JSONL file to review.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument(
        "--source-id",
        default=None,
        help="Optional source_id such as table2_english_summary. Defaults to an inference from the input filename.",
    )
    parser.add_argument(
        "--edited-report-language",
        default="zh",
        help="Language tag stored in edited_report_language. Defaults to zh to match the Chinese-normalized review workflow.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional number of rows to export.")
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = [row for row in read_json_objects(input_path) if isinstance(row, dict)]
    if args.limit is not None:
        rows = rows[: args.limit]

    source_id = args.source_id or infer_source_id(input_path)
    write_json(
        Path(args.output),
        build_review_rows(
            rows=rows,
            input_path=input_path,
            source_id=source_id,
            edited_report_language=args.edited_report_language,
        ),
    )


if __name__ == "__main__":
    main()
