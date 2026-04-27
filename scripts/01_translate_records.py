#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Dict, List

from common import extract_text_response, get_client, pick_identifier, read_json_objects, usage_dict, write_jsonl


def translate_text(client, model: str, text: str, target_language: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional medical translator. "
                    "Translate faithfully into the target language. "
                    "Preserve meaning, uncertainty, tone, and structure. "
                    "Do not explain the translation."
                ),
            },
            {
                "role": "user",
                "content": f"Target language: {target_language}\n\nText:\n{text}",
            },
        ],
    )
    return {
        "text": extract_text_response(response),
        "usage": usage_dict(response),
    }


def translate_messages(client, model: str, messages: List[Dict[str, Any]], target_language: str) -> Dict[str, Any]:
    translated: List[Dict[str, Any]] = []
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for message in messages:
        content = str(message.get("content", ""))
        result = translate_text(client, model, content, target_language)
        translated.append({"role": message.get("role", "user"), "content": result["text"]})
        for key, value in result["usage"].items():
            total[key] += value
    return {"messages": translated, "usage": total}


def translate_turns(
    client,
    model: str,
    turns: List[Dict[str, Any]],
    target_language: str,
    text_key: str,
) -> Dict[str, Any]:
    translated: List[Dict[str, Any]] = []
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for turn in turns:
        out = copy.deepcopy(turn)
        result = translate_text(client, model, str(turn.get(text_key, "")), target_language)
        out[text_key] = result["text"]
        translated.append(out)
        for key, value in result["usage"].items():
            total[key] += value
    return {"turns": translated, "usage": total}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reviewer-friendly forward translation script.")
    parser.add_argument("--input", required=True, help="Input JSON/JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSONL file.")
    parser.add_argument("--field", required=True, help="Field to translate.")
    parser.add_argument("--field-type", choices=["text", "messages", "turns"], required=True)
    parser.add_argument("--target-language", required=True, help="Language name, e.g. Chinese.")
    parser.add_argument("--text-key", default="text", help="Text key for --field-type turns.")
    parser.add_argument(
        "--output-field",
        default="translation",
        help="Field name to store the translated content. Use the source field name to mimic production layouts.",
    )
    parser.add_argument("--model", default="openai/gpt-4o-mini")
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
        out = copy.deepcopy(row)
        source = row.get(args.field)
        if args.field_type == "text":
            result = translate_text(client, args.model, str(source or ""), args.target_language)
            out[args.output_field] = result["text"]
            usage = result["usage"]
        elif args.field_type == "messages":
            result = translate_messages(client, args.model, list(source or []), args.target_language)
            out[args.output_field] = result["messages"]
            usage = result["usage"]
        else:
            result = translate_turns(client, args.model, list(source or []), args.target_language, args.text_key)
            out[args.output_field] = result["turns"]
            usage = result["usage"]

        out["translation_meta"] = {
            "target_language": args.target_language,
            "source_field": args.field,
            "output_field": args.output_field,
            "source_row": pick_identifier(row),
            "model": args.model,
            **usage,
        }
        outputs.append(out)

    write_jsonl(Path(args.output), outputs)


if __name__ == "__main__":
    main()
