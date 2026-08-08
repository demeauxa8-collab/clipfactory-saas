"""Simple segment selection for short videos (< story pipeline threshold).

For long videos, the story arc path is used instead (see story_arcs.py).
"""

from __future__ import annotations

from typing import Any

import structlog

from ..models import ArcSegmentSpec, StoryArc
from ..prompts import SIMPLE_SEGMENTS_SYSTEM_PROMPT, simple_segments_user_prompt
from ..providers import LLMProvider, ProviderError

log = structlog.get_logger()

MIN_SIMPLE_SEGMENT_SECONDS = 20.0
MAX_SIMPLE_SEGMENT_SECONDS = 60.0


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


def _coerce_text(v: Any, *, max_len: int) -> str | None:
    if v is None or isinstance(v, (dict, list, bool)):
        return None
    text = str(v).strip()
    return text[:max_len] if text else None


def _parse_segments_as_arcs(payload: Any) -> list[StoryArc]:
    """Adapt simple segment responses into single-segment StoryArc objects so the
    downstream pipeline (verify, score, render) only deals with one shape."""
    if isinstance(payload, dict):
        items = payload.get("segments") or payload.get("items") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    arcs: list[StoryArc] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        start = _coerce_float(raw.get("start"))
        end = _coerce_float(raw.get("end"))
        if end - start < MIN_SIMPLE_SEGMENT_SECONDS or end - start > MAX_SIMPLE_SEGMENT_SECONDS:
            continue
        hook_score = _coerce_int(raw.get("hook_score_text"))
        emotion = _coerce_int(raw.get("emotion_score"))
        arcs.append(
            StoryArc(
                title=str(raw.get("title", ""))[:120],
                arc_type="continuous",
                segments=[
                    ArcSegmentSpec(
                        role="single",
                        start=start,
                        end=end,
                        transcript_excerpt=str(raw.get("transcript_excerpt", ""))[:300],
                        why=str(raw.get("why", ""))[:280] or None,
                        start_anchor=_coerce_text(raw.get("start_anchor"), max_len=180),
                        end_anchor=_coerce_text(raw.get("end_anchor"), max_len=180),
                    )
                ],
                viral_reason=str(raw.get("why", ""))[:280],
                estimated_retention=max(hook_score, emotion),
                continuity_risk="low",
                suggested_hook=(
                    str(raw.get("suggested_hook"))[:120] if raw.get("suggested_hook") else None
                ),
                opening_words=_coerce_text(raw.get("start_anchor"), max_len=180),
            )
        )
    return arcs


async def select_simple_segments(
    *,
    provider: LLMProvider,
    model: str,
    transcript_lines: str,
    campaign: dict[str, Any],
    target_clip_count: int,
) -> tuple[list[StoryArc], int]:
    """Returns (single-segment story arcs, tokens_used). Used for short videos."""
    user = simple_segments_user_prompt(
        transcript_lines=transcript_lines,
        campaign=campaign,
        target_clip_count=target_clip_count,
    )
    result = await provider.chat_json(
        model=model,
        system=SIMPLE_SEGMENTS_SYSTEM_PROMPT,
        user=user,
        max_tokens=3072,
        temperature=0.3,
    )
    arcs = _parse_segments_as_arcs(result.payload)
    if not arcs:
        raise ProviderError("no usable segments in response", kind="empty")
    log.info("analyze.simple_segments", n=len(arcs), tokens=result.tokens_total)
    return arcs, result.tokens_total
