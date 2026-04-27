#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Dict, List

from common import extract_text_response, get_client, pick_identifier, read_json_objects, usage_dict, write_jsonl


def back_translate_text(client, model: str, text: str, source_language: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=model,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional medical back-translator. "
                    "Translate faithfully into English. "
                    "Preserve meaning, uncertainty, formatting, and tone. "
                    "Do not explain the translation."
                ),
            },
            {
                "role": "user",
                "content": f"Source language: {source_language}\n\nText:\n{text}",
            },
        ],
    )
    return {
        "text": extract_text_response(response),
        "usage": usage_dict(response),
    }


def back_translate_messages(client, model: str, messages: List[Dict[str, Any]], source_language: str) -> Dict[str, Any]:
    translated: List[Dict[str, Any]] = []
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for message in messages:
        result = back_translate_text(client, model, str(message.get("content", "")), source_language)
        translated.append({"role": message.get("role", "user"), "content": result["text"]})
        for key, value in result["usage"].items():
            total[key] += value
    return {"messages": translated, "usage": total}


def back_translate_turns(
    client,
    model: str,
    turns: List[Dict[str, Any]],
    source_language: str,
    text_key: str,
) -> Dict[str, Any]:
    translated: List[Dict[str, Any]] = []
    total = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for turn in turns:
        out = copy.deepcopy(turn)
        result = back_translate_text(client, model, str(turn.get(text_key, "")), source_language)
        out[text_key] = result["text"]
        translated.append(out)
        for key, value in result["usage"].items():
            total[key] += value
    return {"turns": translated, "usage": total}


def main() -> None:
    parser = argparse.ArgumentParser(description="Reviewer-friendly back-translation script.")
    parser.add_argument("--input", required=True, help="Input JSON/JSONL file.")
    parser.add_argument("--output", required=True, help="Output JSONL file.")
    parser.add_argument("--field", required=True, help="Field to back-translate.")
    parser.add_argument("--field-type", choices=["text", "messages", "turns"], required=True)
    parser.add_argument("--source-language", required=True, help="Language name, e.g. Chinese.")
    parser.add_argument("--text-key", default="text", help="Text key for --field-type turns.")
    parser.add_argument(
        "--output-field",
        default="back_translation",
        help="Field name to store the back-translated content. Use the source field name to mimic production layouts.",
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
            result = back_translate_text(client, args.model, str(source or ""), args.source_language)
            out[args.output_field] = result["text"]
            usage = result["usage"]
        elif args.field_type == "messages":
            result = back_translate_messages(client, args.model, list(source or []), args.source_language)
            out[args.output_field] = result["messages"]
            usage = result["usage"]
        else:
            result = back_translate_turns(client, args.model, list(source or []), args.source_language, args.text_key)
            out[args.output_field] = result["turns"]
            usage = result["usage"]

        out["back_translation_meta"] = {
            "source_language": args.source_language,
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
