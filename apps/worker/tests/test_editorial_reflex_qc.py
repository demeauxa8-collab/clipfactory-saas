from dataclasses import replace

import pytest

from app.models import Transcript, TranscriptSentence, TranscriptWord
from app.pipeline.editorial_beats import (
    AudioBeat,
    BeatEdge,
    EditorialBeat,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    VisualFocusRegion,
)
from app.pipeline.editorial_reflex_qc import (
    EditorialReflexPolicy,
    evaluate_editorial_reflex_qc,
)
from app.pipeline.edl import (
    EditIntentPlan,
    EditScope,
    EditShotIntent,
    FramingIntent,
    FramingRegion,
    InclusiveWordRange,
    compile_edit_intent,
)


def _transcript() -> Transcript:
    words = [
        TranscriptWord("Pourquoi", 0.0, 0.35),
        TranscriptWord("ça", 0.35, 0.55),
        TranscriptWord("marche", 0.55, 0.95),
        TranscriptWord("voici", 1.7, 2.0),
        TranscriptWord("la", 2.0, 2.15),
        TranscriptWord("preuve", 2.15, 2.6),
        TranscriptWord("cent", 2.6, 2.95),
        TranscriptWord("euros", 2.95, 3.4),
    ]
    return Transcript(
        text="Pourquoi ça marche voici la preuve cent euros",
        words=words,
        sentences=[
            TranscriptSentence("Pourquoi ça marche ?", 0.0, 0.95),
            TranscriptSentence("Voici la preuve cent euros.", 1.7, 3.4),
        ],
    )


def _graph(
    *,
    first_range: InclusiveWordRange | None = None,
    second_range: InclusiveWordRange | None = None,
    first_framings: tuple[str, ...] = ("source_safe", "locked_face"),
    second_framings: tuple[str, ...] = (
        "source_safe",
        "fit_blur",
        "screen_focus",
    ),
    relation: str = "proves",
    semantic_continuity: str = "continuous",
    dramatic_pause: bool = False,
    readable_screen: bool = True,
    screen_roi: bool = True,
    same_visual: bool = False,
) -> EditorialBeatGraph:
    first_range = first_range or InclusiveWordRange(0, 2)
    second_range = second_range or InclusiveWordRange(3, 7)
    moments = (
        SourceMoment("moment_00", first_range, 0, 950, "claim"),
        SourceMoment(
            "moment_01",
            second_range,
            1_700,
            3_400,
            "proof",
            "none" if same_visual else "visible",
        ),
    )
    focus = VisualFocusRegion(0.1, 0.1, 0.8, 0.7) if screen_roi else None
    first_visual_id = "visual_shared" if same_visual else "visual_face"
    second_visual_id = "visual_shared_2" if same_visual else "visual_screen"
    visuals = (
        VisualBeat(
            first_visual_id,
            "event_shared" if same_visual else "event_face",
            0,
            1_900 if same_visual else 950,
            "talking_head",
            "primary",
            "none",
            "still",
            "lower",
            90,
            None,
            "verified_candidate",
        ),
        VisualBeat(
            second_visual_id,
            "event_shared" if same_visual else "event_screen",
            900 if same_visual else 1_700,
            3_400,
            "talking_head" if same_visual else "screen_proof",
            "primary" if same_visual else "none",
            "none" if same_visual else ("readable" if readable_screen else "unknown"),
            "still",
            "lower" if same_visual else "upper",
            90,
            None if same_visual else focus,
            "verified_candidate",
        ),
    )
    audio = (
        (
            AudioBeat("pause_00", 950, 1_700, "dramatic_pause", 2, 3)
            if dramatic_pause
            else AudioBeat("pause_00", 950, 1_700, "kept_pause", 2, 3)
        ),
    )
    beats = (
        EditorialBeat(
            "beat_00",
            "moment_00",
            (first_visual_id,),
            (),
            "hook",
            first_framings,
        ),
        EditorialBeat(
            "beat_01",
            "moment_01",
            (second_visual_id,),
            (),
            "prove",
            second_framings,
        ),
    )
    return EditorialBeatGraph(
        "1.0",
        8,
        EditScope((InclusiveWordRange(0, 7),)),
        moments,
        visuals,
        audio,
        beats,
        (
            BeatEdge(
                "edge_00",
                "beat_00",
                "beat_01",
                relation,  # type: ignore[arg-type]
                semantic_continuity,  # type: ignore[arg-type]
                "scene_change",
                "pause" if dramatic_pause else "unknown",
            ),
        ),
    )


def _edl(
    *,
    first_range: tuple[int, int] = (0, 2),
    second_range: tuple[int, int] = (3, 7),
    first_transition: str = "hard_cut",
    first_framing: FramingIntent | None = None,
    second_framing: FramingIntent | None = None,
    second_speed: float = 1.0,
):
    first_framing = first_framing or FramingIntent("locked_face", 0.5, 1.1)
    second_framing = second_framing or FramingIntent(
        "screen_focus",
        0.5,
        1.0,
        FramingRegion(0.1, 0.1, 0.8, 0.7),
    )
    plan = EditIntentPlan(
        "2.0",
        "claim then proof",
        (
            EditShotIntent(
                "claim",
                "hook",
                *first_range,
                framing=first_framing,
                transition_out=first_transition,  # type: ignore[arg-type]
                post_roll_ms=0,
            ),
            EditShotIntent(
                "proof",
                "proof",
                *second_range,
                framing=second_framing,
                speed=second_speed,
                post_roll_ms=0,
            ),
        ),
    )
    return compile_edit_intent(plan, _transcript(), source_duration_ms=4_000)


def _codes(report) -> set[str]:
    return {item.code for item in report.findings}


def test_passes_a_fully_grounded_edit_and_returns_stable_mappings() -> None:
    report = evaluate_editorial_reflex_qc(_edl(), _graph(), transcript=_transcript())

    assert report.status == "pass"
    assert report.findings == ()
    assert [(item.shot_id, item.moment_id, item.beat_id) for item in report.shot_mappings] == [
        ("claim", "moment_00", "beat_00"),
        ("proof", "moment_01", "beat_01"),
    ]


@pytest.mark.parametrize(
    "graph, expected",
    [
        (_graph(first_range=InclusiveWordRange(0, 1)), "shot_outside_source_moment"),
        (
            replace(
                _graph(),
                source_moments=(
                    *_graph().source_moments,
                    SourceMoment("moment_extra", InclusiveWordRange(0, 2), 0, 950, "claim"),
                ),
                editorial_beats=(
                    *_graph().editorial_beats,
                    EditorialBeat(
                        "beat_extra",
                        "moment_extra",
                        ("visual_face",),
                        (),
                        "hook",
                        ("source_safe", "locked_face"),
                    ),
                ),
            ),
            "ambiguous_source_moment",
        ),
    ],
)
def test_rejects_shots_without_exactly_one_containing_source_moment(
    graph: EditorialBeatGraph, expected: str
) -> None:
    report = evaluate_editorial_reflex_qc(_edl(), graph)
    assert report.status == "reject"
    assert expected in _codes(report)


def test_rejects_framing_outside_graph_controls() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(first_framing=FramingIntent("locked_face", 0.5, 1.0)),
        _graph(first_framings=("source_safe",)),
    )
    assert report.status == "reject"
    assert "framing_not_available" in _codes(report)


def test_rejects_screen_focus_without_graph_backed_readability_and_roi() -> None:
    graph = _graph(
        readable_screen=False,
        screen_roi=False,
        second_framings=("source_safe", "fit_blur"),
    )
    report = evaluate_editorial_reflex_qc(_edl(), graph)
    assert report.status == "reject"
    assert "screen_focus_without_unique_readable_roi" in _codes(report)


def test_rejects_screen_focus_when_compiled_roi_does_not_match_graph_evidence() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(
            second_framing=FramingIntent(
                "screen_focus",
                screen_region=FramingRegion(0.2, 0.1, 0.7, 0.7),
            )
        ),
        _graph(),
    )

    assert report.status == "reject"
    assert "screen_focus_region_mismatch" in _codes(report)


def test_short_proof_and_visible_screen_hold_are_configurable_fallbacks() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(second_speed=2.0),
        _graph(),
        policy=EditorialReflexPolicy(
            min_proof_hold_ms=1_200,
            min_readable_screen_hold_ms=1_000,
        ),
    )
    assert report.status == "pass_with_fallback"
    assert {"proof_hold_too_short", "readable_screen_hold_too_short"} <= _codes(report)


@pytest.mark.parametrize(
    "transition, relation, semantic_continuity, expected_status",
    [
        ("reveal", "proves", "continuous", "pass"),
        ("reveal", "continues", "continuous", "pass_with_fallback"),
        ("contrast", "contrasts", "continuous", "pass"),
        ("contrast", "proves", "continuous", "pass_with_fallback"),
        ("time_jump", "continues", "unknown", "pass"),
        ("time_jump", "continues", "continuous", "pass_with_fallback"),
        ("hard_impact", "continues", "continuous", "pass"),
    ],
)
def test_stylized_transitions_require_compatible_directed_edges(
    transition: str,
    relation: str,
    semantic_continuity: str,
    expected_status: str,
) -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(first_transition=transition),
        _graph(relation=relation, semantic_continuity=semantic_continuity),
    )
    assert report.status == expected_status
    assert ("unmotivated_stylized_transition" in _codes(report)) is (
        expected_status == "pass_with_fallback"
    )


def test_unknown_or_missing_transition_evidence_falls_back_to_hard_cut() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(first_transition="reveal"),
        replace(_graph(), edges=()),
    )
    assert report.status == "pass_with_fallback"
    assert "unmotivated_stylized_transition" in _codes(report)


def test_flags_same_scale_jump_only_for_same_talking_head_and_short_source_joint() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(
            first_framing=FramingIntent("locked_face", 0.5, 1.1),
            second_framing=FramingIntent("locked_face", 0.51, 1.1),
        ),
        _graph(
            same_visual=True,
            second_framings=("source_safe", "locked_face"),
        ),
    )
    assert report.status == "pass_with_fallback"
    assert "same_scale_jump" in _codes(report)


def test_dramatic_pause_edges_cannot_be_split_across_a_joint() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(),
        _graph(dramatic_pause=True),
    )
    assert report.status == "reject"
    assert "dramatic_pause_split" in _codes(report)


def test_dramatic_pause_split_cannot_be_hidden_by_an_inserted_replay() -> None:
    base = _edl()
    inserted = replace(
        base.shots[0],
        shot_id="inserted",
        timeline_in_ms=base.shots[0].timeline_out_ms,
        timeline_out_ms=base.shots[0].timeline_out_ms * 2,
        timeline_in_frame=base.shots[0].timeline_out_frame,
        timeline_out_frame=base.shots[0].timeline_out_frame * 2,
        word_occurrences=(),
    )
    inserted_frames = inserted.timeline_out_frame - inserted.timeline_in_frame
    shifted_proof = replace(
        base.shots[1],
        timeline_in_ms=base.shots[1].timeline_in_ms + inserted.timeline_duration_ms,
        timeline_out_ms=base.shots[1].timeline_out_ms + inserted.timeline_duration_ms,
        timeline_in_frame=base.shots[1].timeline_in_frame + inserted_frames,
        timeline_out_frame=base.shots[1].timeline_out_frame + inserted_frames,
    )
    edited = replace(
        base,
        shots=(base.shots[0], inserted, shifted_proof),
        duration_ms=shifted_proof.timeline_out_ms,
        duration_frames=shifted_proof.timeline_out_frame,
    )

    report = evaluate_editorial_reflex_qc(edited, _graph(dramatic_pause=True))
    assert report.status == "reject"
    assert "dramatic_pause_split" in _codes(report)


def test_qc_rejects_forged_unused_moment_time_and_neighboring_speech_roll() -> None:
    graph = _graph()
    forged = replace(
        graph,
        source_moments=(
            graph.source_moments[0],
            replace(graph.source_moments[1], source_in_ms=1_650),
        ),
    )
    report = evaluate_editorial_reflex_qc(
        _edl(first_range=(0, 2), second_range=(0, 2)),
        forged,
        transcript=_transcript(),
    )
    assert report.status == "reject"
    assert "forged_source_moment_bounds" in _codes(report)

    base = _edl()
    leaked = replace(base.shots[0], source_out_ms=1_800)
    report = evaluate_editorial_reflex_qc(
        replace(base, shots=(leaked, base.shots[1])),
        graph,
        transcript=_transcript(),
    )
    assert report.status == "reject"
    assert "source_window_leaks_neighboring_speech" in _codes(report)


def test_sentence_evidence_only_flags_genuine_mid_thought_boundaries() -> None:
    report = evaluate_editorial_reflex_qc(
        _edl(first_range=(1, 2), second_range=(3, 6)),
        _graph(
            first_range=InclusiveWordRange(0, 2),
            second_range=InclusiveWordRange(3, 7),
        ),
        transcript=_transcript(),
    )
    assert report.status == "pass_with_fallback"
    assert "mid_thought_cut" in _codes(report)


def test_ambiguous_asr_sentence_evidence_is_ignored_conservatively() -> None:
    transcript = _transcript()
    transcript.sentences.append(TranscriptSentence("overlap", 0.2, 0.8))
    report = evaluate_editorial_reflex_qc(
        _edl(),
        _graph(),
        transcript=transcript,
    )
    assert report.status == "pass"
    assert "mid_thought_cut" not in _codes(report)


def test_invalid_persisted_graph_and_transcript_mismatch_are_machine_readable_rejects() -> None:
    invalid = replace(_graph(), schema_version="9.0")
    report = evaluate_editorial_reflex_qc(_edl(), invalid)
    assert report.status == "reject"
    assert _codes(report) == {"invalid_beat_graph"}

    transcript = _transcript()
    transcript.words.pop()
    report = evaluate_editorial_reflex_qc(_edl(), _graph(), transcript=transcript)
    assert report.status == "reject"
    assert _codes(report) == {"transcript_graph_mismatch"}


def test_invalid_policy_is_a_configuration_error() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        evaluate_editorial_reflex_qc(
            _edl(),
            _graph(),
            policy=EditorialReflexPolicy(min_proof_hold_ms=-1),
        )
