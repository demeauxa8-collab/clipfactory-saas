"""Transcript-based segment boundary snapping.

LLM-selected timestamps are approximate. This module uses the word-level
transcript we already have to expand each segment to nearby phrase/silence
boundaries before vision and render.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..models import ArcSegmentSpec, StoryArc, TranscriptWord

STRONG_PUNCTUATION = (".", "!", "?")
TRAILING_QUOTES = "\"')]}»”’"


@dataclass(frozen=True)
class SnapReport:
    arcs_seen: int
    segments_seen: int
    segments_changed: int


def _sorted_words(words: list[TranscriptWord]) -> list[TranscriptWord]:
    return sorted(words, key=lambda w: (w.start, w.end))


def _ends_sentence(word: str) -> bool:
    return word.strip().rstrip(TRAILING_QUOTES).endswith(STRONG_PUNCTUATION)


def _start_boundaries(
    words: list[TranscriptWord], *, silence_threshold_seconds: float
) -> list[float]:
    if not words:
        return []
    out = [max(0.0, words[0].start)]
    for prev, cur in zip(words, words[1:]):
        gap = cur.start - prev.end
        if gap >= silence_threshold_seconds or _ends_sentence(prev.word):
            out.append(max(0.0, cur.start))
    return out


def _end_boundaries(
    words: list[TranscriptWord], *, silence_threshold_seconds: float
) -> list[float]:
    if not words:
        return []
    out: list[float] = []
    for idx, word in enumerate(words):
        next_word = words[idx + 1] if idx < len(words) - 1 else None
        gap = (next_word.start - word.end) if next_word else silence_threshold_seconds
        if next_word is None or gap >= silence_threshold_seconds or _ends_sentence(word.word):
            out.append(max(0.0, word.end))
    return out


def snap_segment(
    words: list[TranscriptWord],
    start: float,
    end: float,
    *,
    tolerance_seconds: float = 1.5,
    silence_threshold_seconds: float = 0.35,
    min_duration_seconds: float = 4.0,
) -> tuple[float, float]:
    """Expand a segment to nearby transcript boundaries.

    Start snaps to the closest upstream boundary. End snaps to the closest
    downstream boundary. If snapping would produce an invalid or too-short
    segment, the original window is kept.
    """
    if end <= start or not words:
        return start, end

    ordered = _sorted_words(words)
    starts = _start_boundaries(ordered, silence_threshold_seconds=silence_threshold_seconds)
    ends = _end_boundaries(ordered, silence_threshold_seconds=silence_threshold_seconds)

    start_candidates = [t for t in starts if start - tolerance_seconds <= t <= start]
    snapped_start = max(start_candidates) if start_candidates else start

    end_candidates = [t for t in ends if end <= t <= end + tolerance_seconds]
    snapped_end = min(end_candidates) if end_candidates else end

    snapped_start = max(0.0, snapped_start)
    if snapped_end - snapped_start < min_duration_seconds:
        return start, end
    return snapped_start, snapped_end


def snap_arc_segments(
    arcs: list[StoryArc],
    words: list[TranscriptWord],
    *,
    tolerance_seconds: float = 1.5,
    silence_threshold_seconds: float = 0.35,
) -> tuple[list[StoryArc], SnapReport]:
    snapped_arcs: list[StoryArc] = []
    changed = 0
    seen = 0

    for arc in arcs:
        snapped_segments: list[ArcSegmentSpec] = []
        for segment in arc.segments:
            seen += 1
            start, end = snap_segment(
                words,
                segment.start,
                segment.end,
                tolerance_seconds=tolerance_seconds,
                silence_threshold_seconds=silence_threshold_seconds,
            )
            if abs(start - segment.start) > 0.001 or abs(end - segment.end) > 0.001:
                changed += 1
            snapped_segments.append(replace(segment, start=start, end=end))
        snapped_arcs.append(replace(arc, segments=snapped_segments))

    return snapped_arcs, SnapReport(
        arcs_seen=len(arcs),
        segments_seen=seen,
        segments_changed=changed,
    )
