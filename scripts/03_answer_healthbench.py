#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any, Dict, List

from common import extract_text_response, get_client, read_json_objects, usage_dict, write_jsonl


def build_messages(row: Dict[str, Any]) -> List[Dict[str, str]]:
    if isinstance(row.get("translation"), list):
        return [
            {"role": str(message.get("role", "user")), "content": str(message.get("content", ""))}
            for message in row["translation"]
            if isinstance(message, dict)
        ]
    if isinstance(row.get("back_translation"), list):
        return [
            {"role": str(message.get("role", "user")), "content": str(message.get("content", ""))}
            for message in row["back_translation"]
            if isinstance(message, dict)
        ]
    if isinstance(row.get("prompt"), list):
        return [
            {"role": str(message.get("role", "user")), "content": str(message.get("content", ""))}
            for message in row["prompt"]
            if isinstance(message, dict)
        ]
    raise ValueError("Row does not contain prompt, translation, or back_translation messages.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reviewer-friendly HealthBench answers.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="openai/gpt-4o")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--language-label", default="EN", help="Display label such as EN or ZH.")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    client = get_client(api_key=args.api_key, base_url=args.base_url)
    rows = read_json_objects(Path(args.input))
    if args.limit is not None:
        rows = rows[: args.limit]

    outputs: List[Dict[str, Any]] = []
    for round_id in range(1, args.rounds + 1):
        for row in rows:
            if not isinstance(row, dict):
                continue
            messages = build_messages(row)
            t0 = time.perf_counter()
            error = None
            response_text = ""
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            try:
                response = client.chat.completions.create(
                    model=args.model,
                    messages=messages,
                    temperature=args.temperature,
                )
                response_text = extract_text_response(response)
                usage = usage_dict(response)
            except Exception as exc:
                error = str(exc)
            elapsed = round(time.perf_counter() - t0, 3)
            outputs.append(
                {
                    "prompt_id": row.get("prompt_id"),
                    "language": args.language_label,
                    "round": round_id,
                    "response": response_text,
                    "error": error,
                    "original_input": messages,
                    **usage,
                    "response_time_sec": elapsed,
                }
            )

    write_jsonl(Path(args.output), outputs)


if __name__ == "__main__":
    main()
