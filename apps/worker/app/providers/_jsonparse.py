"""Shared JSON extraction helpers — used by every provider to coerce a possibly
fenced / preambled LLM response into a clean JSON object/array.
"""

from __future__ import annotations

import json
import re
from typing import Any

_FENCE_OPEN = re.compile(r"^```(?:json|JSON)?\s*", re.MULTILINE)
_FENCE_CLOSE = re.compile(r"```\s*$", re.MULTILINE)


def extract_json(text: str) -> Any:
    """Best-effort JSON extraction from an LLM response.

    Strategy:
      1. Strip leading/trailing code fences.
      2. Try direct json.loads on the stripped text.
      3. Fall back to slicing from first `{` or `[` to the matching last `}`/`]`.

    Raises ValueError when nothing parseable is found.
    """
    if not text or not text.strip():
        raise ValueError("empty response")

    cleaned = _FENCE_OPEN.sub("", text.strip()).strip()
    cleaned = _FENCE_CLOSE.sub("", cleaned).strip()

    # Fast path
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Slow path: bracket slice
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = cleaned.find(open_ch)
        end = cleaned.rfind(close_ch)
        if start != -1 and end != -1 and end > start:
            candidate = cleaned[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError("no parseable JSON in response")
