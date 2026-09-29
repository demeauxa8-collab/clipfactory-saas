"""Boundary detection, anchoring and snapping.

Three contracts are checked here, in the order the pipeline applies them:
phrase boundaries (ASR sentences first, ranked silences as a fallback),
anchoring of a window onto the words the model actually quoted, and snapping of
that window onto phrase edges without ever reopening what the model cut.
"""

import pytest

from app.models import (
    ArcSegmentSpec,
    StoryArc,
    Transcript,
    TranscriptSentence,
    TranscriptWord,
)
from app.pipeline.boundaries import (
    MIN_CLIP_SECONDS,
    MIN_SEGMENT_SECONDS,
    _gap_boundary_indices,
    _phrases_from_gaps,
    _phrases_from_sentences,
    anchor_arcs_to_transcript,
    build_phrase_index,
    filter_arcs_by_duration,
    next_phrase_end_after,
    snap_arc_segments,
    snap_segment,
)


def words_from(spans: list[tuple[float, float]], *, text: str = "mot") -> list[TranscriptWord]:
    """Build word-level transcript from (start, end) spans. No punctuation,
    mirroring whisper-1 output."""
    return [TranscriptWord(text, start, end) for start, end in spans]


def words_from_text(text: str, start: float, *, step: float = 0.4) -> list[TranscriptWord]:
    """Pack words back to back from `start`, exactly as whisper-1 does."""
    out: list[TranscriptWord] = []
    t = start
    for token in text.split():
        out.append(TranscriptWord(token, t, t + step))
        t += step
    return out


# ---------------------------------------------------------------------------
# A three-phrase, dense-speech transcript with no punctuation. Intra-phrase
# gaps are 0.05s, phrase boundaries are 0.60s silences -> gaps alone must
# produce exactly 3 phrases.
# ---------------------------------------------------------------------------
DENSE_SPANS = [
    (10.00, 10.50),
    (10.55, 11.10),
    (11.15, 11.90),
    (11.95, 12.80),
    (12.85, 13.60),
    (14.20, 14.80),
    (14.85, 15.50),
    (15.55, 16.40),
    (16.45, 17.30),
    (17.35, 18.20),
    (18.80, 19.50),
    (19.55, 20.40),
    (20.45, 21.30),
    (21.35, 22.20),
    (22.25, 23.10),
]
# Phrase A: 10.00 -> 13.60 | Phrase B: 14.20 -> 18.20 | Phrase C: 18.80 -> 23.10


# --- 1. Phrase boundaries from the ASR's own sentences ----------------------


def test_sentences_are_the_primary_boundary_source() -> None:
    words = words_from(DENSE_SPANS)
    sentences = [
        TranscriptSentence("Première phrase.", 10.0, 13.6),
        TranscriptSentence("Deuxième phrase !", 14.2, 18.2),
        TranscriptSentence("Et la troisième ?", 18.8, 23.1),
    ]
    index = build_phrase_index(words, sentences)
    assert index.source == "sentences"
    assert index.phrases == ((0, 4), (5, 9), (10, 14))


def test_sentences_split_packed_words_that_gaps_could_never_separate() -> None:
    """The real whisper-1 failure: words are packed end-to-start, so there is no
    silence to find. Punctuated sentences still cut in the right place."""
    words = words_from_text("un deux trois quatre cinq six", 0.0)  # zero gaps
    sentences = [
        TranscriptSentence("Un deux trois.", 0.0, 1.2),
        TranscriptSentence("Quatre cinq six.", 1.2, 2.4),
    ]
    assert _phrases_from_sentences(words, sentences) == [(0, 2), (3, 5)]


def test_words_past_the_last_sentence_extend_it_instead_of_being_lost() -> None:
    words = words_from(DENSE_SPANS)
    sentences = [TranscriptSentence("Tronquée.", 10.0, 13.6)]
    assert _phrases_from_sentences(words, sentences) == [(0, 14)]


def test_index_falls_back_to_gaps_without_sentences() -> None:
    index = build_phrase_index(words_from(DENSE_SPANS))
    assert index.source == "gaps"
    assert index.phrases


def test_empty_transcript_yields_an_empty_index() -> None:
    index = build_phrase_index([])
    assert index.source == "empty"
    assert index.phrases == ()


# --- 2. Gap fallback: rank, not absolute value ------------------------------


def test_gap_boundaries_are_ranked_not_thresholded() -> None:
    """Every gap here is far below the old 0.28s floor. A value threshold finds
    nothing; ranking still isolates the two widest breaks."""
    spans = [
        (0.00, 0.40),
        (0.40, 0.80),
        (0.80, 1.20),
        (1.35, 1.75),
        (1.75, 2.15),
        (2.15, 2.55),  # 0.15 break
        (2.70, 3.10),
        (3.10, 3.50),
        (3.50, 3.90),  # 0.15 break
    ]
    words = words_from(spans)
    assert _gap_boundary_indices(words, top_fraction=0.25) == {2, 5}
    assert _phrases_from_gaps(words, top_fraction=0.25) == [(0, 2), (3, 5), (6, 8)]


def test_gap_fallback_survives_a_transcript_with_no_silence_at_all() -> None:
    """All gaps are exactly 0.000s (the observed whisper-1 case). We must not
    crash and must not return one 30s "phrase" either."""
    words = words_from_text(" ".join(["mot"] * 60), 0.0, step=0.5)
    phrases = _phrases_from_gaps(words, top_fraction=0.12, max_phrase_seconds=12.0)
    assert len(phrases) > 1
    durations = [words[b].end - words[a].start for a, b in phrases]
    assert max(durations) <= 12.0 + 1e-6


def test_punctuation_still_creates_a_boundary_in_the_fallback() -> None:
    words = [
        TranscriptWord("Bonjour", 1.00, 1.40),
        TranscriptWord("tout", 1.45, 1.70),
        TranscriptWord("monde.", 1.75, 2.10),
        TranscriptWord("On", 2.15, 2.35),
        TranscriptWord("continue", 2.40, 2.90),
    ]
    assert (0, 2) in _phrases_from_gaps(words, top_fraction=0.0)


def test_next_phrase_end_after_walks_forward() -> None:
    index = build_phrase_index(
        words_from(DENSE_SPANS),
        [
            TranscriptSentence("A.", 10.0, 13.6),
            TranscriptSentence("B.", 14.2, 18.2),
            TranscriptSentence("C.", 18.8, 23.1),
        ],
    )
    assert next_phrase_end_after(index, 12.0) == pytest.approx(13.60)
    assert next_phrase_end_after(index, 13.60) == pytest.approx(18.20)
    assert next_phrase_end_after(index, 23.10) is None


# --- 3. Anchoring on the quoted words ---------------------------------------

# Reproduction of the drift observed in production: the model declares start=1.0
# (the [t] marker of the transcript line) but quotes words that only start at
# 5.4 — 11 words later. The payoff line lands further out still, at 19.8.
ANCHOR_TEXT = (
    "c est beaucoup plus long terme que TikTok et surtout tu "           # 0-10
    "le problème c est que sur Google il faut au minimum cent euros pour lancer "  # 11-25
    "on va faire ça ensemble tranquillement sans se presser du tout maintenant "   # 26-37
    "et là on est vraiment content du résultat obtenu "                  # 38-46
    "voilà c est fini pour cette vidéo à très vite les amis"             # 47-57
)
ANCHOR_WORDS = words_from_text(ANCHOR_TEXT, 1.0)
QUOTED_START = 1.0 + 11 * 0.4      # 5.40 — where the quoted words really are
PAYOFF_END = 1.4 + 46 * 0.4        # 19.80 — end of the payoff line


def _arc_with(
    start: float,
    end: float,
    excerpt: str,
    *,
    opening: str | None = None,
    payoff: str | None = None,
    start_anchor: str | None = None,
    end_anchor: str | None = None,
) -> StoryArc:
    return StoryArc(
        title="Arc",
        arc_type="hook",
        segments=[
            ArcSegmentSpec(
                role="single",
                start=start,
                end=end,
                transcript_excerpt=excerpt,
                start_anchor=start_anchor,
                end_anchor=end_anchor,
            )
        ],
        viral_reason="r",
        estimated_retention=70,
        continuity_risk="low",
        opening_words=opening,
        payoff_line=payoff,
    )


def _transcript(words: list[TranscriptWord]) -> Transcript:
    return Transcript(text=" ".join(w.word for w in words), words=words)


def test_anchor_moves_the_start_onto_the_quoted_words() -> None:
    arc = _arc_with(1.0, 13.0, "Le problème c'est que sur Google il faut au minimum 100 euros")
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))

    seg = anchored.segments[0]
    assert seg.start == pytest.approx(QUOTED_START - 0.12)
    assert report.segments_anchored == 1
    assert report.max_drift_seconds == pytest.approx(abs(seg.start - 1.0), abs=1e-3)


def test_explicit_start_anchor_applies_a_sub_threshold_frame_shift() -> None:
    exact_start = QUOTED_START - 0.12
    arc = _arc_with(
        exact_start + 0.04,
        exact_start + 12.04,
        "Le problème c est que sur Google il faut au minimum cent euros",
        start_anchor="le problème c est que sur Google",
    )

    (anchored,), report = anchor_arcs_to_transcript(
        [arc],
        _transcript(ANCHOR_WORDS),
    )

    assert anchored.segments[0].start == pytest.approx(exact_start)
    assert anchored.segments[0].start_anchor_resolved is True
    assert report.segments_anchored == 1
    assert report.max_drift_seconds == pytest.approx(0.04)


def test_anchor_preserves_the_declared_duration() -> None:
    arc = _arc_with(1.0, 13.0, "Le problème c'est que sur Google il faut au minimum 100 euros")
    (anchored,), _ = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    seg = anchored.segments[0]
    assert seg.end - seg.start == pytest.approx(12.0, abs=0.01)


def test_anchor_can_use_opening_words_when_the_excerpt_is_useless() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "",  # no excerpt at all
        opening="le problème c'est que sur Google",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.segments_anchored == 1
    assert anchored.segments[0].start == pytest.approx(QUOTED_START - 0.12)


def test_explicit_start_anchor_has_priority_over_excerpt_head() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "c est beaucoup plus long terme que TikTok",
        start_anchor="le problème c est que sur Google",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.segments_anchored == 1
    assert anchored.segments[0].start == pytest.approx(QUOTED_START - 0.12)


def test_anchor_keeps_the_declared_window_when_nothing_matches() -> None:
    arc = _arc_with(1.0, 13.0, "une phrase qui n'a jamais été prononcée dans cette vidéo")
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert anchored.segments[0].start == pytest.approx(1.0)
    assert anchored.segments[0].end == pytest.approx(13.0)
    assert report.segments_unmatched == 1
    assert report.segments_anchored == 0


def test_anchor_ignores_a_match_outside_the_tolerance_window() -> None:
    arc = _arc_with(200.0, 212.0, "Le problème c'est que sur Google il faut au minimum 100 euros")
    _, report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.segments_unmatched == 1


def test_anchor_is_a_no_op_when_the_model_was_already_right() -> None:
    start = QUOTED_START - 0.12
    arc = _arc_with(
        start, start + 12.0, "Le problème c'est que sur Google il faut au minimum 100 euros"
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert anchored.segments[0].start == pytest.approx(start)
    assert report.segments_anchored == 0
    assert report.segments_unmatched == 0


def test_anchor_never_crashes_on_an_empty_transcript() -> None:
    arc = _arc_with(1.0, 13.0, "peu importe")
    arcs, report = anchor_arcs_to_transcript([arc], Transcript(text="", words=[]))
    assert arcs[0].segments[0].start == pytest.approx(1.0)
    assert report.segments_unmatched == 1


# --- 4. The clip must land on its payoff ------------------------------------


def test_payoff_after_the_window_pulls_the_end_forward() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "Le problème c'est que sur Google il faut au minimum 100 euros",
        payoff="on est vraiment content du résultat obtenu",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.payoffs_extended == 1
    assert anchored.segments[0].end == pytest.approx(PAYOFF_END + 0.22)


def test_payoff_already_inside_the_window_changes_nothing() -> None:
    arc = _arc_with(
        1.0,
        19.0,   # 18s window: once anchored it already covers the payoff
        "Le problème c'est que sur Google il faut au minimum 100 euros",
        payoff="on est vraiment content du résultat obtenu",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.payoffs_extended == 0
    assert anchored.segments[0].end == pytest.approx(anchored.segments[0].start + 18.0)


def test_payoff_out_of_reach_is_reported_not_forced() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "Le problème c'est que sur Google il faut au minimum 100 euros",
        payoff="on est vraiment content du résultat obtenu",
    )
    (anchored,), report = anchor_arcs_to_transcript(
        [arc], _transcript(ANCHOR_WORDS), max_segment_seconds=6.0
    )
    assert report.payoffs_out_of_reach == 1
    assert anchored.segments[0].end - anchored.segments[0].start == pytest.approx(12.0)


def test_unfindable_payoff_is_counted_and_harmless() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "Le problème c'est que sur Google il faut au minimum 100 euros",
        payoff="une punchline totalement inventée par le modèle",
    )
    _, report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert report.payoffs_unmatched == 1
    assert report.payoffs_extended == 0


def test_explicit_end_anchor_sets_the_cut_after_its_last_word() -> None:
    arc = _arc_with(
        1.0,
        25.0,
        "Le problème c est que sur Google il faut au minimum cent euros",
        start_anchor="le problème c est que sur Google",
        end_anchor="et là on est vraiment content du résultat obtenu",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    seg = anchored.segments[0]
    # The explicit ending is authoritative: the old 24s coarse window is
    # shortened to the final anchored word plus the configured 220ms padding.
    expected_last_word = ANCHOR_WORDS[46].end
    assert seg.end == pytest.approx(expected_last_word + 0.22)
    assert report.segment_ends_anchored == 1
    assert report.segment_ends_unmatched == 0


def test_unfindable_end_anchor_keeps_the_window_and_is_reported() -> None:
    arc = _arc_with(
        1.0,
        13.0,
        "Le problème c est que sur Google il faut au minimum cent euros",
        end_anchor="une fin totalement inventée",
    )
    (anchored,), report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert anchored.segments[0].end - anchored.segments[0].start == pytest.approx(12.0)
    assert report.segment_ends_anchored == 0
    assert report.segment_ends_unmatched == 1


def test_end_anchor_search_uses_original_end_after_start_shift() -> None:
    tokens = [f"token{i:02d}" for i in range(70)]
    words = words_from_text(" ".join(tokens), 0.0, step=0.5)
    arc = _arc_with(
        0.0,
        20.0,
        "token09 token10 token11 token12 token13 token14",
        start_anchor="token09 token10 token11 token12 token13 token14",
        end_anchor="token35 token36 token37 token38 token39 token40",
    )
    (anchored,), report = anchor_arcs_to_transcript(
        [arc], _transcript(words), tolerance_seconds=5.0
    )

    # Resolving the start translates the working end by ~4.4s. The independent
    # end anchor is still searched around the declared 20s neighbourhood.
    assert report.segment_ends_anchored == 1
    assert anchored.segments[0].end == pytest.approx(words[40].end + 0.22)


def test_resolved_end_anchor_is_not_moved_by_phrase_snapping() -> None:
    arc = _arc_with(
        1.0,
        25.0,
        "Le problème c est que sur Google il faut au minimum cent euros",
        start_anchor="le problème c est que sur Google",
        end_anchor="et là on est vraiment content du résultat obtenu",
    )
    (anchored,), _ = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    locked_end = anchored.segments[0].end
    assert anchored.segments[0].end_anchor_resolved is True

    (snapped,), _ = snap_arc_segments([anchored], ANCHOR_WORDS)
    assert snapped.segments[0].end == pytest.approx(locked_end)


def test_payoff_after_resolved_end_anchor_drops_incoherent_arc() -> None:
    arc = _arc_with(
        1.0,
        25.0,
        "Le problème c est que sur Google il faut au minimum cent euros",
        start_anchor="le problème c est que sur Google",
        end_anchor="on va faire ça ensemble tranquillement sans se presser",
        payoff="et là on est vraiment content du résultat obtenu",
    )
    anchored, report = anchor_arcs_to_transcript([arc], _transcript(ANCHOR_WORDS))
    assert anchored == []
    assert report.arcs_dropped_anchor_conflicts == 1


def test_repeated_exact_anchor_chooses_occurrence_nearest_declared_time() -> None:
    phrase = "voici la méthode exacte pour trouver le bon résultat"
    tail = " ".join(f"suite{i}" for i in range(30))
    words = words_from_text(f"{phrase} remplissage {phrase} {tail}", 0.0, step=0.5)
    second_start = (len(phrase.split()) + 1) * 0.5
    arc = _arc_with(
        second_start,
        second_start + 12.0,
        phrase,
        start_anchor=phrase,
    )
    (anchored,), _ = anchor_arcs_to_transcript([arc], _transcript(words))
    assert anchored.segments[0].start == pytest.approx(second_start - 0.12)


# --- 5. Start snapping: no backward pull ------------------------------------


def test_start_never_recedes_to_an_earlier_phrase_start() -> None:
    """The 5.2s regression: the snap used to rewind an anchored start to the
    beginning of its phrase, re-adding the throat-clearing the model cut."""
    words = words_from(DENSE_SPANS)
    start, _end = snap_segment(words, 12.85, 22.00)
    assert start == pytest.approx(12.85 - 0.12)
    assert start > 10.00


def test_start_recedes_only_when_it_lands_mid_word() -> None:
    words = words_from(DENSE_SPANS)
    # 13.00 is inside the word [12.85, 13.60] -> take that word whole.
    start, _end = snap_segment(words, 13.00, 22.00)
    assert start == pytest.approx(12.85 - 0.12)


def test_start_advances_when_it_lands_in_silence() -> None:
    words = words_from(DENSE_SPANS)
    # 13.90 falls in the silence between phrase A and B -> next word (14.20).
    start, _end = snap_segment(words, 13.90, 22.00)
    assert start == pytest.approx(14.20 - 0.12)


def test_preroll_clamps_at_zero_and_padding_applied() -> None:
    spans = [
        (0.05, 0.60),
        (0.65, 1.30),
        (1.35, 2.10),  # phrase 1: 0.05 -> 2.10
        (2.70, 4.00),
        (4.05, 8.00),
        (8.05, 10.00),  # phrase 2: 2.70 -> 10.00
    ]
    words = words_from(spans)
    start, end = snap_segment(words, 0.30, 9.00)
    assert start == 0.0                       # 0.05 - 0.12 preroll clamps to 0
    assert end == pytest.approx(10.00 + 0.22)  # padding on the last word


# --- 6. End snapping --------------------------------------------------------


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
        (10.00, 10.50),
        (10.55, 11.20),  # phrase 1 -> end 11.20
        (11.80, 12.50),
        (12.55, 40.00),
        (40.05, 54.00),  # long phrase 2 -> end 54.00
        (54.60, 56.00),
        (56.05, 60.00),  # phrase 3 -> end 60.00
    ]
    words = words_from(spans)
    sentences = [
        TranscriptSentence("Une.", 10.00, 11.20),
        TranscriptSentence("Deux.", 11.80, 54.00),
        TranscriptSentence("Trois.", 54.60, 60.00),
    ]
    start, end = snap_segment(words, 10.30, 58.00, sentences=sentences)
    assert start == pytest.approx(10.00 - 0.12)
    # 45s cap from start (10.00) = 55.00; 60.00 is unreachable -> fall back to 54.00.
    assert end == pytest.approx(54.00 + 0.22)


# --- 7. Failure handling + reporting ----------------------------------------


def test_short_window_returns_original_and_flags_failure() -> None:
    # A 1.2s window can never reach the 3s segment floor -> keep the original
    # and flag the failure so the caller knows the snap did not take.
    words = words_from([(5.00, 5.30), (5.35, 5.80), (5.85, 6.20)])
    arc = _arc_with(5.10, 6.00, "x")
    snapped, report = snap_arc_segments([arc], words)

    assert snapped[0].segments[0].start == pytest.approx(5.10)
    assert snapped[0].segments[0].end == pytest.approx(6.00)
    assert report.segments_failed == 1
    assert report.segments_changed == 0


def test_snap_refuses_to_amputate_the_window() -> None:
    """The segment floor is now 3s, so a badly receding end could silently cut a
    35s moment down to 15s. Losing more than 40% of the window is a failure, not
    an alignment."""
    words = words_from([(10.0, 10.5), (10.55, 25.0), (25.6, 30.0), (30.05, 60.0)])
    sentences = [
        TranscriptSentence("Une.", 10.0, 25.0),
        TranscriptSentence("Deux.", 25.6, 60.0),
    ]
    start, end = snap_segment(words, 10.0, 45.0, sentences=sentences)
    assert (start, end) == (10.0, 45.0)


def test_snap_segment_returns_original_on_invalid_window() -> None:
    words = words_from(DENSE_SPANS)
    assert snap_segment(words, 12.0, 12.0) == (12.0, 12.0)
    assert snap_segment([], 1.0, 9.0) == (1.0, 9.0)


def test_snap_arc_segments_preserves_why_and_reports() -> None:
    words = words_from(DENSE_SPANS)
    arc = StoryArc(
        title="Arc",
        arc_type="hook",
        segments=[
            ArcSegmentSpec(
                role="single",
                start=14.20,   # anchored start: must stay put
                end=20.00,     # mid phrase C -> extend to C end
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


def test_snap_uses_sentences_when_they_are_provided() -> None:
    words = words_from(DENSE_SPANS)
    # One single sentence covering everything: the end can only be 23.10.
    sentences = [TranscriptSentence("Tout d'un bloc.", 10.0, 23.1)]
    _start, end = snap_segment(words, 14.50, 16.00, sentences=sentences)
    assert end == pytest.approx(23.10 + 0.22)


# --- 8. The duration floors are reconciled -----------------------------------


def test_duration_floors_are_one_documented_pair() -> None:
    """One clip floor (12s, the prompt's hard floor), one segment floor (3s).
    The old 8s snap floor was a third, contradictory value."""
    assert MIN_CLIP_SECONDS == 12.0
    assert MIN_SEGMENT_SECONDS == 3.0


def test_final_duration_guard_rechecks_segments_and_arc_total() -> None:
    too_short_segment = _arc_with(0.0, 2.99, "x")
    too_short_total = StoryArc(
        title="two tiny segments",
        arc_type="story",
        segments=[
            ArcSegmentSpec("setup", 0.0, 4.0, "a"),
            ArcSegmentSpec("payoff", 10.0, 17.0, "b"),
        ],
        viral_reason="",
        estimated_retention=70,
        continuity_risk="low",
    )
    valid = _arc_with(0.0, 12.0, "valid")
    kept, report = filter_arcs_by_duration(
        [too_short_segment, too_short_total, valid],
        min_segment_seconds=3.0,
        max_segment_seconds=30.0,
        min_clip_seconds=12.0,
        max_clip_seconds=60.0,
    )
    assert kept == [valid]
    assert report.arcs_dropped_segment_duration == 1
    assert report.arcs_dropped_clip_duration == 1


def test_anchoring_near_end_of_video_keeps_the_clip_length():
    """Codex P2: shifting a window forward past the transcript end used to clamp
    the end alone, collapsing a valid 12s arc to ~5s while still passing verify
    and snap. The declared duration must survive the clamp."""
    words = [
        TranscriptWord(word=w, start=100.0 + i * 0.4, end=100.0 + i * 0.4 + 0.38)
        for i, w in enumerate(
            "alors on arrive au bout de cette vidéo et je vous montre "
            "le résultat final des ventes qu on a faites aujourd hui".split()
        )
    ]
    transcript = Transcript(words=words, language="french", text="")
    declared_start, declared_end = 96.0, 108.0  # 12s, starts before the words
    arc = StoryArc(
        title="fin de vidéo",
        arc_type="continuous",
        segments=[
            ArcSegmentSpec(
                role="single",
                start=declared_start,
                end=declared_end,
                transcript_excerpt="le résultat final des ventes",
                why=None,
            )
        ],
        viral_reason="",
        estimated_retention=80,
        continuity_risk="low",
        suggested_hook=None,
    )

    anchored, _report = anchor_arcs_to_transcript([arc], transcript)
    seg = anchored[0].segments[0]
    kept = seg.end - seg.start
    assert kept >= (declared_end - declared_start) - 0.5, (
        f"clip collapsed to {kept:.2f}s instead of keeping ~12s"
    )
