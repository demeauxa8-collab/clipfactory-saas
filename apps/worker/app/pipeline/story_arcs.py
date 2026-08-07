from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from typing import Any

import structlog

from ..models import ArcSegmentSpec, StoryArc, Transcript, VideoMap
from ..prompts import STORY_ARC_SYSTEM_PROMPT, story_arc_user_prompt
from ..providers import LLMProvider, ProviderError
from .boundaries import (
    MAX_CLIP_SECONDS,
    MAX_SEGMENT_SECONDS,
    MIN_CLIP_SECONDS,
    MIN_SEGMENT_SECONDS,
    PADDING_SECONDS,
    PhraseIndex,
    build_phrase_index,
    next_phrase_end_after,
)

log = structlog.get_logger()

# Montage-v2 bounds. A segment is a window of the source; an arc is 1-3 of them.
# The numbers themselves live in boundaries.py (single source of truth, shared
# with the snapper); these aliases keep the vocabulary of this module.
MIN_ARC_SECONDS = MIN_CLIP_SECONDS
MAX_ARC_SECONDS = MAX_CLIP_SECONDS
MAX_SEGMENTS_PER_ARC = 3

__all__ = [
    "MAX_ARC_SECONDS",
    "MAX_SEGMENTS_PER_ARC",
    "MAX_SEGMENT_SECONDS",
    "MIN_ARC_SECONDS",
    "MIN_SEGMENT_SECONDS",
    "select_story_arcs",
]


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


def _video_map_duration(video_map: VideoMap) -> int | None:
    """Best-effort source duration, read off the last mapped event."""
    ends = [e.end for e in video_map.events if e.end > 0]
    return round(max(ends)) if ends else None


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
    """Free-text field from the LLM: absent / null / non-scalar / blank -> None."""
    if v is None or isinstance(v, (dict, list, bool)):
        return None
    text = str(v).strip()
    return text[:max_len] if text else None


def _coerce_bool(v: Any, default: bool = True) -> bool:
    """Tolerant bool: real bools, "true"/"false"/"yes"/"no"/"0"/"1", else default."""
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "yes", "y", "1", "oui"}:
            return True
        if s in {"false", "no", "n", "0", "non"}:
            return False
    return default


def _extend_to_duration_floor(
    segments: list[ArcSegmentSpec],
    index: PhraseIndex,
    *,
    min_total: float = MIN_ARC_SECONDS,
    max_segment_seconds: float = MAX_SEGMENT_SECONDS,
    max_total: float = MAX_ARC_SECONDS,
    padding: float = PADDING_SECONDS,
    max_steps: int = 12,
) -> list[ArcSegmentSpec] | None:
    """Grow the last segment, one sentence at a time, until the arc clears the floor.

    An arc below the floor is a repair job, not a verdict: the model found a real
    moment (a 8.6s cold open scored 95 on campaign fit) and merely stopped
    quoting too early. We push its end to the next sentence end — never mid-
    thought — and only give up when the caps make it impossible. Returns the
    repaired segments, or None if the floor is out of reach.
    """
    if not segments or not index.phrases:
        return None
    out = list(segments)
    last = out[-1]
    end = last.end
    total = sum(s.end - s.start for s in out)

    for _ in range(max_steps):
        if total >= min_total - 1e-6:
            out[-1] = replace(last, end=end)
            return out
        next_end = next_phrase_end_after(index, end)
        if next_end is None:
            return None
        candidate = next_end + padding
        if candidate - last.start > max_segment_seconds:
            return None
        if total + (candidate - end) > max_total:
            return None
        total += candidate - end
        end = candidate

    return None


def _parse_arcs(payload: Any, *, transcript: Transcript | None = None) -> list[StoryArc]:
    """Parse the selection response into StoryArc objects.

    When a ``transcript`` is supplied, an arc that falls short of the duration
    floor is repaired (its end extended to the next sentence end) instead of
    being dropped. Every discarded arc is counted by reason and logged once at
    the end — a silent drop here used to look like "the model returned nothing
    useful".
    """
    if isinstance(payload, dict):
        arcs_raw = payload.get("arcs") or []
        video_read = _coerce_text(payload.get("video_read"), max_len=1200)
    elif isinstance(payload, list):
        arcs_raw = payload
        video_read = None
    else:
        log.warning("story_arcs.unusable_payload", payload_type=type(payload).__name__)
        return []

    if video_read:
        # The model's own reading of the video: the single most useful line in the
        # logs when clips come out flat.
        log.info("story_arcs.video_read", text=video_read[:600])

    index = (
        build_phrase_index(transcript.words, transcript.sentences)
        if transcript is not None
        else None
    )
    rejected: Counter[str] = Counter()
    repaired_count = 0
    arcs: list[StoryArc] = []
    for raw in arcs_raw:
        if not isinstance(raw, dict):
            rejected["not_an_object"] += 1
            continue
        seg_raw = raw.get("segments") or []
        if not isinstance(seg_raw, list) or not seg_raw:
            rejected["no_segments"] += 1
            continue
        segments: list[ArcSegmentSpec] = []
        for s in seg_raw:
            if not isinstance(s, dict):
                rejected["segment_not_an_object"] += 1
                continue
            # Models sometimes emit "start" only (or a duration instead of an
            # end): count that separately, it is a prompt bug rather than a
            # judgement call about length.
            if s.get("start") is None or s.get("end") is None:
                rejected["segment_missing_timestamps"] += 1
                continue
            start = _coerce_float(s.get("start"))
            end = _coerce_float(s.get("end"))
            # Montage-v2: each segment is 3-30s. A short segment is only valid
            # inside a multi-segment arc; the total-duration gate below still
            # enforces a minimum overall clip length.
            if end - start < MIN_SEGMENT_SECONDS or end - start > MAX_SEGMENT_SECONDS:
                rejected["segment_duration_out_of_bounds"] += 1
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
        if not segments:
            rejected["no_valid_segment"] += 1
            continue
        if len(segments) > MAX_SEGMENTS_PER_ARC:
            rejected["too_many_segments"] += 1
            continue
        total = sum(s.end - s.start for s in segments)
        if total > MAX_ARC_SECONDS:
            rejected["arc_too_long"] += 1
            continue
        if total < MIN_ARC_SECONDS:
            repaired = (
                _extend_to_duration_floor(segments, index) if index is not None else None
            )
            if repaired is None:
                rejected["arc_too_short_unrepairable"] += 1
                continue
            log.info(
                "story_arcs.repaired_short_arc",
                title=str(raw.get("title", ""))[:80],
                before=round(total, 2),
                after=round(sum(s.end - s.start for s in repaired), 2),
            )
            repaired_count += 1
            segments = repaired

        link_reason = _coerce_text(raw.get("link_reason"), max_len=280)
        # A multi-segment arc without a stated narrative link is downgraded (kept
        # but flagged) — the scorer will treat its joints as ordinary cuts.
        if len(segments) > 1 and not link_reason:
            log.warning(
                "story_arcs.multi_segment_missing_link_reason",
                title=str(raw.get("title", ""))[:80],
                n_segments=len(segments),
            )

        cf_raw = raw.get("campaign_fit")
        campaign_fit_llm = _coerce_int(cf_raw) if cf_raw is not None else None

        self_contained = _coerce_bool(raw.get("self_contained"), default=True)
        if not self_contained:
            # Kept on purpose: the model self-reports, and dropping here would hide
            # the signal. The scorer and the human reviewer see the flag instead.
            log.info(
                "story_arcs.not_self_contained",
                title=str(raw.get("title", ""))[:80],
            )

        arcs.append(
            StoryArc(
                title=str(raw.get("title", ""))[:120],
                arc_type=str(raw.get("arc_type", "continuous")),  # type: ignore[arg-type]
                segments=segments,
                viral_reason=str(raw.get("viral_reason", ""))[:280],
                estimated_retention=_coerce_int(raw.get("estimated_retention")),
                continuity_risk=str(raw.get("continuity_risk", "medium")),
                suggested_hook=_coerce_text(raw.get("suggested_hook"), max_len=120),
                link_reason=link_reason,
                campaign_fit_llm=campaign_fit_llm,
                campaign_fit_reason=_coerce_text(
                    raw.get("campaign_fit_reason"), max_len=280
                ),
                opening_words=_coerce_text(raw.get("opening_words"), max_len=200),
                self_contained=self_contained,
                payoff_line=_coerce_text(raw.get("payoff_line"), max_len=300),
            )
        )

    if rejected:
        log.warning(
            "story_arcs.rejected",
            total=sum(rejected.values()),
            kept=len(arcs),
            repaired=repaired_count,
            reasons=dict(rejected),
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
    duration_seconds: int | None = None,
    language: str | None = None,
    transcript: Transcript | None = None,
) -> tuple[list[StoryArc], int]:
    """Returns (story_arcs, tokens_used).

    Pass ``transcript`` to enable the repair pass: an arc that lands under the
    duration floor is extended to the next sentence end instead of being thrown
    away.
    """
    user = story_arc_user_prompt(
        transcript_lines=transcript_lines,
        video_map_json=_video_map_to_json(video_map),
        campaign=campaign,
        target_clip_count=target_clip_count,
        duration_seconds=duration_seconds or _video_map_duration(video_map),
        video_summary=video_map.summary,
        language=language,
    )
    result = await provider.chat_json(
        model=model,
        system=STORY_ARC_SYSTEM_PROMPT,
        user=user,
        max_tokens=8192,
        temperature=0.3,
    )
    arcs = _parse_arcs(result.payload, transcript=transcript)
    if not arcs:
        raise ProviderError("no usable arcs in response", kind="empty")
    log.info(
        "story_arcs.parsed",
        n=len(arcs),
        multi=sum(1 for a in arcs if len(a.segments) > 1),
        tokens=result.tokens_total,
    )
    return arcs, result.tokens_total
