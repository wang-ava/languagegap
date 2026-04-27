#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from common import (
    encode_image_as_data_url,
    extract_text_response,
    get_client,
    parse_json_object,
    read_json_objects,
    usage_dict,
    write_jsonl,
)


LANGUAGE_SPECS = {
    "en": {"name": "English", "yes": "Yes", "no": "No"},
    "zh": {"name": "Chinese", "yes": "是", "no": "否"},
    "ms": {"name": "Malay", "yes": "Ya", "no": "Tidak"},
    "th": {"name": "Thai", "yes": "ใช่", "no": "ไม่ใช่"},
    "fa": {"name": "Persian", "yes": "بله", "no": "خیر"},
}


def build_step1_prompt(language_name: str) -> str:
    return (
        "You are an ICU physician. Examine the monitoring figure carefully and communicate in "
        f"{language_name}. "
        "Extract key patient information, vital-sign ranges, and major time-series trends. "
        "Return valid JSON with keys: patient_info, vital_signs, time_series_trends."
    )


def build_step2_prompt(language_name: str, yes_word: str, no_word: str, step1_json: str) -> str:
    return (
        "Based on the extracted monitoring information below, answer whether the patient would require "
        f"re-intubation within 6 hours if extubated now. Communicate in {language_name}. "
        "Return valid JSON with keys: analysis and conclusion. "
        f"The conclusion must be exactly '{yes_word}' or '{no_word}'.\n\n"
        f"Extracted information:\n{step1_json}"
    )


def build_case_rows(args) -> List[Dict[str, Any]]:
    if args.case_jsonl:
        rows = []
        for row in read_json_objects(Path(args.case_jsonl)):
            if isinstance(row, dict):
                rows.append(row)
        return rows
    if not args.image:
        raise ValueError("Provide --image for a single case or --case-jsonl for multiple cases.")
    return [{"patient_id": args.patient_id, "image_path": args.image}]


def main() -> None:
    parser = argparse.ArgumentParser(description="Simplified two-step MIMIC-III extubation answering.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--case-jsonl", default=None)
    parser.add_argument("--image", default=None)
    parser.add_argument("--patient-id", default="case_0")
    parser.add_argument("--language", choices=sorted(LANGUAGE_SPECS), default="en")
    parser.add_argument("--model", default="openai/gpt-4o")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    spec = LANGUAGE_SPECS[args.language]
    client = get_client(api_key=args.api_key, base_url=args.base_url)
    rows = build_case_rows(args)
    if args.limit is not None:
        rows = rows[: args.limit]

    outputs: List[Dict[str, Any]] = []
    for row in rows:
        image_path = Path(str(row["image_path"]))
        image_url = encode_image_as_data_url(image_path)

        step1_response = client.chat.completions.create(
            model=args.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": build_step1_prompt(spec["name"])},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the monitoring information into JSON."},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
        )
        step1_text = extract_text_response(step1_response)
        step1_parsed = parse_json_object(step1_text)

        step2_response = client.chat.completions.create(
            model=args.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": f"You are an ICU physician. Communicate in {spec['name']}."},
                {
                    "role": "user",
                    "content": build_step2_prompt(
                        spec["name"],
                        spec["yes"],
                        spec["no"],
                        json.dumps(step1_parsed or step1_text, ensure_ascii=False),
                    ),
                },
            ],
        )
        step2_text = extract_text_response(step2_response)
        step2_parsed = parse_json_object(step2_text)

        usage_1 = usage_dict(step1_response)
        usage_2 = usage_dict(step2_response)
        outputs.append(
            {
                "patient_id": row.get("patient_id"),
                "image_path": str(image_path),
                "language": args.language,
                "step1_response": step1_text,
                "step1_parsed": step1_parsed,
                "step2_response": step2_text,
                "step2_parsed": step2_parsed,
                "conclusion": step2_parsed.get("conclusion"),
                "usage": {
                    "input_tokens": usage_1["input_tokens"] + usage_2["input_tokens"],
                    "output_tokens": usage_1["output_tokens"] + usage_2["output_tokens"],
                    "total_tokens": usage_1["total_tokens"] + usage_2["total_tokens"],
                },
            }
        )

    write_jsonl(Path(args.output), outputs)


if __name__ == "__main__":
    main()
