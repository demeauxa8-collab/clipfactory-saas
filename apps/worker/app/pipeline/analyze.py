from __future__ import annotations

import json
import re
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from ..models import TextCandidate
from ..prompts import CANDIDATE_SYSTEM_PROMPT, candidate_user_prompt
from ..settings import get_settings

log = structlog.get_logger()


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, round(float(v))))
    except Exception:
        return default


def _coerce_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _extract_json_array(text: str) -> list[Any]:
    text = text.strip()
    # Strip optional ```json fences
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []


async def select_text_candidates(
    *,
    transcript_lines: str,
    campaign: dict[str, Any],
    target_clip_count: int,
) -> tuple[list[TextCandidate], int]:
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    user_prompt = candidate_user_prompt(
        transcript_text=transcript_lines,
        campaign=campaign,
        target_clip_count=target_clip_count,
    )

    msg = await client.messages.create(
        model=settings.anthropic_text_model,
        max_tokens=4096,
        system=CANDIDATE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    tokens_used = (msg.usage.input_tokens or 0) + (msg.usage.output_tokens or 0)
    items = _extract_json_array(raw)

    candidates: list[TextCandidate] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        start = _coerce_float(it.get("start"))
        end = _coerce_float(it.get("end"))
        if end - start < 5 or end - start > 90:
            continue
        candidates.append(
            TextCandidate(
                start=start,
                end=end,
                hook_score_text=_coerce_int(it.get("hook_score_text")),
                emotion_score=_coerce_int(it.get("emotion_score")),
                transcript_excerpt=str(it.get("transcript_excerpt", ""))[:280],
                why=str(it.get("why", ""))[:280],
                suggested_title=(
                    str(it.get("suggested_title")) if it.get("suggested_title") else None
                ),
                suggested_hook=(
                    str(it.get("suggested_hook")) if it.get("suggested_hook") else None
                ),
            )
        )

    log.info("analyze.candidates", n=len(candidates), tokens=tokens_used)
    return candidates, int(tokens_used)
