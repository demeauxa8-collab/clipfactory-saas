"""Deep vision on top arcs only.

Note: cheap global vision lives in `video_map.py`. This module is reserved for
the high-cost confirmation pass run on the top N arcs after scoring.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from ..models import ArcSegmentSpec, SegmentVision, StoryArc, VisionResult
from ..prompts import DEEP_VISION_SYSTEM_PROMPT, deep_vision_user_prompt
from ..providers import LLMProvider, ProviderError
from ..providers.base import ImageInput
from .ffmpeg import FFmpegError, extract_frame

log = structlog.get_logger()


def _coerce_int(v: Any, default: int = 0) -> int:
    try:
        return max(0, min(100, round(float(v))))
    except Exception:
        return default


def _parse_vision(payload: Any) -> VisionResult | None:
    if not isinstance(payload, dict):
        return None
    return VisionResult(
        decor=str(payload.get("decor", "unknown")),
        person_visible=bool(payload.get("person_visible", False)),
        energy=_coerce_int(payload.get("energy")),
        action=str(payload.get("action", "other")),
        proof_objects=[str(x) for x in (payload.get("proof_objects") or []) if x],
        problems=[str(x) for x in (payload.get("problems") or []) if x],
        visual_score=_coerce_int(payload.get("visual_score")),
    )


def _frame_timestamps_for_segment(segment: ArcSegmentSpec) -> list[float]:
    """Up to 6 frames per segment: start, q1, mid, q3, end. Caps depending on
    segment duration."""
    duration = max(0.0, segment.end - segment.start)
    if duration < 6:
        return [segment.start + 0.2, max(segment.start + 0.2, segment.end - 0.2)]
    return [
        segment.start + 0.2,
        segment.start + duration * 0.25,
        segment.start + duration * 0.5,
        segment.start + duration * 0.75,
        max(segment.start + 0.2, segment.end - 0.2),
    ]


async def _extract_segment_frames(
    *, source_path: str, segment: ArcSegmentSpec, workdir: str, prefix: str
) -> list[str]:
    paths: list[str] = []
    for k, ts in enumerate(_frame_timestamps_for_segment(segment)):
        out = os.path.join(workdir, f"{prefix}_f{k}.jpg")
        try:
            await extract_frame(source_path, ts, out)
            paths.append(out)
        except FFmpegError:
            continue
    return paths


def _load_images(paths: list[str]) -> list[ImageInput]:
    images: list[ImageInput] = []
    for p in paths:
        try:
            with open(p, "rb") as fh:
                images.append(ImageInput(bytes_jpeg=fh.read()))
        except FileNotFoundError:
            continue
    return images


async def deep_vision_for_arc(
    *,
    provider: LLMProvider,
    model: str,
    source_path: str,
    arc: StoryArc,
    workdir: str,
    arc_idx: int,
) -> tuple[list[SegmentVision], int, int]:
    """Run deep vision on each segment of an arc.

    Returns (per_segment_vision, total_frames_used, total_tokens_used).
    """
    segment_results: list[SegmentVision] = []
    total_frames = 0
    total_tokens = 0
    for s_idx, segment in enumerate(arc.segments):
        prefix = f"arc{arc_idx:02d}_seg{s_idx:02d}"
        frame_paths = await _extract_segment_frames(
            source_path=source_path, segment=segment, workdir=workdir, prefix=prefix
        )
        images = _load_images(frame_paths)
        if not images:
            segment_results.append(
                SegmentVision(segment_idx=s_idx, frames_used=0, vision=None, tokens_used=0)
            )
            continue

        context = (
            f"role={segment.role}, source_seconds=[{segment.start:.1f}, {segment.end:.1f}], "
            f"excerpt: {segment.transcript_excerpt[:200]}"
        )
        try:
            result = await provider.vision_json(
                model=model,
                system=DEEP_VISION_SYSTEM_PROMPT,
                user_text=deep_vision_user_prompt(segment_context=context),
                images=images,
                max_tokens=512,
                temperature=0.2,
            )
        except ProviderError as exc:
            log.warning(
                "deep_vision.segment_failed",
                arc_idx=arc_idx,
                seg_idx=s_idx,
                err=str(exc),
            )
            segment_results.append(
                SegmentVision(segment_idx=s_idx, frames_used=len(images), vision=None)
            )
            total_frames += len(images)
            continue

        vision = _parse_vision(result.payload)
        segment_results.append(
            SegmentVision(
                segment_idx=s_idx,
                frames_used=len(images),
                vision=vision,
                tokens_used=result.tokens_total,
            )
        )
        total_frames += len(images)
        total_tokens += result.tokens_total

    return segment_results, total_frames, total_tokens


def aggregate_visual_score(per_segment: list[SegmentVision]) -> int | None:
    """Return the average visual_score across segments, or None if no vision."""
    scores = [sv.vision.visual_score for sv in per_segment if sv.vision is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores))


def aggregate_visual_summary(per_segment: list[SegmentVision]) -> str | None:
    parts: list[str] = []
    for sv in per_segment:
        if sv.vision is None:
            continue
        v = sv.vision
        parts.append(
            f"seg{sv.segment_idx + 1}: {v.decor}/{v.action}, "
            f"energy={v.energy}, score={v.visual_score}"
        )
    return "; ".join(parts) if parts else None
