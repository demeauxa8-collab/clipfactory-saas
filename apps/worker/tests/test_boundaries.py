import pytest

from app.models import ArcSegmentSpec, StoryArc, TranscriptWord
from app.pipeline.boundaries import (
    _gap_threshold,
    _phrases,
    snap_arc_segments,
    snap_segment,
)


def words_from(spans: list[tuple[float, float]], *, text: str = "mot") -> list[TranscriptWord]:
    """Build word-level transcript from (start, end) spans. No punctuation,
    mirroring whisper-1 output."""
    return [TranscriptWord(text, start, end) for start, end in spans]


# ---------------------------------------------------------------------------
# A three-phrase, dense-speech transcript with no punctuation. Intra-phrase
# gaps are 0.05s, phrase boundaries are 0.60s silences -> gaps alone must
# produce exactly 3 phrases.
# ---------------------------------------------------------------------------
DENSE_SPANS = [
    (10.00, 10.50), (10.55, 11.10), (11.15, 11.90), (11.95, 12.80), (12.85, 13.60),
    (14.20, 14.80), (14.85, 15.50), (15.55, 16.40), (16.45, 17.30), (17.35, 18.20),
    (18.80, 19.50), (19.55, 20.40), (20.45, 21.30), (21.35, 22.20), (22.25, 23.10),
]
# Phrase A: 10.00 -> 13.60 | Phrase B: 14.20 -> 18.20 | Phrase C: 18.80 -> 23.10


# --- 1. Adaptive gap threshold ---------------------------------------------


def test_gap_threshold_floor_in_dense_speech() -> None:
    words = words_from(DENSE_SPANS)
    # Tiny intra-word gaps -> the 0.28 floor dominates.
    assert _gap_threshold(words, floor=0.28, percentile=85.0) == pytest.approx(0.28)


def test_gap_threshold_adapts_up_in_slow_speech() -> None:
    # "Slow" speech: normal inter-word gaps of 0.30s would each trip the 0.28
    # floor and shatter every word into its own phrase. The p85 must lift the
    # threshold so only the wide 0.90s breaks survive.
    spans = [
        (10.00, 10.50), (10.80, 11.30), (11.60, 12.10),   # gaps 0.30, 0.30
        (13.00, 13.50), (13.80, 14.30), (14.60, 15.10),   # break 0.90, then 0.30, 0.30
        (16.00, 16.50), (16.80, 17.30), (17.60, 18.10),   # break 0.90, then 0.30, 0.30
    ]
    words = words_from(spans)
    threshold = _gap_threshold(words, floor=0.28, percentile=85.0)
    assert threshold > 0.30  # adapted above the routine 0.30 gaps
    assert threshold < 0.90  # but still catches the real breaks
    # Only the two 0.90s gaps are boundaries -> 3 phrases, not 9.
    assert _phrases(words, threshold=threshold) == [(0, 2), (3, 5), (6, 8)]


def test_phrases_split_on_gaps_without_punctuation() -> None:
    words = words_from(DENSE_SPANS)
    threshold = _gap_threshold(words, floor=0.28, percentile=85.0)
    assert _phrases(words, threshold=threshold) == [(0, 4), (5, 9), (10, 14)]


def test_phrases_still_split_on_punctuation_when_present() -> None:
    # If a future ASR emits punctuation, it must create a boundary even when
    # the gap is tiny.
    words = [
        TranscriptWord("Bonjour", 1.00, 1.40),
        TranscriptWord("tout", 1.45, 1.70),
        TranscriptWord("monde.", 1.75, 2.10),
        TranscriptWord("On", 2.15, 2.35),
        TranscriptWord("continue", 2.40, 2.90),
    ]
    assert _phrases(words, threshold=0.28) == [(0, 2), (3, 4)]


# --- 2. Start snapping ------------------------------------------------------


def test_start_recedes_to_phrase_start_when_in_first_third() -> None:
    words = words_from(DENSE_SPANS)
    # 10.80 is in the first third of phrase A (10.00 -> 13.60, cutoff 11.20).
    start, _end = snap_segment(words, 10.80, 20.00)
    assert start == pytest.approx(10.00 - 0.12)  # snapped back to phrase A start


def test_start_advances_to_next_phrase_when_on_previous_tail() -> None:
    words = words_from(DENSE_SPANS)
    # 13.00 is the tail of phrase A (past the first-third cutoff 11.20). The
    # killer bug: it used to recede deeper into phrase A. It must now advance
    # to the start of phrase B (14.20).
    start, _end = snap_segment(words, 13.00, 22.00)
    assert start == pytest.approx(14.20 - 0.12)
    assert start != pytest.approx(10.00 - 0.12)


def test_start_advances_when_llm_lands_in_inter_phrase_silence() -> None:
    words = words_from(DENSE_SPANS)
    # 13.90 falls in the 0.60s silence between phrase A and B -> advance to B.
    start, _end = snap_segment(words, 13.90, 22.00)
    assert start == pytest.approx(14.20 - 0.12)


# --- 3. End snapping --------------------------------------------------------


def test_end_extends_forward_past_mid_phrase_cut() -> None:
    words = words_from(DENSE_SPANS)
    # LLM end 20.00 lands mid phrase C. Instead of cutting there, extend
    # forward to the phrase-C end (23.10).
    _start, end = snap_segment(words, 14.50, 20.00)
    assert end == pytest.approx(23.10 + 0.22)
    assert end > 20.00


def test_end_extension_blocked_by_duration_cap_falls_back_to_last_boundary() -> None:
    # Long middle phrase pushes the next phrase-end (60.00) past the 45s span
    # cap, so we cannot reach it; snap must recede to the last reachable
    # phrase-end (54.00) rather than cut mid-word.
    spans = [
        (10.00, 10.50), (10.55, 11.20),                 # phrase 1 -> end 11.20
        (11.80, 12.50), (12.55, 40.00), (40.05, 54.00),  # long phrase 2 -> end 54.00
        (54.60, 56.00), (56.05, 60.00),                 # phrase 3 -> end 60.00
    ]
    words = words_from(spans)
    start, end = snap_segment(words, 10.30, 58.00)
    assert start == pytest.approx(10.00 - 0.12)
    # 45s cap from start (10.00) = 55.00; 60.00 is unreachable -> fall back to 54.00.
    assert end == pytest.approx(54.00 + 0.22)


# --- 4. Padding / clamps / failure ------------------------------------------


def test_preroll_clamps_at_zero_and_padding_applied() -> None:
    spans = [
        (0.05, 0.60), (0.65, 1.30), (1.35, 2.10),   # phrase 1: 0.05 -> 2.10
        (2.70, 4.00), (4.05, 8.00), (8.05, 10.00),  # phrase 2: 2.70 -> 10.00
    ]
    words = words_from(spans)
    start, end = snap_segment(words, 0.30, 9.00)
    assert start == 0.0                       # 0.05 - 0.12 preroll clamps to 0
    assert end == pytest.approx(10.00 + 0.22)  # padding on the last word


def test_short_window_returns_original_and_flags_failure() -> None:
    # A single ~1.2s phrase can never reach the 8s minimum -> keep original,
    # flag the failure so the caller knows the snap did not take.
    words = words_from([(5.00, 5.30), (5.35, 5.80), (5.85, 6.20)])
    arc = StoryArc(
        title="Arc",
        arc_type="hook",
        segments=[
            ArcSegmentSpec(role="single", start=5.10, end=6.00, transcript_excerpt="x")
        ],
        viral_reason="r",
        estimated_retention=70,
        continuity_risk="low",
    )
    snapped, report = snap_arc_segments([arc], words)

    assert snapped[0].segments[0].start == pytest.approx(5.10)
    assert snapped[0].segments[0].end == pytest.approx(6.00)
    assert report.segments_failed == 1
    assert report.segments_changed == 0


def test_snap_segment_returns_original_on_invalid_window() -> None:
    words = words_from(DENSE_SPANS)
    assert snap_segment(words, 12.0, 12.0) == (12.0, 12.0)
    assert snap_segment([], 1.0, 9.0) == (1.0, 9.0)


# --- 5. Arc-level reporting --------------------------------------------------


def test_snap_arc_segments_preserves_why_and_reports() -> None:
    words = words_from(DENSE_SPANS)
    arc = StoryArc(
        title="Arc",
        arc_type="hook",
        segments=[
            ArcSegmentSpec(
                role="single",
                start=13.00,   # tail of phrase A -> should advance to B
                end=20.00,     # mid phrase C -> should extend to C end
                transcript_excerpt="Setup clair",
                why="pose le contexte",
            )
        ],
        viral_reason="contraste",
        estimated_retention=80,
        continuity_risk="low",
    )

    snapped, report = snap_arc_segments([arc], words)

    assert report.arcs_seen == 1
    assert report.segments_seen == 1
    assert report.segments_changed == 1
    assert report.segments_failed == 0
    seg = snapped[0].segments[0]
    assert seg.why == "pose le contexte"
    assert seg.start == pytest.approx(14.20 - 0.12)
    assert seg.end == pytest.approx(23.10 + 0.22)
