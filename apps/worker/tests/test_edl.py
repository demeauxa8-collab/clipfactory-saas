import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.edl import (
    EditIntentPlan,
    EditShotIntent,
    EDLValidationError,
    EffectIntent,
    FramingIntent,
    MusicIntent,
    SFXCueIntent,
    compile_edit_intent,
    plan_decode_islands,
)


def _transcript() -> Transcript:
    spans = [
        (0.00, 0.30, "alpha"),
        (0.31, 0.65, "bravo"),
        (0.66, 1.00, "charlie"),
        (1.01, 1.35, "delta"),
        (10.00, 10.30, "echo"),
        (10.31, 10.65, "foxtrot"),
        (10.66, 11.00, "golf"),
        (11.01, 11.35, "hotel"),
        (100.00, 100.30, "india"),
        (100.31, 100.65, "juliet"),
        (100.66, 101.00, "kilo"),
        (101.01, 101.35, "lima"),
    ]
    words = [TranscriptWord(word, start, end) for start, end, word in spans]
    return Transcript(text=" ".join(word.word for word in words), words=words)


def _shot(
    shot_id: str,
    start_word: int,
    end_word: int,
    *,
    role: str = "setup",
    effects: tuple[EffectIntent, ...] = (),
    speed: float = 1.0,
) -> EditShotIntent:
    return EditShotIntent(
        shot_id=shot_id,
        role=role,  # type: ignore[arg-type]
        from_word_id=start_word,
        to_word_id=end_word,
        framing=FramingIntent("locked_face", center_x=0.5, base_scale=1.0),
        effects=effects,
        speed=speed,
    )


def test_llm_can_reorder_reuse_and_speed_up_word_ranges() -> None:
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Open on the reaction, then explain, then replay proof.",
        shots=(
            _shot("reaction", 8, 11, role="hook"),
            _shot("setup", 0, 3),
            _shot("proof", 4, 7, role="proof", speed=1.25),
            _shot("proof_replay", 8, 9, role="payoff"),
        ),
    )
    edl = compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)

    assert [shot.shot_id for shot in edl.shots] == [
        "reaction",
        "setup",
        "proof",
        "proof_replay",
    ]
    assert edl.shots[0].source_in_ms == 100_000
    assert edl.shots[1].source_in_ms == 0
    # The timeline is frame-authoritative on purpose: 1470ms at 1.25x is 1176ms,
    # which is 35.28 frames at 30fps. Quantising to 35 whole frames (1167ms) is
    # what keeps captions, audio and mux duration on one clock — so the
    # expectation is the frame grid, not the naive division.
    speed_frames = max(1, round((edl.shots[2].source_duration_ms / 1.25) * edl.fps / 1000))
    assert edl.shots[2].timeline_duration_ms == round(speed_frames * 1000 / edl.fps)
    assert edl.shots[3].source_in_ms == 100_000  # source reuse is intentional
    assert all(
        current.timeline_out_ms == following.timeline_in_ms
        for current, following in zip(edl.shots, edl.shots[1:], strict=False)
    )


def test_decode_islands_group_source_near_shots_not_timeline_neighbours() -> None:
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Non-linear edit",
        shots=(
            _shot("late_a", 8, 9, role="hook"),
            _shot("early", 0, 3),
            _shot("late_b", 10, 11, role="payoff"),
        ),
    )
    edl = compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)

    assert len(edl.decode_islands) == 2
    assert edl.decode_islands[0].shot_ids == ("early",)
    assert edl.decode_islands[1].shot_ids == ("late_a", "late_b")
    assert edl.decode_islands[1].source_in_ms == 100_000
    assert edl.decode_islands[1].source_out_ms == 101_470


def test_music_and_sfx_are_resolved_against_compiled_timeline() -> None:
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Music under voice and one payoff hit.",
        shots=(
            _shot("setup", 0, 3),
            _shot("payoff", 4, 7, role="payoff"),
        ),
        music=(
            MusicIntent(
                asset_id="music_uplift_01",
                start_shot_id="setup",
                end_shot_id="payoff",
            ),
        ),
        sfx=(
            SFXCueIntent(
                asset_id="sfx_hit_soft_01",
                shot_id="payoff",
                at_word_id=6,
            ),
        ),
    )
    transcript = _transcript()
    edl = compile_edit_intent(plan, transcript, source_duration_ms=120_000)

    assert edl.music[0].timeline_in_ms == 0
    assert edl.music[0].timeline_out_ms == edl.duration_ms
    payoff = edl.shots[1]
    expected = payoff.timeline_in_ms + round(
        (round(transcript.words[6].start * 1000) - payoff.source_in_ms) / payoff.speed
    )
    assert edl.sfx[0].timeline_at_ms == expected


@pytest.mark.parametrize(
    ("shot", "message"),
    [
        (_shot("bad_range", 5, 4), "invalid inclusive word range"),
        (_shot("bad_speed", 0, 3, speed=2.1), "speed must be"),
        (
            EditShotIntent(
                shot_id="bad_framing",
                role="setup",
                from_word_id=0,
                to_word_id=3,
                framing=FramingIntent("raw_ffmpeg", 0.5, 1.0),  # type: ignore[arg-type]
            ),
            "unsupported framing",
        ),
        (
            _shot(
                "effect_outside",
                0,
                3,
                effects=(EffectIntent("punch_in", at_word_id=8),),
            ),
            "effect word",
        ),
    ],
)
def test_invalid_or_unbounded_llm_operations_are_rejected(
    shot: EditShotIntent, message: str
) -> None:
    plan = EditIntentPlan("2.0", "unsafe", (shot,))
    with pytest.raises(EDLValidationError, match=message):
        compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)


def test_asset_ids_are_catalogue_ids_not_paths_or_urls() -> None:
    plan = EditIntentPlan(
        "2.0",
        "unsafe asset",
        (_shot("setup", 0, 3),),
        music=(MusicIntent(asset_id="../../private/song.mp3"),),
    )
    with pytest.raises(EDLValidationError, match="catalogue-safe ID"):
        compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)


def test_effect_density_has_a_duration_based_budget() -> None:
    effects = (
        EffectIntent("punch_in", at_word_id=0),
        EffectIntent("flash", at_word_id=1),
    )
    plan = EditIntentPlan(
        "2.0",
        "too noisy",
        (_shot("short", 0, 3, effects=effects),),
    )
    with pytest.raises(EDLValidationError, match="effect budget exceeded"):
        compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)


def test_decode_island_arguments_are_validated() -> None:
    with pytest.raises(ValueError, match="positive"):
        plan_decode_islands((), max_gap_ms=-1)


def test_verbatim_anchors_handle_apostrophes_without_shifting_word_ids() -> None:
    transcript = Transcript(
        text="J'ai seulement un euro maintenant",
        words=[
            TranscriptWord("J'ai", 0.0, 0.25),
            TranscriptWord("seulement", 0.26, 0.60),
            TranscriptWord("un", 0.61, 0.72),
            TranscriptWord("euro", 0.73, 0.95),
            TranscriptWord("maintenant", 0.96, 1.30),
        ],
    )
    plan = EditIntentPlan(
        "2.0",
        "Keep the exact claim.",
        (
            EditShotIntent(
                shot_id="claim",
                role="hook",
                from_word_id=0,
                to_word_id=3,
                start_anchor="J'ai seulement",
                end_anchor="un euro",
            ),
        ),
    )

    edl = compile_edit_intent(plan, transcript, source_duration_ms=2_000)

    assert edl.shots[0].from_word_id == 0
    assert edl.shots[0].to_word_id == 3


def test_runtime_role_outside_closed_catalogue_is_rejected() -> None:
    plan = EditIntentPlan(
        "2.0",
        "Unsafe role",
        (_shot("bad_role", 0, 3, role="execute_shell"),),
    )
    with pytest.raises(EDLValidationError, match="unsupported role"):
        compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)
