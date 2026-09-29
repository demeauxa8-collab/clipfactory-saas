"""Anchoring and snapping of segment boundaries onto the real transcript.

Two distinct jobs live here, in the order the runner must apply them:

1. ANCHORING (:func:`anchor_arcs_to_transcript`) — the selection model declares
   a start/end AND quotes the words it means (``transcript_excerpt``,
   ``opening_words``). Measured on a real run, the two disagree: on 7 arcs out
   of 8 the quoted words start 0.7s to 8.1s *after* the declared start, because
   the model reads the ``[t]`` marker of a transcript line as a start while
   quoting words from the middle of that line. Nothing used to check this: the
   verifier only asks whether the excerpt appears *somewhere* in a padded
   window, so an 8s drift scores a perfect 1.0. Anchoring re-derives the start
   from the quoted words themselves, and extends the end so ``payoff_line``
   (the line that makes the clip land) is actually inside the clip.

2. SNAPPING (:func:`snap_arc_segments`) — once the window is anchored, align it
   on phrase boundaries so the clip does not open mid-word or cut mid-thought.

Phrase boundaries come from the ASR's own punctuated sentences
(``Transcript.sentences``) whenever we have them. Inter-word silence is only a
fallback, and a rank-based one: whisper-1 returns words packed back to back
(median AND p85 inter-word gap = 0.000s on our reference job), so any
value-based threshold collapses onto its floor and yields 73 "phrases" for 2864
words. Taking the widest N% of gaps degrades gracefully on any source.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

import structlog

from ..models import (
    ArcSegmentSpec,
    StoryArc,
    Transcript,
    TranscriptSentence,
    TranscriptWord,
)

log = structlog.get_logger()

STRONG_PUNCTUATION = (".", "!", "?")
TRAILING_QUOTES = "\"')]}»”’"  # noqa: RUF001 (curly quotes are intentional data)

# --- Duration policy --------------------------------------------------------
# Single source of truth for the whole pipeline. It used to be spread over three
# contradictory floors: 12s in story_arcs (arc total), 8.0s here (per segment)
# and 12s in the prompt. The floor is a property of the *clip*, not of a
# segment: a 4s setup segment is perfectly legal inside a 3-segment arc.
MIN_SEGMENT_SECONDS = 3.0
MAX_SEGMENT_SECONDS = 30.0
MIN_CLIP_SECONDS = 12.0     # arc total — matches the prompt's "12s hard floor"
MAX_CLIP_SECONDS = 60.0

# --- Boundary detection (gap fallback) --------------------------------------
GAP_TOP_FRACTION = 0.12     # the widest 12% of inter-word gaps are boundaries
MAX_PHRASE_SECONDS = 12.0   # split anything longer at its widest internal gap

# --- Padding around a snapped/anchored window -------------------------------
PREROLL_SECONDS = 0.12            # breathing room before the first word
PADDING_SECONDS = 0.22            # let the last word finish before the cut
# A start sitting within this much of a word's end is adjacent to it, not inside
# it. Without this, the pre-roll of an anchored start falls into the tail of the
# previous word and the snapper "helpfully" adds that word back in.
MIDWORD_TOLERANCE_SECONDS = PREROLL_SECONDS

# --- End search -------------------------------------------------------------
END_BACK_SLACK_SECONDS = 0.5      # accept a phrase-end this far before the end
END_EXTENSION_SECONDS = 8.0       # allow extending this far past the end
END_EXTENSION_MAX_DURATION = 45.0  # ...as long as the raw span stays under this

# --- Final duration guard on a snapped segment ------------------------------
# The floor here is the SEGMENT floor, not the clip floor: a 4s setup inside a
# 3-segment arc is legal, and rejecting it was one reason the snap gave up.
MIN_DURATION_SECONDS = MIN_SEGMENT_SECONDS
MAX_DURATION_SECONDS = 50.0
MIN_RETAINED_FRACTION = 0.6       # a snap that drops 40% of the window is wrong

# --- Anchoring --------------------------------------------------------------
ANCHOR_TOLERANCE_SECONDS = 15.0   # observed drift peaks at 8.1s; keep headroom
ANCHOR_MIN_RATIO = 0.72           # fuzzy-match confidence to move a start
ANCHOR_HEAD_WORDS = 8             # how many quoted words identify the opening
ANCHOR_MIN_SHIFT_SECONDS = 0.05   # below this, the declared start was fine
PAYOFF_LOOKAHEAD_SECONDS = 20.0   # how far past the end we hunt for the payoff

# (first_word_index, last_word_index) into the sorted word list
Phrase = tuple[int, int]


@dataclass(frozen=True)
class SnapReport:
    arcs_seen: int
    segments_seen: int
    segments_changed: int
    segments_failed: int = 0


@dataclass(frozen=True)
class AnchorReport:
    """What anchoring actually did — every number here is a diagnosis."""

    arcs_seen: int
    segments_seen: int
    segments_anchored: int
    segments_unmatched: int
    max_drift_seconds: float
    total_drift_seconds: float
    segment_ends_anchored: int
    segment_ends_unmatched: int
    segments_missing_explicit_anchors: int
    arcs_dropped_anchor_conflicts: int
    payoffs_extended: int
    payoffs_out_of_reach: int
    payoffs_unmatched: int

    @property
    def mean_drift_seconds(self) -> float:
        return self.total_drift_seconds / self.segments_anchored if self.segments_anchored else 0.0


@dataclass(frozen=True)
class FinalDurationReport:
    """Result of the last guard after every boundary mutation has run."""

    arcs_seen: int
    arcs_kept: int
    arcs_dropped_segment_duration: int
    arcs_dropped_clip_duration: int


# =============================================================
# Phrase index
# =============================================================


@dataclass(frozen=True)
class PhraseIndex:
    """Words plus the phrase ranges over them, and where those ranges came from."""

    words: tuple[TranscriptWord, ...]
    phrases: tuple[Phrase, ...]
    source: str  # "sentences" | "gaps" | "empty"


def _sorted_words(words: Sequence[TranscriptWord]) -> list[TranscriptWord]:
    return sorted(words, key=lambda w: (w.start, w.end))


def _ends_sentence(word: str) -> bool:
    return word.strip().rstrip(TRAILING_QUOTES).endswith(STRONG_PUNCTUATION)


def _phrases_from_sentences(
    words: Sequence[TranscriptWord], sentences: Sequence[TranscriptSentence]
) -> list[Phrase]:
    """Map ASR sentences onto word indices.

    Words and sentences describe the same audio, so a single forward walk is
    enough: every word belongs to the first sentence that has not ended yet.
    Words before the first sentence join it; words after the last one extend it.
    """
    if not words or not sentences:
        return []
    ordered_sentences = sorted(sentences, key=lambda s: (s.start, s.end))
    phrases: list[Phrase] = []
    i = 0
    n = len(words)
    for sentence in ordered_sentences:
        if i >= n:
            break
        first = i
        while i < n and (words[i].start + words[i].end) / 2.0 <= sentence.end:
            i += 1
        if i > first:
            phrases.append((first, i - 1))
    if i < n:
        # Trailing words the ASR did not cover: glue them to the last sentence
        # rather than inventing a boundary.
        if phrases:
            phrases[-1] = (phrases[-1][0], n - 1)
        else:
            phrases.append((0, n - 1))
    return phrases


def _gap_boundary_indices(words: Sequence[TranscriptWord], *, top_fraction: float) -> set[int]:
    """Indices i where words[i] ends a phrase, by RANK of the following gap.

    A value threshold ("a gap of at least 0.28s") is meaningless on an ASR that
    packs words end-to-start: 85% of the gaps are exactly 0.000s, so the
    threshold falls back on its floor and almost nothing separates. Ranking
    keeps the criterion relative — the widest gaps are the breaths, whatever the
    source's absolute scale.
    """
    n_gaps = len(words) - 1
    if n_gaps <= 0:
        return set()
    gaps = [(max(0.0, words[i + 1].start - words[i].end), i) for i in range(n_gaps)]
    positive = [(g, i) for g, i in gaps if g > 0.0]
    keep = round(top_fraction * n_gaps)
    if not positive or keep <= 0:
        return set()
    positive.sort(key=lambda item: (-item[0], item[1]))
    return {i for _g, i in positive[:keep]}


def _split_long_phrase(
    words: Sequence[TranscriptWord],
    first: int,
    last: int,
    *,
    max_seconds: float,
    out: list[Phrase],
) -> None:
    """Recursively cut a too-long phrase at its widest internal gap."""
    if words[last].end - words[first].start <= max_seconds or last <= first:
        out.append((first, last))
        return
    best_gap, best_i = -1.0, -1
    for i in range(first, last):
        gap = words[i + 1].start - words[i].end
        if gap > best_gap:
            best_gap, best_i = gap, i
    if best_i < 0:
        out.append((first, last))
        return
    _split_long_phrase(words, first, best_i, max_seconds=max_seconds, out=out)
    _split_long_phrase(words, best_i + 1, last, max_seconds=max_seconds, out=out)


def _phrases_from_gaps(
    words: Sequence[TranscriptWord],
    *,
    top_fraction: float = GAP_TOP_FRACTION,
    max_phrase_seconds: float = MAX_PHRASE_SECONDS,
) -> list[Phrase]:
    """Fallback boundaries: widest gaps by rank, plus punctuation when present."""
    if not words:
        return []
    boundaries = _gap_boundary_indices(words, top_fraction=top_fraction)
    raw: list[Phrase] = []
    start = 0
    for i in range(len(words) - 1):
        if i in boundaries or _ends_sentence(words[i].word):
            raw.append((start, i))
            start = i + 1
    raw.append((start, len(words) - 1))

    phrases: list[Phrase] = []
    for first, last in raw:
        _split_long_phrase(words, first, last, max_seconds=max_phrase_seconds, out=phrases)
    return phrases


def build_phrase_index(
    words: Sequence[TranscriptWord],
    sentences: Sequence[TranscriptSentence] = (),
    *,
    top_fraction: float = GAP_TOP_FRACTION,
    max_phrase_seconds: float = MAX_PHRASE_SECONDS,
) -> PhraseIndex:
    """Phrase boundaries for a transcript: ASR sentences first, gaps as backup."""
    ordered = _sorted_words(words)
    if not ordered:
        return PhraseIndex(words=(), phrases=(), source="empty")
    phrases = _phrases_from_sentences(ordered, sentences)
    source = "sentences"
    if not phrases:
        phrases = _phrases_from_gaps(
            ordered, top_fraction=top_fraction, max_phrase_seconds=max_phrase_seconds
        )
        source = "gaps"
    return PhraseIndex(words=tuple(ordered), phrases=tuple(phrases), source=source)


def next_phrase_end_after(index: PhraseIndex, time_seconds: float) -> float | None:
    """First phrase end strictly after ``time_seconds`` (None past the last one)."""
    for _first, last in index.phrases:
        end = index.words[last].end
        if end > time_seconds + 1e-6:
            return end
    return None


# =============================================================
# Anchoring — put the cut where the model's own words are
# =============================================================


def _normalize(text: str) -> str:
    """Lowercase, keep alphanumerics only (accents included), collapse spaces.

    Punctuation and apostrophes vanish, so "J'ai" and "j ai" compare equal —
    the excerpt comes back from the model with its own typography.
    """
    chars = [ch if ch.isalnum() else " " for ch in text.lower()]
    return " ".join("".join(chars).split())


def _head_query(text: str | None, *, n_words: int) -> str:
    if not text:
        return ""
    return " ".join(_normalize(text).split()[:n_words])


def _word_index_bounds(
    words: Sequence[TranscriptWord], center: float, tolerance: float
) -> tuple[int, int]:
    lo, hi = -1, -2
    for i, w in enumerate(words):
        if w.start >= center - tolerance:
            lo = i
            break
    if lo < 0:
        return 0, -1
    for i in range(lo, len(words)):
        if words[i].start > center + tolerance:
            break
        hi = i
    return lo, hi


def _locate(
    words: Sequence[TranscriptWord],
    normalized: Sequence[str],
    query: str,
    *,
    center: float,
    tolerance: float,
    min_ratio: float,
) -> tuple[int, int, float] | None:
    """Fuzzy-find ``query`` in the words around ``center``.

    Returns (first_word_index, last_word_index, ratio) or None. Candidates are
    scored on normalized text of comparable length, so a difference in
    tokenization (elisions, numbers) cannot shift the match.
    """
    if not query or not words:
        return None
    lo, hi = _word_index_bounds(words, center, tolerance)
    if hi < lo:
        return None
    # Prefer a literal normalized match. Fuzzy matching is only a fallback for
    # ASR/model tokenization differences (numbers, apostrophes, elisions).
    exact: list[tuple[float, int, int]] = []
    query_words = len(query.split())
    for i in range(lo, hi + 1):
        parts: list[str] = []
        for j in range(i, min(len(words), i + query_words + 3)):
            if normalized[j]:
                parts.append(normalized[j])
            candidate = " ".join(parts)
            if candidate == query:
                exact.append((abs(words[i].start - center), i, j))
                break
            if len(candidate) > len(query) + 12:
                break
    if exact:
        _distance, first, last = min(exact)
        return first, last, 1.0

    target_len = len(query)
    best: tuple[float, float, int, int] | None = None
    for i in range(lo, hi + 1):
        parts: list[str] = []
        total = 0
        j = i
        while j < len(words) and total < target_len:
            token = normalized[j]
            if token:
                parts.append(token)
                total += len(token) + 1
            j += 1
        if not parts:
            continue
        candidate = " ".join(parts)
        matcher = SequenceMatcher(None, query, candidate)
        if matcher.real_quick_ratio() < min_ratio or matcher.quick_ratio() < min_ratio:
            continue
        ratio = matcher.ratio()
        if ratio < min_ratio:
            continue
        proximity = -abs(words[i].start - center)
        if best is None or (ratio, proximity) > (best[0], best[1]):
            best = (ratio, proximity, i, max(i, j - 1))
    if best is None:
        return None
    return best[2], best[3], best[0]


def _anchor_segment_start(
    words: Sequence[TranscriptWord],
    normalized: Sequence[str],
    segment: ArcSegmentSpec,
    quoted_opening: str | None,
    *,
    tolerance: float,
    min_ratio: float,
    head_words: int,
) -> tuple[int, float, bool] | None:
    """Return word index, match ratio and whether an explicit anchor matched."""
    explicit = _head_query(segment.start_anchor, n_words=head_words)
    if len(explicit) >= 8:
        found = _locate(
            words,
            normalized,
            explicit,
            center=segment.start,
            tolerance=tolerance,
            min_ratio=min_ratio,
        )
        if found is not None:
            first, _last, ratio = found
            return first, ratio, True

    queries = [
        _head_query(segment.transcript_excerpt, n_words=head_words),
        _head_query(quoted_opening, n_words=head_words),
    ]
    best: tuple[float, int] | None = None
    for query in queries:
        if len(query) < 8:  # too short to identify anything reliably
            continue
        found = _locate(
            words,
            normalized,
            query,
            center=segment.start,
            tolerance=tolerance,
            min_ratio=min_ratio,
        )
        if found is None:
            continue
        first, _last, ratio = found
        if best is None or ratio > best[0]:
            best = (ratio, first)
    if best is None:
        return None
    return best[1], best[0], False


def anchor_arcs_to_transcript(
    arcs: Sequence[StoryArc],
    transcript: Transcript,
    *,
    tolerance_seconds: float = ANCHOR_TOLERANCE_SECONDS,
    min_ratio: float = ANCHOR_MIN_RATIO,
    head_words: int = ANCHOR_HEAD_WORDS,
    preroll_seconds: float = PREROLL_SECONDS,
    padding_seconds: float = PADDING_SECONDS,
    payoff_lookahead_seconds: float = PAYOFF_LOOKAHEAD_SECONDS,
    min_segment_seconds: float = MIN_SEGMENT_SECONDS,
    max_segment_seconds: float = MAX_SEGMENT_SECONDS,
) -> tuple[list[StoryArc], AnchorReport]:
    """Re-cut every segment on the words the model actually quoted.

    Call this right after ``select_story_arcs`` and *before* ``verify_arcs``:
    the verifier then checks a window that means what it says, and the snapper
    starts from a start that is already correct.

    For each segment we look for the head of ``transcript_excerpt`` (and, for the
    first segment, of ``opening_words``) within ±tolerance of the declared
    start. On a confident match the window slides so it opens on that word minus
    a pre-roll — the declared duration is preserved, because the drift affects
    the whole window, not just its left edge. On no match, the declared window is
    kept untouched and counted: never guess, never crash.

    Finally, when ``payoff_line`` lands after the end of the last segment, the
    end is pushed to include it (plus padding) as long as the segment stays
    under ``max_segment_seconds`` — rule #1 of the prompt is that the clip must
    land.
    """
    words = _sorted_words(transcript.words)
    normalized = [_normalize(w.word) for w in words]
    if not words:
        return list(arcs), AnchorReport(
            arcs_seen=len(arcs),
            segments_seen=sum(len(a.segments) for a in arcs),
            segments_anchored=0,
            segments_unmatched=sum(len(a.segments) for a in arcs),
            max_drift_seconds=0.0,
            total_drift_seconds=0.0,
            segment_ends_anchored=0,
            segment_ends_unmatched=0,
            segments_missing_explicit_anchors=sum(
                not (s.start_anchor and s.end_anchor) for a in arcs for s in a.segments
            ),
            arcs_dropped_anchor_conflicts=0,
            payoffs_extended=0,
            payoffs_out_of_reach=0,
            payoffs_unmatched=0,
        )
    transcript_end = words[-1].end

    seen = anchored = unmatched = 0
    max_drift = 0.0
    total_drift = 0.0
    ends_anchored = ends_unmatched = 0
    missing_explicit_anchors = anchor_conflicts = 0
    payoffs_extended = payoffs_out_of_reach = payoffs_unmatched = 0
    out: list[StoryArc] = []

    for arc in arcs:
        segments: list[ArcSegmentSpec] = []
        for idx, segment in enumerate(arc.segments):
            seen += 1
            if not (segment.start_anchor and segment.end_anchor):
                missing_explicit_anchors += 1
            found = _anchor_segment_start(
                words,
                normalized,
                segment,
                arc.opening_words if idx == 0 else None,
                tolerance=tolerance_seconds,
                min_ratio=min_ratio,
                head_words=head_words,
            )
            if found is None:
                unmatched += 1
                log.warning(
                    "boundaries.anchor_not_found",
                    title=arc.title[:60],
                    segment=idx,
                    start=round(segment.start, 2),
                    excerpt=segment.transcript_excerpt[:60],
                )
                segments.append(segment)
                continue

            word_idx, ratio, explicit_start = found
            new_start = max(0.0, words[word_idx].start - preroll_seconds)
            shift = new_start - segment.start
            # A fuzzy/excerpt match may keep a sub-threshold coarse timestamp
            # to avoid needless jitter. An explicit model-selected word anchor
            # is different: even 40ms can move a 30fps cut by one frame, so it
            # must remain authoritative whenever the two values are not equal.
            if abs(shift) <= 1e-6 or (
                not explicit_start and abs(shift) < ANCHOR_MIN_SHIFT_SECONDS
            ):
                segments.append(
                    replace(segment, start_anchor_resolved=explicit_start)
                    if explicit_start
                    else segment
                )
                continue

            anchored += 1
            drift = abs(shift)
            total_drift += drift
            max_drift = max(max_drift, drift)

            # Shifting the window forward can run its end past the transcript.
            # Clamping the end alone would silently shorten the clip (a 12s arc
            # near the end of the video collapsed to 5.2s), so keep the declared
            # duration by giving back to the start what the end cannot take.
            duration = segment.end - segment.start
            max_end = transcript_end + padding_seconds
            new_end = new_start + duration
            if new_end > max_end:
                new_end = max_end
                recovered_start = max(0.0, new_end - duration)
                if recovered_start < new_start:
                    log.info(
                        "boundaries.anchor_end_clamped",
                        title=arc.title[:60],
                        segment=idx,
                        kept_start=round(recovered_start, 2),
                        anchored_start=round(new_start, 2),
                    )
                    new_start = recovered_start
            log.info(
                "boundaries.anchored",
                title=arc.title[:60],
                segment=idx,
                declared_start=round(segment.start, 2),
                anchored_start=round(new_start, 2),
                drift=round(shift, 2),
                ratio=round(ratio, 2),
            )
            segments.append(
                replace(
                    segment,
                    start=new_start,
                    end=new_end,
                    start_anchor_resolved=explicit_start,
                )
            )

        # Every explicit end anchor lets the editor choose the exact final word.
        # The seconds are only a neighbourhood hint; the transcript word clock
        # produces the authoritative end passed downstream to FFmpeg.
        for idx, segment in enumerate(segments):
            end_query = _normalize(segment.end_anchor or "")
            if len(end_query) < 8:
                continue
            # Search around the LLM's original coarse end. Start anchoring may
            # translate the working window by several seconds; that translation
            # must not move the neighbourhood used to resolve the independent
            # explicit end anchor.
            declared_end = arc.segments[idx].end
            found_end = _locate(
                words,
                normalized,
                end_query,
                center=declared_end,
                tolerance=tolerance_seconds,
                min_ratio=min_ratio,
            )
            if found_end is None:
                ends_unmatched += 1
                log.warning(
                    "boundaries.end_anchor_not_found",
                    title=arc.title[:60],
                    segment=idx,
                    end=round(declared_end, 2),
                    anchor=(segment.end_anchor or "")[:60],
                )
                continue
            _first, last_idx, ratio = found_end
            anchored_end = min(
                transcript_end + padding_seconds,
                words[last_idx].end + padding_seconds,
            )
            duration = anchored_end - segment.start
            if duration < min_segment_seconds or duration > max_segment_seconds:
                ends_unmatched += 1
                log.warning(
                    "boundaries.end_anchor_out_of_bounds",
                    title=arc.title[:60],
                    segment=idx,
                    duration=round(duration, 2),
                )
                continue
            ends_anchored += 1
            log.info(
                "boundaries.end_anchored",
                title=arc.title[:60],
                segment=idx,
                declared_end=round(declared_end, 2),
                anchored_end=round(anchored_end, 2),
                ratio=round(ratio, 2),
            )
            segments[idx] = replace(
                segment,
                end=anchored_end,
                end_anchor_resolved=True,
            )

        # --- the clip must land on its payoff ---------------------------------
        drop_for_anchor_conflict = False
        if arc.payoff_line and segments:
            last = segments[-1]
            payoff_query = _normalize(arc.payoff_line)
            found_payoff = (
                _locate(
                    words,
                    normalized,
                    payoff_query,
                    center=last.end,
                    tolerance=payoff_lookahead_seconds,
                    min_ratio=min_ratio,
                )
                if len(payoff_query) >= 8
                else None
            )
            if found_payoff is None:
                payoffs_unmatched += 1
            else:
                _first, last_idx, _ratio = found_payoff
                needed_end = words[last_idx].end + padding_seconds
                if needed_end > last.end + 1e-6:
                    if last.end_anchor_resolved:
                        anchor_conflicts += 1
                        drop_for_anchor_conflict = True
                        log.warning(
                            "boundaries.payoff_after_end_anchor",
                            title=arc.title[:60],
                            anchored_end=round(last.end, 2),
                            payoff_end=round(needed_end, 2),
                        )
                        continue
                    cap = last.start + max_segment_seconds
                    if needed_end <= cap:
                        payoffs_extended += 1
                        log.info(
                            "boundaries.payoff_pulled_in",
                            title=arc.title[:60],
                            old_end=round(last.end, 2),
                            new_end=round(needed_end, 2),
                        )
                        segments[-1] = replace(last, end=needed_end)
                    else:
                        payoffs_out_of_reach += 1
                        log.warning(
                            "boundaries.payoff_out_of_reach",
                            title=arc.title[:60],
                            end=round(last.end, 2),
                            needed_end=round(needed_end, 2),
                        )

        if not drop_for_anchor_conflict:
            out.append(replace(arc, segments=segments))

    report = AnchorReport(
        arcs_seen=len(arcs),
        segments_seen=seen,
        segments_anchored=anchored,
        segments_unmatched=unmatched,
        max_drift_seconds=round(max_drift, 3),
        total_drift_seconds=round(total_drift, 3),
        segment_ends_anchored=ends_anchored,
        segment_ends_unmatched=ends_unmatched,
        segments_missing_explicit_anchors=missing_explicit_anchors,
        arcs_dropped_anchor_conflicts=anchor_conflicts,
        payoffs_extended=payoffs_extended,
        payoffs_out_of_reach=payoffs_out_of_reach,
        payoffs_unmatched=payoffs_unmatched,
    )
    log.info(
        "boundaries.anchor_report",
        arcs=report.arcs_seen,
        segments=report.segments_seen,
        anchored=report.segments_anchored,
        unmatched=report.segments_unmatched,
        max_drift=report.max_drift_seconds,
        ends_anchored=report.segment_ends_anchored,
        ends_unmatched=report.segment_ends_unmatched,
        missing_explicit_anchors=report.segments_missing_explicit_anchors,
        anchor_conflicts=report.arcs_dropped_anchor_conflicts,
        payoffs_extended=report.payoffs_extended,
    )
    return out, report


# =============================================================
# Final guard — no boundary mutation may violate the product contract
# =============================================================


def filter_arcs_by_duration(
    arcs: Sequence[StoryArc],
    *,
    min_segment_seconds: float,
    max_segment_seconds: float,
    min_clip_seconds: float,
    max_clip_seconds: float,
) -> tuple[list[StoryArc], FinalDurationReport]:
    """Drop arcs that became invalid after anchoring/snapping.

    Parsers validate the model's coarse seconds, but word anchoring and phrase
    snapping intentionally mutate those windows. This last deterministic guard
    is therefore the authoritative duration contract passed to scoring/render.
    """
    kept: list[StoryArc] = []
    dropped_segment = 0
    dropped_clip = 0
    for arc in arcs:
        durations = [segment.end - segment.start for segment in arc.segments]
        if not durations or any(
            duration < min_segment_seconds or duration > max_segment_seconds
            for duration in durations
        ):
            dropped_segment += 1
            log.warning(
                "boundaries.final_duration_segment_drop",
                title=arc.title[:60],
                durations=[round(duration, 3) for duration in durations],
                minimum=min_segment_seconds,
                maximum=max_segment_seconds,
            )
            continue
        total = sum(durations)
        if total < min_clip_seconds or total > max_clip_seconds:
            dropped_clip += 1
            log.warning(
                "boundaries.final_duration_clip_drop",
                title=arc.title[:60],
                total=round(total, 3),
                minimum=min_clip_seconds,
                maximum=max_clip_seconds,
            )
            continue
        kept.append(arc)

    return kept, FinalDurationReport(
        arcs_seen=len(arcs),
        arcs_kept=len(kept),
        arcs_dropped_segment_duration=dropped_segment,
        arcs_dropped_clip_duration=dropped_clip,
    )


# =============================================================
# Snapping — align an (already anchored) window on phrase boundaries
# =============================================================


def _select_start_word(
    index: PhraseIndex,
    start: float,
    *,
    midword_tolerance: float = MIDWORD_TOLERANCE_SECONDS,
) -> int:
    """Pick the first word of the clip, without ever reopening what was cut.

    The old rule receded to the beginning of the current phrase, which on a real
    run re-added 5.2s of throat-clearing that the prompt had just taught the
    model to cut. After anchoring, the start is already on the right word: the
    only legitimate move backwards is when it lands *inside* a word, in which
    case we take that word whole. Otherwise we take the first word starting at
    or after it.
    """
    words = index.words
    for i, w in enumerate(words):
        if w.start >= start - 1e-6:
            # Does the previous word really straddle the requested start, or
            # does it merely end inside the pre-roll?
            if i > 0 and words[i - 1].end > start + midword_tolerance:
                return i - 1
            return i
    # Past the last word start: keep the last word if it straddles, else it is
    # the only thing left anyway.
    return len(words) - 1


def _select_end_word(
    index: PhraseIndex,
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
    words = index.words
    max_end = min(end_llm + extension, start_time + extension_max_duration)
    lower = end_llm - back_slack

    # Forward: first phrase-end at/after (end_llm - slack) that fits the caps.
    for _first, last in index.phrases:
        phrase_end = words[last].end
        if phrase_end <= start_time:
            continue
        if lower <= phrase_end <= max_end:
            return last

    # Nothing reachable forward -> recede to the last phrase-end still inside
    # the window, rather than cutting mid-word.
    fallback: int | None = None
    for _first, last in index.phrases:
        phrase_end = words[last].end
        if start_time < phrase_end <= max_end:
            fallback = last
    return fallback


def _snap_with_index(
    index: PhraseIndex,
    start: float,
    end: float,
    *,
    preroll_seconds: float,
    padding_seconds: float,
    end_back_slack_seconds: float,
    end_extension_seconds: float,
    end_extension_max_duration: float,
    min_duration_seconds: float,
    max_duration_seconds: float,
    min_retained_fraction: float,
) -> tuple[float, float, bool]:
    """Core snap. Returns (start, end, failed)."""
    if end <= start or not index.words or not index.phrases:
        return start, end, True

    start_word = _select_start_word(index, start)
    start_time = index.words[start_word].start

    end_word = _select_end_word(
        index,
        end,
        start_time,
        back_slack=end_back_slack_seconds,
        extension=end_extension_seconds,
        extension_max_duration=end_extension_max_duration,
    )
    if end_word is None or end_word < start_word:
        return start, end, True

    snapped_start = max(0.0, start_time - preroll_seconds)
    snapped_end = index.words[end_word].end + padding_seconds

    duration = snapped_end - snapped_start
    if duration < min_duration_seconds or duration > max_duration_seconds:
        return start, end, True
    if duration < min_retained_fraction * (end - start):
        # Aligning is not worth amputating the moment: keep what was asked.
        return start, end, True
    return snapped_start, snapped_end, False


def snap_segment(
    words: Sequence[TranscriptWord],
    start: float,
    end: float,
    *,
    sentences: Sequence[TranscriptSentence] = (),
    preroll_seconds: float = PREROLL_SECONDS,
    padding_seconds: float = PADDING_SECONDS,
    end_back_slack_seconds: float = END_BACK_SLACK_SECONDS,
    end_extension_seconds: float = END_EXTENSION_SECONDS,
    end_extension_max_duration: float = END_EXTENSION_MAX_DURATION,
    min_duration_seconds: float = MIN_DURATION_SECONDS,
    max_duration_seconds: float = MAX_DURATION_SECONDS,
    min_retained_fraction: float = MIN_RETAINED_FRACTION,
) -> tuple[float, float]:
    """Realign a segment on phrase boundaries.

    The start holds where it was asked (only receding when it fell mid-word);
    the end extends forward to the next phrase end so the clip finishes on a
    complete thought. If no valid window is found, the original is returned.
    """
    index = build_phrase_index(words, sentences)
    snapped_start, snapped_end, _failed = _snap_with_index(
        index,
        start,
        end,
        preroll_seconds=preroll_seconds,
        padding_seconds=padding_seconds,
        end_back_slack_seconds=end_back_slack_seconds,
        end_extension_seconds=end_extension_seconds,
        end_extension_max_duration=end_extension_max_duration,
        min_duration_seconds=min_duration_seconds,
        max_duration_seconds=max_duration_seconds,
        min_retained_fraction=min_retained_fraction,
    )
    return snapped_start, snapped_end


def snap_arc_segments(
    arcs: Sequence[StoryArc],
    words: Sequence[TranscriptWord],
    *,
    sentences: Sequence[TranscriptSentence] = (),
    preroll_seconds: float = PREROLL_SECONDS,
    padding_seconds: float = PADDING_SECONDS,
    end_back_slack_seconds: float = END_BACK_SLACK_SECONDS,
    end_extension_seconds: float = END_EXTENSION_SECONDS,
    end_extension_max_duration: float = END_EXTENSION_MAX_DURATION,
    min_duration_seconds: float = MIN_DURATION_SECONDS,
    max_duration_seconds: float = MAX_DURATION_SECONDS,
    min_retained_fraction: float = MIN_RETAINED_FRACTION,
) -> tuple[list[StoryArc], SnapReport]:
    index = build_phrase_index(words, sentences)
    snapped_arcs: list[StoryArc] = []
    changed = 0
    failed = 0
    seen = 0

    for arc in arcs:
        snapped_segments: list[ArcSegmentSpec] = []
        for segment in arc.segments:
            seen += 1
            if segment.start_anchor_resolved and segment.end_anchor_resolved:
                start, end, seg_failed = segment.start, segment.end, False
            else:
                start, end, seg_failed = _snap_with_index(
                    index,
                    segment.start,
                segment.end,
                preroll_seconds=preroll_seconds,
                padding_seconds=padding_seconds,
                end_back_slack_seconds=end_back_slack_seconds,
                end_extension_seconds=end_extension_seconds,
                end_extension_max_duration=end_extension_max_duration,
                min_duration_seconds=min_duration_seconds,
                    max_duration_seconds=max_duration_seconds,
                    min_retained_fraction=min_retained_fraction,
                )
                if segment.start_anchor_resolved:
                    start = segment.start
                if segment.end_anchor_resolved:
                    end = segment.end
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
