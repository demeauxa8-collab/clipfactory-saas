"""Anti-hallucination verification.

LLMs can invent moments and excerpts that don't exist in the source. Before we
render anything, we verify that each segment's transcript_excerpt is actually
present in the transcript around the claimed timestamps.

Rejected segments cause the whole arc to be dropped. We prefer 2 solid clips
over 3 where one is a hallucination.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

import structlog

from ..models import ArcSegmentSpec, StoryArc, Transcript

log = structlog.get_logger()

# Words within this many seconds outside the claimed window are still allowed in
# the comparison (LLMs round timestamps loosely).
_WINDOW_PADDING_SECONDS = 3.0

# Minimum fuzzy ratio for the excerpt to be considered "found".
_MIN_RATIO = 0.65


_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", text.lower()).strip()


def _transcript_in_window(
    transcript: Transcript, start: float, end: float
) -> str:
    lo = start - _WINDOW_PADDING_SECONDS
    hi = end + _WINDOW_PADDING_SECONDS
    words = [w.word for w in transcript.words if lo <= w.start <= hi or lo <= w.end <= hi]
    return " ".join(words)


def verify_segment(transcript: Transcript, segment: ArcSegmentSpec) -> tuple[bool, float]:
    """Returns (ok, ratio). ok is True if the excerpt is plausibly in the window."""
    excerpt = _normalize(segment.transcript_excerpt)
    if not excerpt:
        # Empty excerpt: we cannot verify; allow it but flag low confidence.
        return True, 0.0
    window_text = _normalize(_transcript_in_window(transcript, segment.start, segment.end))
    if not window_text:
        return False, 0.0
    # First: substring match (fast and very high confidence)
    if excerpt in window_text or window_text in excerpt:
        return True, 1.0
    ratio = SequenceMatcher(None, excerpt, window_text).ratio()
    return ratio >= _MIN_RATIO, ratio


def verify_arc(transcript: Transcript, arc: StoryArc) -> tuple[bool, list[float]]:
    """Returns (ok, list_of_ratios_per_segment)."""
    ratios: list[float] = []
    ok = True
    for seg in arc.segments:
        seg_ok, ratio = verify_segment(transcript, seg)
        ratios.append(round(ratio, 2))
        if not seg_ok:
            ok = False
    return ok, ratios


def verify_arcs(
    transcript: Transcript, arcs: list[StoryArc]
) -> tuple[list[StoryArc], int]:
    """Filter out arcs with hallucinated segments.

    Returns (kept_arcs, dropped_count).
    """
    kept: list[StoryArc] = []
    dropped = 0
    for arc in arcs:
        ok, ratios = verify_arc(transcript, arc)
        if ok:
            kept.append(arc)
        else:
            dropped += 1
            log.warning(
                "verify.arc_dropped",
                title=arc.title[:60],
                ratios=ratios,
            )
    return kept, dropped
