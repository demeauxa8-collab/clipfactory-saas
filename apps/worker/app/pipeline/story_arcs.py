from __future__ import annotations

import json
from typing import Any

import structlog

from ..models import ArcSegmentSpec, StoryArc, VideoMap
from ..prompts import STORY_ARC_SYSTEM_PROMPT, story_arc_user_prompt
from ..providers import LLMProvider, ProviderError

log = structlog.get_logger()


def _video_map_to_json(video_map: VideoMap) -> str:
    return json.dumps(
        {
            "summary": video_map.summary,
            "events": [
                {
                    "id": e.id,
                    "start": round(e.start, 2),
                    "end": round(e.end, 2),
                    "decor": e.decor,
                    "people": e.people,
                    "objects": e.objects[:5],
                    "action": e.action,
                    "transcript_summary": e.transcript_summary,
                    "visual_importance": e.visual_importance,
                    "narrative_role": e.narrative_role,
                }
                for e in video_map.events
            ],
        },
        ensure_ascii=False,
    )


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


def _parse_arcs(payload: Any) -> list[StoryArc]:
    if isinstance(payload, dict):
        arcs_raw = payload.get("arcs") or []
    elif isinstance(payload, list):
        arcs_raw = payload
    else:
        return []

    arcs: list[StoryArc] = []
    for raw in arcs_raw:
        if not isinstance(raw, dict):
            continue
        seg_raw = raw.get("segments") or []
        if not isinstance(seg_raw, list) or not seg_raw:
            continue
        segments: list[ArcSegmentSpec] = []
        for s in seg_raw:
            if not isinstance(s, dict):
                continue
            start = _coerce_float(s.get("start"))
            end = _coerce_float(s.get("end"))
            if end - start < 3 or end - start > 30:
                continue
            segments.append(
                ArcSegmentSpec(
                    role=str(s.get("role", "single")),  # type: ignore[arg-type]
                    start=start,
                    end=end,
                    transcript_excerpt=str(s.get("transcript_excerpt", ""))[:300],
                    why=str(s.get("why", ""))[:280] or None,
                )
            )
        if not segments or len(segments) > 3:
            continue
        total = sum(s.end - s.start for s in segments)
        if total < 15 or total > 70:
            continue
        arcs.append(
            StoryArc(
                title=str(raw.get("title", ""))[:120],
                arc_type=str(raw.get("arc_type", "continuous")),  # type: ignore[arg-type]
                segments=segments,
                viral_reason=str(raw.get("viral_reason", ""))[:280],
                estimated_retention=_coerce_int(raw.get("estimated_retention")),
                continuity_risk=str(raw.get("continuity_risk", "medium")),
                suggested_hook=(
                    str(raw.get("suggested_hook"))[:120] if raw.get("suggested_hook") else None
                ),
            )
        )
    return arcs


async def select_story_arcs(
    *,
    provider: LLMProvider,
    model: str,
    transcript_lines: str,
    video_map: VideoMap,
    campaign: dict[str, Any],
    target_clip_count: int,
) -> tuple[list[StoryArc], int]:
    """Returns (story_arcs, tokens_used)."""
    user = story_arc_user_prompt(
        transcript_lines=transcript_lines,
        video_map_json=_video_map_to_json(video_map),
        campaign=campaign,
        target_clip_count=target_clip_count,
    )
    result = await provider.chat_json(
        model=model,
        system=STORY_ARC_SYSTEM_PROMPT,
        user=user,
        max_tokens=4096,
        temperature=0.3,
    )
    arcs = _parse_arcs(result.payload)
    if not arcs:
        raise ProviderError("no usable arcs in response", kind="empty")
    log.info("story_arcs.parsed", n=len(arcs), tokens=result.tokens_total)
    return arcs, result.tokens_total
