"""Transcript-based segment boundary snapping.

LLM-selected timestamps are approximate and routinely land mid-phrase, which
produces clips that start on an orphan word from the previous sentence and end
in the middle of a thought. This module realigns each segment to phrase
boundaries derived from the word-level transcript we already have.

Phrase boundaries are inferred from inter-word gaps (silence). whisper-1 gives
us word-level timings but no punctuation, so gaps are the primary signal; the
punctuation test is kept as a free bonus for the day the ASR provides it. The
gap threshold is adaptive (a floor OR the 85th percentile of observed gaps) so
it holds up in both dense and slow speech.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from ..models import ArcSegmentSpec, StoryArc, TranscriptWord

STRONG_PUNCTUATION = (".", "!", "?")
TRAILING_QUOTES = "\"')]}»”’"  # noqa: RUF001 (curly quotes are intentional data)

# Boundary detection
GAP_FLOOR_SECONDS = 0.28          # minimum gap to treat as a phrase boundary
GAP_PERCENTILE = 85.0             # adaptive component of the gap threshold

# Padding around the snapped window
PREROLL_SECONDS = 0.12            # breathing room before the first word
PADDING_SECONDS = 0.22            # let the last word finish before the cut

# End search
END_BACK_SLACK_SECONDS = 0.5      # accept a phrase-end this far before the LLM end
END_EXTENSION_SECONDS = 8.0       # allow extending this far past the LLM end
END_EXTENSION_MAX_DURATION = 45.0  # ...as long as the raw span stays under this

# Final duration guard
MIN_DURATION_SECONDS = 8.0
MAX_DURATION_SECONDS = 50.0

# (first_word_index, last_word_index) into the sorted word list
Phrase = tuple[int, int]


@dataclass(frozen=True)
class SnapReport:
    arcs_seen: int
    segments_seen: int
    segments_changed: int
    segments_failed: int = 0


def _sorted_words(words: list[TranscriptWord]) -> list[TranscriptWord]:
    return sorted(words, key=lambda w: (w.start, w.end))


def _ends_sentence(word: str) -> bool:
    return word.strip().rstrip(TRAILING_QUOTES).endswith(STRONG_PUNCTUATION)


def _percentile(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile. Empty -> 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


def _gap_threshold(
    words: list[TranscriptWord], *, floor: float, percentile: float
) -> float:
    """Adaptive silence threshold: max(floor, p85 of inter-word gaps).

    Dense speech has tiny gaps, so the floor dominates. Slow speech has large
    gaps everywhere, so the percentile lifts the bar and only the real phrase
    breaks (the widest gaps) survive as boundaries.
    """
    gaps = [max(0.0, words[i + 1].start - words[i].end) for i in range(len(words) - 1)]
    return max(floor, _percentile(gaps, percentile))


def _phrases(words: list[TranscriptWord], *, threshold: float) -> list[Phrase]:
    """Split words into phrases at silence gaps (or punctuation, when present)."""
    if not words:
        return []
    phrases: list[Phrase] = []
    start = 0
    for i in range(len(words) - 1):
        gap = words[i + 1].start - words[i].end
        if gap >= threshold or _ends_sentence(words[i].word):
            phrases.append((start, i))
            start = i + 1
    phrases.append((start, len(words) - 1))
    return phrases


def _select_start_word(
    words: list[TranscriptWord], phrases: list[Phrase], start_llm: float
) -> int:
    """Pick the first word of the clip.

    The LLM start lands somewhere in a phrase. If it lands in the first third,
    the LLM meant that phrase -> snap back to its start. If it lands later, the
    start is really the tail of that phrase, so the intended content is the
    *next* phrase -> snap forward to its start.
    """
    idx = 0
    for pi, (first, _last) in enumerate(phrases):
        if words[first].start <= start_llm:
            idx = pi
        else:
            break  # phrases are sorted by start time

    first, last = phrases[idx]
    p_start = words[first].start
    p_end = words[last].end
    first_third = p_start + (p_end - p_start) / 3.0

    if start_llm <= first_third:
        return first
    if idx + 1 < len(phrases):
        return phrases[idx + 1][0]
    return first


def _select_end_word(
    words: list[TranscriptWord],
    phrases: list[Phrase],
    end_llm: float,
    start_time: float,
    *,
    back_slack: float,
    extension: float,
    extension_max_duration: float,
) -> int | None:
    """Pick the last word of the clip by looking for a forward phrase-end.

    Returns the last-word index of the chosen phrase, or None if no phrase-end
    is reachable within the caps (caller then keeps the original window).
    """
    max_end = min(end_llm + extension, start_time + extension_max_duration)
    lower = end_llm - back_slack

    # Forward: first phrase-end at/after (end_llm - slack) that fits the caps.
    for _first, last in phrases:
        phrase_end = words[last].end
        if phrase_end <= start_time:
            continue
        if lower <= phrase_end <= max_end:
            return last

    # Nothing reachable forward -> recede to the last phrase-end still inside
    # the window, rather than cutting mid-word.
    fallback: int | None = None
    for _first, last in phrases:
        phrase_end = words[last].end
        if start_time < phrase_end <= max_end:
            fallback = last
    return fallback


def _snap_segment_impl(
    words: list[TranscriptWord],
    start: float,
    end: float,
    *,
    preroll_seconds: float,
    padding_seconds: float,
    gap_floor_seconds: float,
    gap_percentile: float,
    end_back_slack_seconds: float,
    end_extension_seconds: float,
    end_extension_max_duration: float,
    min_duration_seconds: float,
    max_duration_seconds: float,
) -> tuple[float, float, bool]:
    """Core snap. Returns (start, end, failed).

    ``failed`` is True when we could not produce a valid phrase-aligned window
    and fell back to the original one.
    """
    if end <= start or not words:
        return start, end, True

    ordered = _sorted_words(words)
    threshold = _gap_threshold(
        ordered, floor=gap_floor_seconds, percentile=gap_percentile
    )
    phrases = _phrases(ordered, threshold=threshold)
    if not phrases:
        return start, end, True

    start_word = _select_start_word(ordered, phrases, start)
    start_time = ordered[start_word].start

    end_word = _select_end_word(
        ordered,
        phrases,
        end,
        start_time,
        back_slack=end_back_slack_seconds,
        extension=end_extension_seconds,
        extension_max_duration=end_extension_max_duration,
    )
    if end_word is None or end_word < start_word:
        return start, end, True

    snapped_start = max(0.0, start_time - preroll_seconds)
    snapped_end = ordered[end_word].end + padding_seconds

    duration = snapped_end - snapped_start
    if duration < min_duration_seconds or duration > max_duration_seconds:
        return start, end, True
    return snapped_start, snapped_end, False


def snap_segment(
    words: list[TranscriptWord],
    start: float,
    end: float,
    *,
    preroll_seconds: float = PREROLL_SECONDS,
    padding_seconds: float = PADDING_SECONDS,
    gap_floor_seconds: float = GAP_FLOOR_SECONDS,
    gap_percentile: float = GAP_PERCENTILE,
    end_back_slack_seconds: float = END_BACK_SLACK_SECONDS,
    end_extension_seconds: float = END_EXTENSION_SECONDS,
    end_extension_max_duration: float = END_EXTENSION_MAX_DURATION,
    min_duration_seconds: float = MIN_DURATION_SECONDS,
    max_duration_seconds: float = MAX_DURATION_SECONDS,
) -> tuple[float, float]:
    """Realign a segment to transcript phrase boundaries.

    The start snaps to a phrase start (receding into the current phrase or
    advancing to the next one, so an orphan tail word never drags the clip
    backwards). The end extends forward to the next phrase end so the clip
    finishes on a complete thought. If no valid window is found, the original
    is returned unchanged.
    """
    snapped_start, snapped_end, _failed = _snap_segment_impl(
        words,
        start,
        end,
        preroll_seconds=preroll_seconds,
        padding_seconds=padding_seconds,
        gap_floor_seconds=gap_floor_seconds,
        gap_percentile=gap_percentile,
        end_back_slack_seconds=end_back_slack_seconds,
        end_extension_seconds=end_extension_seconds,
        end_extension_max_duration=end_extension_max_duration,
        min_duration_seconds=min_duration_seconds,
        max_duration_seconds=max_duration_seconds,
    )
    return snapped_start, snapped_end


def snap_arc_segments(
    arcs: list[StoryArc],
    words: list[TranscriptWord],
    *,
    preroll_seconds: float = PREROLL_SECONDS,
    padding_seconds: float = PADDING_SECONDS,
    gap_floor_seconds: float = GAP_FLOOR_SECONDS,
    gap_percentile: float = GAP_PERCENTILE,
    end_back_slack_seconds: float = END_BACK_SLACK_SECONDS,
    end_extension_seconds: float = END_EXTENSION_SECONDS,
    end_extension_max_duration: float = END_EXTENSION_MAX_DURATION,
    min_duration_seconds: float = MIN_DURATION_SECONDS,
    max_duration_seconds: float = MAX_DURATION_SECONDS,
) -> tuple[list[StoryArc], SnapReport]:
    snapped_arcs: list[StoryArc] = []
    changed = 0
    failed = 0
    seen = 0

    for arc in arcs:
        snapped_segments: list[ArcSegmentSpec] = []
        for segment in arc.segments:
            seen += 1
            start, end, seg_failed = _snap_segment_impl(
                words,
                segment.start,
                segment.end,
                preroll_seconds=preroll_seconds,
                padding_seconds=padding_seconds,
                gap_floor_seconds=gap_floor_seconds,
                gap_percentile=gap_percentile,
                end_back_slack_seconds=end_back_slack_seconds,
                end_extension_seconds=end_extension_seconds,
                end_extension_max_duration=end_extension_max_duration,
                min_duration_seconds=min_duration_seconds,
                max_duration_seconds=max_duration_seconds,
            )
            if seg_failed:
                failed += 1
            if abs(start - segment.start) > 0.001 or abs(end - segment.end) > 0.001:
                changed += 1
            snapped_segments.append(replace(segment, start=start, end=end))
        snapped_arcs.append(replace(arc, segments=snapped_segments))

    return snapped_arcs, SnapReport(
        arcs_seen=len(arcs),
        segments_seen=seen,
        segments_changed=changed,
        segments_failed=failed,
    )
