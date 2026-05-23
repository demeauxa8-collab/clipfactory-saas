from __future__ import annotations

import hashlib
import re
from typing import Any

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _hash_email(value: str) -> str:
    digest = hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:16]
    return f"email_sha256:{digest}"


def _scrub(value: Any) -> Any:
    if isinstance(value, str):
        return EMAIL_RE.sub(lambda match: _hash_email(match.group(0)), value)
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub(item) for item in value)
    return value


def scrub_email_values(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    return {key: _scrub(value) for key, value in event_dict.items()}
