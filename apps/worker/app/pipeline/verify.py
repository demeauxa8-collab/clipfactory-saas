"""Anti-hallucination verification.

LLMs can invent moments and excerpts that don't exist in the source. Before we
render anything, we verify that each segment's transcript_excerpt is actually
present in the transcript around the claimed timestamps.

Rejected segments cause the whole arc to be dropped. We prefer 2 solid clips
over 3 where one is a hallucination.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

import structlog

from ..models import ArcSegmentSpec, StoryArc, Transcript

log = structlog.get_logger()

# Words within this many seconds outside the claimed window are still allowed in
# the comparison (LLMs round timestamps loosely).
_WINDOW_PADDING_SECONDS = 3.0

# Measure coverage of the quoted words, independently of window padding.
_MIN_RATIO = 0.85
_PROTECTED_WORDS = frozenset(
    {"ne", "n", "pas", "jamais", "sans", "aucun", "aucune", "non", "not", "no", "never", "without"}
)


_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", text).casefold()).strip()


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", _normalize(text))


def _transcript_in_window(transcript: Transcript, start: float, end: float) -> str:
    lo = start - _WINDOW_PADDING_SECONDS
    hi = end + _WINDOW_PADDING_SECONDS
    words = [w.word for w in transcript.words if w.start < hi and w.end > lo]
    return " ".join(words)


def verify_segment(transcript: Transcript, segment: ArcSegmentSpec) -> tuple[bool, float]:
    """Returns (ok, ratio). ok is True if the excerpt is plausibly in the window."""
    excerpt = _tokens(segment.transcript_excerpt)
    if not excerpt:
        return False, 0.0
    window_text = _tokens(_transcript_in_window(transcript, segment.start, segment.end))
    if not window_text:
        return False, 0.0
    for index in range(len(window_text) - len(excerpt) + 1):
        if window_text[index : index + len(excerpt)] == excerpt:
            return True, 1.0
    blocks = SequenceMatcher(None, excerpt, window_text, autojunk=False).get_matching_blocks()[:-1]
    matched = {index for block in blocks for index in range(block.a, block.a + block.size)}
    ratio = len(matched) / len(excerpt)
    if len(excerpt) < 6 or not blocks:
        return False, ratio
    # Fuzzy lexical recovery may tolerate a transcription spelling difference,
    # but it cannot invent a number or negate an original claim.
    if any(
        index not in matched and (any(c.isdigit() for c in token) or token in _PROTECTED_WORDS)
        for index, token in enumerate(excerpt)
    ):
        return False, ratio
    lo, hi = blocks[0].b, blocks[-1].b + blocks[-1].size
    matched_source = {index for block in blocks for index in range(block.b, block.b + block.size)}
    if any(
        index not in matched_source
        and (any(c.isdigit() for c in token) or token in _PROTECTED_WORDS)
        for index, token in enumerate(window_text)
        if lo <= index < hi
    ):
        return False, ratio
    # Do not accept a stitched quote spread across a much larger uncut passage.
    source_coverage = len(matched_source) / max(1, hi - lo)
    return ratio >= _MIN_RATIO and source_coverage >= 0.65, ratio


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


def verify_arcs(transcript: Transcript, arcs: list[StoryArc]) -> tuple[list[StoryArc], int]:
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
