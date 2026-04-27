from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from openai import OpenAI


def sanitize_model_name(model: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", model).strip("_")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json_objects(path: Path) -> List[Any]:
    text = path.read_text(encoding="utf-8")
    stripped = text.strip()
    if not stripped:
        return []

    try:
        obj = json.loads(stripped)
        if isinstance(obj, list):
            return obj
        return [obj]
    except json.JSONDecodeError:
        pass

    rows: List[Any] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows = []
                break
    if rows:
        return rows

    decoder = json.JSONDecoder()
    idx = 0
    rows = []
    while idx < len(text):
        while idx < len(text) and text[idx].isspace():
            idx += 1
        if idx >= len(text):
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
            rows.append(obj)
            idx = end
        except json.JSONDecodeError:
            idx += 1
    return rows


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def get_client(api_key: Optional[str] = None, base_url: Optional[str] = None) -> OpenAI:
    resolved_key = (api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not resolved_key:
        raise ValueError("Missing API key. Set OPENAI_API_KEY or OPENROUTER_API_KEY.")
    resolved_base = (base_url or os.getenv("BASE_URL") or "https://api.openai.com/v1").strip()
    return OpenAI(api_key=resolved_key, base_url=resolved_base)


def extract_text_response(response: Any) -> str:
    choice = response.choices[0]
    content = getattr(choice.message, "content", "")
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(part for part in parts if part).strip()
    return str(content or "").strip()


def usage_dict(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    if isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
    input_tokens = int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens))
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def parse_json_object(text: str) -> Dict[str, Any]:
    candidate = (text or "").strip()
    if not candidate:
        return {}
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z0-9_-]*\n?", "", candidate)
        candidate = re.sub(r"\n?```$", "", candidate)
        candidate = candidate.strip()
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        snippet = candidate[start : end + 1]
        try:
            parsed = json.loads(snippet)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def pick_identifier(row: Dict[str, Any]) -> str:
    for key in ("prompt_id", "patient_id", "id", "source_index"):
        if key in row and row.get(key) not in (None, ""):
            return f"{key}:{row[key]}"
    return "row"


def encode_image_as_data_url(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    raw = image_path.read_bytes()
    b64 = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def normalized_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()
