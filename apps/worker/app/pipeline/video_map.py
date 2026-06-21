from __future__ import annotations

import os
from pathlib import Path

import structlog

from ..models import Transcript, VideoEvent, VideoMap
from ..prompts import VIDEO_MAP_SYSTEM_PROMPT, video_map_user_prompt
from ..providers import LLMProvider, ProviderError
from ..providers.base import ImageInput
from .ffmpeg import FFmpegError, detect_scene_changes, extract_frame

log = structlog.get_logger()


# Sampling cap per duration band (in seconds)
_SAMPLING_BANDS = [
    (600, 80, 6),          # < 10 min : max 80 frames, base every 6s
    (1800, 150, 10),       # 10-30 min : max 150 frames, base every 10s
    (3600, 220, 15),       # 30-60 min : max 220 frames, base every 15s
    (10_000_000, 220, 20), # > 1h : same cap, sparser sampling
]


def _band_for_duration(duration_seconds: int) -> tuple[int, int]:
    for upper, max_frames, base_step in _SAMPLING_BANDS:
        if duration_seconds <= upper:
            return max_frames, base_step
    return _SAMPLING_BANDS[-1][1], _SAMPLING_BANDS[-1][2]


def _build_timeline(
    *,
    duration_seconds: int,
    scene_changes: list[float],
    max_frames: int,
    base_step: int,
) -> list[float]:
    """Merge a regular grid + scene-change timestamps, dedupe, cap at max_frames."""
    grid = [
        float(t)
        for t in range(int(base_step // 2), int(duration_seconds), int(base_step))
        if t < duration_seconds
    ]
    merged = sorted({round(t, 1) for t in grid + scene_changes})
    if len(merged) <= max_frames:
        return merged
    # Down-sample evenly
    step = len(merged) / max_frames
    return [merged[int(i * step)] for i in range(max_frames)]


def _compact_transcript(transcript: Transcript, max_chars: int = 4000) -> str:
    text = transcript.text.strip()
    if len(text) <= max_chars:
        return text
    # Keep beginning + ellipsis + end
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n...\n{tail}"


async def sample_frames(
    *,
    source_path: str,
    duration_seconds: int,
    workdir: str,
) -> list[tuple[float, str]]:
    """Detect scene changes, build sampling timeline, extract frames to disk.

    Returns a list of (timestamp_seconds, jpeg_path).
    """
    Path(workdir).mkdir(parents=True, exist_ok=True)
    max_frames, base_step = _band_for_duration(duration_seconds)
    try:
        scenes = await detect_scene_changes(source_path, threshold=0.4)
    except FFmpegError as exc:
        log.warning("video_map.scene_detection_failed", err=str(exc))
        scenes = []

    timeline = _build_timeline(
        duration_seconds=duration_seconds,
        scene_changes=scenes,
        max_frames=max_frames,
        base_step=base_step,
    )

    out: list[tuple[float, str]] = []
    for i, ts in enumerate(timeline):
        path = os.path.join(workdir, f"map_{i:03d}.jpg")
        try:
            await extract_frame(source_path, ts, path)
            out.append((ts, path))
        except FFmpegError as exc:
            log.warning("video_map.frame_failed", ts=ts, err=str(exc))
            continue
    log.info("video_map.frames_sampled", asked=len(timeline), got=len(out))
    return out


async def build_video_map(
    *,
    provider: LLMProvider,
    model: str,
    source_path: str,
    duration_seconds: int,
    transcript: Transcript,
    workdir: str,
    batch_size: int = 20,
) -> tuple[VideoMap, int, int]:
    """Run the cheap global vision pass over the whole video.

    Returns (video_map, frames_used, tokens_used).
    """
    frames = await sample_frames(
        source_path=source_path,
        duration_seconds=duration_seconds,
        workdir=workdir,
    )
    if not frames:
        raise ProviderError("no frames sampled", kind="empty")

    compact_transcript = _compact_transcript(transcript)

    # Single call if the batch fits; otherwise chunk and merge events.
    if len(frames) <= batch_size:
        return await _call_video_map(
            provider=provider,
            model=model,
            duration_seconds=duration_seconds,
            transcript_summary=compact_transcript,
            frames=frames,
        )

    # Chunked path: split timeline, call per chunk, then merge.
    all_events: list[VideoEvent] = []
    total_tokens = 0
    chunks = [frames[i : i + batch_size] for i in range(0, len(frames), batch_size)]
    summaries: list[str] = []
    for chunk in chunks:
        vm, _, tokens = await _call_video_map(
            provider=provider,
            model=model,
            duration_seconds=duration_seconds,
            transcript_summary=compact_transcript,
            frames=chunk,
        )
        all_events.extend(vm.events)
        total_tokens += tokens
        if vm.summary:
            summaries.append(vm.summary)

    # Re-id events and merge summaries
    merged_summary = " ".join(summaries)[:600]
    for idx, ev in enumerate(all_events):
        ev.id = f"evt_{idx + 1:03d}"

    return VideoMap(summary=merged_summary, events=all_events), len(frames), total_tokens


async def _call_video_map(
    *,
    provider: LLMProvider,
    model: str,
    duration_seconds: int,
    transcript_summary: str,
    frames: list[tuple[float, str]],
) -> tuple[VideoMap, int, int]:
    timestamps = [ts for ts, _ in frames]
    images: list[ImageInput] = []
    for ts, path in frames:
        try:
            with open(path, "rb") as fh:
                images.append(ImageInput(bytes_jpeg=fh.read(), label=f"{ts:.1f}s"))
        except FileNotFoundError:
            continue
    if not images:
        raise ProviderError("no readable frame files", kind="empty")

    user = video_map_user_prompt(
        duration_seconds=duration_seconds,
        transcript_summary=transcript_summary,
        frame_timestamps=timestamps,
    )

    result = await provider.vision_json(
        model=model,
        system=VIDEO_MAP_SYSTEM_PROMPT,
        user_text=user,
        images=images,
        max_tokens=4096,
        temperature=0.2,
    )
    payload = result.payload
    if not isinstance(payload, dict):
        raise ProviderError("video_map: payload not a dict", kind="parse")

    raw_events = payload.get("events") or []
    events: list[VideoEvent] = []
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        try:
            events.append(
                VideoEvent(
                    id=str(raw.get("id") or f"evt_{len(events) + 1:03d}"),
                    start=float(raw.get("start", 0.0)),
                    end=float(raw.get("end", 0.0)),
                    decor=str(raw.get("decor", "unknown")),
                    people=str(raw.get("people", "")),
                    objects=[str(x) for x in (raw.get("objects") or []) if x],
                    action=str(raw.get("action", "")),
                    transcript_summary=str(raw.get("transcript_summary", ""))[:300],
                    visual_importance=max(
                        0, min(100, round(float(raw.get("visual_importance", 0))))
                    ),
                    narrative_role=str(raw.get("narrative_role", "neutral")),
                )
            )
        except (TypeError, ValueError):
            continue

    summary = str(payload.get("video_summary") or "")[:600]
    return VideoMap(summary=summary, events=events), len(frames), result.tokens_total
