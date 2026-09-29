from dataclasses import replace

import pytest

from app.models import Transcript, TranscriptSentence, TranscriptWord
from app.pipeline.edl import EditIntentPlan, EditShotIntent, FramingIntent, compile_edit_intent
from app.pipeline.edl_captions import (
    CaptionSafeZone,
    EDLCaptionError,
    build_caption_plan,
    render_ass,
    sentence_word_ids,
    write_ass_for_edl,
)


def _transcript() -> Transcript:
    words = [
        TranscriptWord("Début", 0.00, 0.30),
        TranscriptWord("calme", 0.31, 0.66),
        TranscriptWord("maintenant", 0.67, 1.05),
        TranscriptWord("preuve", 10.00, 10.35),
        TranscriptWord("très", 10.36, 10.62),
        TranscriptWord("forte", 10.63, 11.02),
    ]
    return Transcript(text=" ".join(word.word for word in words), words=words)


def _edl():
    transcript = _transcript()
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Open on the proof, explain, then replay the payoff.",
        shots=(
            EditShotIntent(
                shot_id="hook",
                role="hook",
                from_word_id=3,
                to_word_id=5,
                framing=FramingIntent("locked_face"),
                caption_theme="hook_bold",
                speed=1.25,
            ),
            EditShotIntent(
                shot_id="setup",
                role="setup",
                from_word_id=0,
                to_word_id=2,
                framing=FramingIntent("screen_focus"),
                caption_theme="proof_clean",
            ),
            EditShotIntent(
                shot_id="replay",
                role="payoff",
                from_word_id=3,
                to_word_id=5,
                framing=FramingIntent("follow_primary_face"),
                caption_theme="reaction_pop",
            ),
            EditShotIntent(
                shot_id="silent_caption_choice",
                role="cta",
                from_word_id=0,
                to_word_id=1,
                caption_theme="none",
            ),
        ),
    )
    return compile_edit_intent(plan, transcript, source_duration_ms=20_000), transcript


def _dialogues(ass: str) -> list[str]:
    return [line for line in ass.splitlines() if line.startswith("Dialogue:")]


def _dialogue_text(line: str) -> str:
    return line.split(",", 9)[9]


def _ass_time(milliseconds: int) -> str:
    centiseconds = milliseconds // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, seconds = divmod(remainder, 6_000)
    return f"{hours}:{minutes:02d}:{seconds // 100:02d}.{seconds % 100:02d}"


def test_plan_uses_compiled_occurrences_for_non_linear_replay_and_speed() -> None:
    edl, transcript = _edl()
    plan = build_caption_plan(edl, transcript)
    rendered_words = [word for cue in plan.cues for word in cue.words]

    # Timeline order follows EDL shots, not source transcript chronology.
    assert [word.text for word in rendered_words] == [
        "preuve",
        "très",
        "forte",
        "Début",
        "calme",
        "maintenant",
        "preuve",
        "très",
        "forte",
    ]
    assert rendered_words[0].timeline_in_ms == edl.shots[0].word_occurrences[0].timeline_in_ms
    assert rendered_words[1].timeline_out_ms == edl.shots[0].word_occurrences[1].timeline_out_ms
    assert rendered_words[0].timeline_in_ms < rendered_words[3].timeline_in_ms
    # Replay is a second occurrence, never de-duplicated by source word_id.
    proof_occurrences = [word for word in rendered_words if word.word_id == 3]
    assert len(proof_occurrences) == 2
    assert proof_occurrences[0].occurrence_id != proof_occurrences[1].occurrence_id


def test_ass_event_timing_is_taken_directly_from_each_compiled_word_occurrence() -> None:
    edl, transcript = _edl()
    plan = build_caption_plan(edl, transcript)
    hook = next(cue for cue in plan.cues if cue.shot_id == "hook")
    hook_lines = [line for line in _dialogues(render_ass(plan)) if ",CFHook," in line]
    lines = hook_lines[: len(hook.words)]

    assert len(lines) == len(hook.words)
    for index, (line, word) in enumerate(zip(lines, hook.words, strict=True)):
        fields = line.split(",", 9)
        expected_end = (
            hook.words[index + 1].timeline_in_ms
            if index + 1 < len(hook.words)
            else word.timeline_out_ms
        )
        assert fields[1] == _ass_time(word.timeline_in_ms)
        assert fields[2] == _ass_time(expected_end)


def test_ass_preserves_transcript_words_and_uses_closed_theme_styles(tmp_path) -> None:
    edl, transcript = _edl()
    plan = build_caption_plan(edl, transcript)
    ass = render_ass(plan)
    lines = _dialogues(ass)

    assert "Style: CFHook," in ass
    assert "Style: CFStandard," in ass
    assert "Style: CFProof," in ass
    assert "Style: CFReaction," in ass
    assert any(",CFHook," in line and "preuve" in _dialogue_text(line) for line in lines)
    assert any(",CFProof," in line and "Début" in _dialogue_text(line) for line in lines)
    assert any(",CFReaction," in line and "forte" in _dialogue_text(line) for line in lines)
    # The source words are used exactly rather than generated/paraphrased text.
    assert [word.text for cue in plan.cues if cue.shot_id == "setup" for word in cue.words] == [
        "Début",
        "calme",
        "maintenant",
    ]
    # The `none` shot creates no Dialogue event.
    assert all("silent_caption_choice" not in line for line in lines)

    out = tmp_path / "edl.ass"
    assert write_ass_for_edl(plan, out_path=str(out)) is True
    assert out.read_text(encoding="utf-8") == ass


def test_framing_fallback_and_trusted_safe_zone_choose_caption_margin() -> None:
    edl, transcript = _edl()
    plan = build_caption_plan(
        edl,
        transcript,
        safe_zones={"hook": CaptionSafeZone("upper")},
    )
    by_shot = {cue.shot_id: cue.margin_v for cue in plan.cues}

    assert by_shot["hook"] == 1_050  # explicit trusted vision safe zone
    assert by_shot["setup"] == 1_050  # screen_focus fallback
    assert by_shot["replay"] == 400  # face-follow fallback


def test_groups_break_on_pause_and_never_cross_an_edl_shot() -> None:
    transcript = Transcript(
        text="one two three four",
        words=[
            TranscriptWord("one", 0.0, 0.2),
            TranscriptWord("two", 0.21, 0.4),
            TranscriptWord("three", 1.0, 1.2),
            TranscriptWord("four", 1.21, 1.4),
        ],
    )
    plan = EditIntentPlan(
        "2.0",
        "Pause then a second shot.",
        (
            EditShotIntent("first", "hook", 0, 2, caption_theme="standard_karaoke"),
            EditShotIntent("second", "payoff", 3, 3, caption_theme="standard_karaoke"),
        ),
    )
    edl = compile_edit_intent(plan, transcript, source_duration_ms=5_000)
    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two"],
        ["three"],
        ["four"],
    ]
    assert [cue.shot_id for cue in captions.cues] == ["first", "first", "second"]


def test_groups_rebalance_a_single_word_tail_within_the_same_phrase() -> None:
    transcript = Transcript(
        text="one two three four five six seven",
        words=[
            TranscriptWord(word, index * 0.21, index * 0.21 + 0.20)
            for index, word in enumerate("one two three four five six seven".split())
        ],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "One uninterrupted phrase should use balanced caption cards.",
            (
                EditShotIntent(
                    "balanced",
                    "hook",
                    0,
                    6,
                    caption_theme="standard_karaoke",
                ),
            ),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two", "three"],
        ["four", "five"],
        ["six", "seven"],
    ]


def test_groups_do_not_cross_overlapping_asr_sentence_boundaries_even_under_max_words() -> None:
    transcript = Transcript(
        text="one two. three four five.",
        words=[
            TranscriptWord("one", 0.00, 0.10),
            TranscriptWord("two.", 0.11, 0.20),
            TranscriptWord("three", 0.21, 0.30),
            TranscriptWord("four", 0.31, 0.40),
            TranscriptWord("five.", 0.41, 0.50),
        ],
        # Segment starts overlap slightly in a normal verbose_json response.
        sentences=[
            TranscriptSentence("one two.", 0.00, 0.205),
            TranscriptSentence("three four five.", 0.195, 0.52),
        ],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "Two punctuated sentences are separate reading units.",
            (EditShotIntent("semantic", "hook", 0, 4, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    # standard_karaoke allows three words, but no cue may straddle `two.` → `three`.
    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two."],
        ["three", "four", "five."],
    ]


def test_sentence_mapping_does_not_steal_next_word_or_caption_empty_asr_placeholders() -> None:
    transcript = Transcript(
        text="des ventes Est ce qu'on gagne",
        words=[
            TranscriptWord("des", 0.00, 0.10),
            TranscriptWord("ventes", 0.10, 0.20),
            TranscriptWord("", 0.20, 0.22),
            # Its midpoint is exactly the preceding sentence end.  Midpoint
            # mapping used to steal this first word into the previous cue.
            TranscriptWord("Est", 0.22, 0.32),
            TranscriptWord("ce", 0.32, 0.34),
            TranscriptWord("qu'on", 0.34, 0.44),
            TranscriptWord("gagne", 0.44, 0.55),
        ],
        sentences=[
            TranscriptSentence("des ventes.", 0.00, 0.27),
            TranscriptSentence("Est-ce qu'on gagne ?", 0.26, 0.56),
        ],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "A boundary may not create a one-word orphan or a blank caption.",
            (EditShotIntent("question", "hook", 0, 6, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["des", "ventes"],
        ["Est", "ce"],
        ["qu'on", "gagne"],
    ]
    # The same mapper consumed by reflex QC assigns the straddling ``Est`` to
    # the second sentence; midpoint mapping used to steal it into the first.
    assert sentence_word_ids(transcript) == (0, 0, None, 1, 1, 1, 1)


def test_stale_sentence_segment_cannot_force_a_caption_boundary_before_unmapped_tail() -> None:
    transcript = Transcript(
        text="one two three",
        words=[
            TranscriptWord("one", 0.00, 0.10),
            TranscriptWord("two", 0.11, 0.20),
            TranscriptWord("three", 0.21, 0.32),
        ],
        # This older partial ASR segment does not cover the later transcript
        # tail. It may map its own words, but cannot force a semantic break.
        sentences=[TranscriptSentence("one two.", 0.00, 0.21)],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "Stale sentence metadata must fall back to timing-safe grouping.",
            (EditShotIntent("stale", "hook", 0, 2, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert sentence_word_ids(transcript) == (0, 0, None)
    assert [[word.text for word in cue.words] for cue in captions.cues] == [["one", "two", "three"]]


def test_sentence_boundaries_apply_to_each_replay_using_compiled_output_occurrences() -> None:
    transcript = Transcript(
        text="one two. three four.",
        words=[
            TranscriptWord("one", 0.00, 0.10),
            TranscriptWord("two.", 0.11, 0.20),
            TranscriptWord("three", 0.21, 0.30),
            TranscriptWord("four.", 0.31, 0.40),
        ],
        sentences=[
            TranscriptSentence("one two.", 0.00, 0.205),
            TranscriptSentence("three four.", 0.195, 0.42),
        ],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "Replay the same two sentence units at a different speed.",
            (
                EditShotIntent(
                    "first_pass",
                    "hook",
                    0,
                    3,
                    caption_theme="standard_karaoke",
                    speed=1.25,
                ),
                EditShotIntent(
                    "replay",
                    "payoff",
                    0,
                    3,
                    caption_theme="standard_karaoke",
                    speed=0.75,
                ),
            ),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two."],
        ["three", "four."],
        ["one", "two."],
        ["three", "four."],
    ]
    first_replay_word = captions.cues[2].words[0]
    assert first_replay_word.word_id == 0
    assert first_replay_word.timeline_in_ms == edl.shots[1].word_occurrences[0].timeline_in_ms
    assert first_replay_word.timeline_in_ms > captions.cues[1].timeline_out_ms


def test_without_sentences_keeps_the_existing_pause_aware_balancing_behaviour() -> None:
    transcript = Transcript(
        text="one two three four",
        words=[
            TranscriptWord("one", 0.00, 0.10),
            TranscriptWord("two", 0.11, 0.20),
            TranscriptWord("three", 0.21, 0.30),
            TranscriptWord("four", 0.31, 0.40),
        ],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "No sentence metadata retains the established cue balancer.",
            (EditShotIntent("fallback", "hook", 0, 3, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert transcript.sentences == []
    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two"],
        ["three", "four"],
    ]


def test_a_long_asr_sentence_still_uses_balanced_cues_within_that_sentence() -> None:
    transcript = Transcript(
        text="one two three four five six seven",
        words=[
            TranscriptWord(word, index * 0.21, index * 0.21 + 0.20)
            for index, word in enumerate("one two three four five six seven".split())
        ],
        sentences=[TranscriptSentence("one two three four five six seven.", 0.00, 1.50)],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "A long semantic unit should not leave a one-word caption tail.",
            (EditShotIntent("long_sentence", "hook", 0, 6, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two", "three"],
        ["four", "five"],
        ["six", "seven"],
    ]


def test_unmappable_sentences_do_not_invent_a_caption_boundary() -> None:
    transcript = Transcript(
        text="one two three four",
        words=[
            TranscriptWord("one", 0.00, 0.10),
            TranscriptWord("two", 0.11, 0.20),
            TranscriptWord("three", 0.21, 0.30),
            TranscriptWord("four", 0.31, 0.40),
        ],
        sentences=[TranscriptSentence("stale ASR segment.", 10.00, 11.00)],
    )
    edl = compile_edit_intent(
        EditIntentPlan(
            "2.0",
            "Stale sentence metadata cannot create a fictitious output cue.",
            (EditShotIntent("unmappable", "hook", 0, 3, caption_theme="standard_karaoke"),),
        ),
        transcript,
        source_duration_ms=5_000,
    )

    captions = build_caption_plan(edl, transcript)

    assert [[word.text for word in cue.words] for cue in captions.cues] == [
        ["one", "two"],
        ["three", "four"],
    ]


def test_rejects_handcrafted_occurrence_that_is_not_a_positive_final_timeline_interval() -> None:
    edl, transcript = _edl()
    invalid_occurrence = replace(edl.shots[0].word_occurrences[0], timeline_out_ms=0)
    invalid_shot = replace(
        edl.shots[0], word_occurrences=(invalid_occurrence, *edl.shots[0].word_occurrences[1:])
    )
    broken = replace(edl, shots=(invalid_shot, *edl.shots[1:]))

    with pytest.raises(EDLCaptionError, match="invalid output timing"):
        build_caption_plan(broken, transcript)


def test_all_none_themes_produce_an_empty_plan_and_no_file(tmp_path) -> None:
    edl, transcript = _edl()
    none_shots = tuple(replace(shot, caption_theme="none") for shot in edl.shots)
    silent = replace(edl, shots=none_shots)
    plan = build_caption_plan(silent, transcript)
    out = tmp_path / "no_captions.ass"

    assert plan.cues == ()
    assert write_ass_for_edl(plan, out_path=str(out)) is False
    assert not out.exists()
