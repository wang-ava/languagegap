#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Dict, List

from common import extract_text_response, get_client, parse_json_object, read_json_objects, usage_dict, write_jsonl


SUMMARY_FIELDS = [
    "chief_complaint",
    "history_of_present_illness",
    "past_history",
    "allergy_history",
]


def build_dialogue_text(turns: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        speaker = turn.get("speaker_label") or turn.get("speaker_id") or f"turn_{index}"
        text = str(turn.get("text", "")).strip()
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def prompt_for_language(language: str) -> str:
    return (
        "Based only on the clinic dialogue below, produce a structured medical summary. "
        "Use only information supported by the dialogue. "
        "Return valid JSON with exactly these fields: "
        "chief_complaint, history_of_present_illness, past_history, allergy_history. "
        f"Write the field values in {language}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize DoctorPeng dialogues into structured fields.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-language", default="English")
    parser.add_argument(
        "--predicted-field",
        default="predicted_medical_record",
        help="Field name for the model summary. Use medical_record to mimic the production summary layout.",
    )
    parser.add_argument("--model", default="openai/gpt-4o")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    rows = read_json_objects(Path(args.input))
    if args.limit is not None:
        rows = rows[: args.limit]

    client = get_client(api_key=args.api_key, base_url=args.base_url)
    outputs: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        turns = row.get("conversation_turns") or []
        dialogue = build_dialogue_text(list(turns))
        response = client.chat.completions.create(
            model=args.model,
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": "You are a medical documentation assistant. Output valid JSON only.",
                },
                {
                    "role": "user",
                    "content": f"{prompt_for_language(args.target_language)}\n\nDialogue:\n{dialogue}",
                },
            ],
        )
        raw_text = extract_text_response(response)
        parsed = parse_json_object(raw_text)
        predicted = {field: parsed.get(field) for field in SUMMARY_FIELDS}
        out = copy.deepcopy(row)
        out[args.predicted_field] = predicted
        out["summary_meta"] = {
            "target_language": args.target_language,
            "predicted_field": args.predicted_field,
            "model": args.model,
            **usage_dict(response),
        }
        out["summary_raw_text"] = raw_text
        outputs.append(out)

    write_jsonl(Path(args.output), outputs)


if __name__ == "__main__":
    main()
