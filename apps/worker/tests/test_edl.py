import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.edl import (
    EditIntentPlan,
    EditScope,
    EditShotIntent,
    EDLValidationError,
    EffectIntent,
    FramingIntent,
    InclusiveWordRange,
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
    expected_frames = round(edl.shots[2].source_duration_ms / 1.25 * edl.fps / 1000)
    assert edl.shots[2].timeline_duration_ms == round(expected_frames * 1000 / edl.fps)
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
    expected = next(
        occurrence.timeline_in_ms
        for occurrence in payoff.word_occurrences
        if occurrence.word_id == 6
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


def test_anchor_cannot_claim_words_outside_its_shot() -> None:
    transcript = Transcript(
        text="alpha bravo charlie",
        words=[
            TranscriptWord("alpha", 0.0, 0.3),
            TranscriptWord("bravo", 0.31, 0.6),
            TranscriptWord("charlie", 0.61, 0.9),
        ],
    )
    plan = EditIntentPlan(
        "2.0",
        "Unsafe anchors",
        (
            EditShotIntent(
                shot_id="middle",
                role="hook",
                from_word_id=1,
                to_word_id=1,
                start_anchor="bravo charlie",
                end_anchor="bravo",
            ),
        ),
    )

    with pytest.raises(EDLValidationError, match="start_anchor does not match"):
        compile_edit_intent(plan, transcript, source_duration_ms=2_000)


def test_scope_allows_reorder_inside_ranges_and_rejects_global_transcript_escape() -> None:
    scope = EditScope(
        allowed_word_ranges=(InclusiveWordRange(4, 11),),
        protected_word_ranges=(InclusiveWordRange(6, 7),),
        required_word_ranges=(InclusiveWordRange(10, 11),),
    )
    valid = EditIntentPlan(
        "2.0",
        "Reorder only within explicit authority.",
        (
            _shot("payoff", 10, 11, role="hook"),
            _shot("context", 4, 7, role="payoff"),
        ),
    )

    compiled = compile_edit_intent(
        valid,
        _transcript(),
        source_duration_ms=120_000,
        edit_scope=scope,
    )
    assert [shot.from_word_id for shot in compiled.shots] == [10, 4]

    escaped = EditIntentPlan(
        "2.0",
        "Escape",
        (_shot("outside", 0, 3, role="hook"),),
    )
    with pytest.raises(EDLValidationError, match="outside the allowed edit scope"):
        compile_edit_intent(
            escaped,
            _transcript(),
            source_duration_ms=120_000,
            edit_scope=scope,
        )


def test_scope_rejects_partial_protected_span_and_missing_required_span() -> None:
    transcript = _transcript()
    scope = EditScope(
        allowed_word_ranges=(InclusiveWordRange(4, 11),),
        protected_word_ranges=(InclusiveWordRange(6, 7),),
        required_word_ranges=(InclusiveWordRange(10, 11),),
    )
    cuts_protected = EditIntentPlan(
        "2.0",
        "Bad cut",
        (_shot("partial", 4, 6, role="hook"),),
    )
    with pytest.raises(EDLValidationError, match="cuts through protected"):
        compile_edit_intent(
            cuts_protected,
            transcript,
            source_duration_ms=120_000,
            edit_scope=scope,
        )

    misses_required = EditIntentPlan(
        "2.0",
        "Missing payoff",
        (_shot("context", 4, 7, role="hook"),),
    )
    with pytest.raises(EDLValidationError, match="required word range is missing"):
        compile_edit_intent(
            misses_required,
            transcript,
            source_duration_ms=120_000,
            edit_scope=scope,
        )


def test_duration_policy_and_catalogue_allowlists_are_authoritative() -> None:
    plan = EditIntentPlan(
        "2.0",
        "Known assets only",
        (_shot("short", 0, 3, role="hook"),),
        music=(MusicIntent(asset_id="music_known_01"),),
        sfx=(SFXCueIntent("sfx_known_01", "short", 1),),
    )
    with pytest.raises(EDLValidationError, match="outside target"):
        compile_edit_intent(
            plan,
            _transcript(),
            source_duration_ms=120_000,
            target_duration_seconds=20,
            allowed_music_asset_ids={"music_known_01"},
            allowed_sfx_asset_ids={"sfx_known_01"},
        )

    with pytest.raises(EDLValidationError, match="unknown music asset_id"):
        compile_edit_intent(
            plan,
            _transcript(),
            source_duration_ms=120_000,
            allowed_music_asset_ids=set(),
            allowed_sfx_asset_ids={"sfx_known_01"},
        )


def test_replayed_words_have_distinct_frame_aligned_occurrences() -> None:
    plan = EditIntentPlan(
        "2.0",
        "Replay a source moment.",
        (
            _shot("first", 4, 7, role="hook", speed=1.25),
            _shot("replay", 4, 7, role="payoff", speed=1.25),
        ),
    )

    edl = compile_edit_intent(plan, _transcript(), source_duration_ms=120_000)

    assert edl.duration_frames == edl.shots[-1].timeline_out_frame
    assert all(
        shot.timeline_in_ms == round(shot.timeline_in_frame * 1000 / edl.fps)
        and shot.timeline_out_ms == round(shot.timeline_out_frame * 1000 / edl.fps)
        for shot in edl.shots
    )
    assert edl.shots[0].word_occurrences[0].word_id == 4
    assert edl.shots[1].word_occurrences[0].word_id == 4
    assert (
        edl.shots[0].word_occurrences[0].occurrence_id
        != edl.shots[1].word_occurrences[0].occurrence_id
    )


def test_zero_duration_asr_words_get_one_frame_occurrences() -> None:
    transcript = Transcript(
        text="Moi c'est précis",
        words=[
            TranscriptWord("Moi", 1.0, 1.0),
            TranscriptWord("c'est", 1.0, 1.08),
            TranscriptWord("précis", 1.09, 1.38),
        ],
    )
    plan = EditIntentPlan(
        "2.0",
        "Keep every ASR word renderable.",
        (_shot("hook", 0, 2, role="hook"),),
    )

    edl = compile_edit_intent(plan, transcript, source_duration_ms=2_000)

    assert all(
        occurrence.timeline_out_frame > occurrence.timeline_in_frame
        and occurrence.timeline_in_ms
        == round(occurrence.timeline_in_frame * 1000 / edl.fps)
        and occurrence.timeline_out_ms
        == round(occurrence.timeline_out_frame * 1000 / edl.fps)
        for occurrence in edl.shots[0].word_occurrences
    )
