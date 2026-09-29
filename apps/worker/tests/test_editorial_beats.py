import json
from dataclasses import replace

import pytest

from app.models import (
    MontageCandidate,
    MontageSegment,
    Transcript,
    TranscriptSentence,
    TranscriptWord,
    VideoEvent,
    VideoMap,
)
from app.pipeline.audio_map import AudioMap, SilenceInterval
from app.pipeline.editorial_beats import (
    BeatEdge,
    EditorialBeatError,
    VisualBeat,
    VisualFocusRegion,
    build_editorial_beat_graph,
    validate_editorial_beat_graph,
)
from app.pipeline.edl import EditScope, InclusiveWordRange


def _transcript() -> Transcript:
    words = [
        TranscriptWord("Voici", 0.0, 0.3),
        TranscriptWord("le", 0.3, 0.45),
        TranscriptWord("résultat", 0.45, 0.9),
        TranscriptWord("on", 2.0, 2.2),
        TranscriptWord("a", 2.2, 2.3),
        TranscriptWord("gagné", 2.3, 2.8),
        TranscriptWord("cent", 2.8, 3.1),
        TranscriptWord("euros", 3.1, 3.5),
    ]
    return Transcript(
        text="Voici le résultat on a gagné cent euros",
        words=words,
        sentences=[
            TranscriptSentence("Voici le résultat.", 0.0, 0.9),
            TranscriptSentence("On a gagné cent euros.", 2.0, 3.5),
        ],
    )


def _scope() -> EditScope:
    return EditScope(allowed_word_ranges=(InclusiveWordRange(0, 7),))


def _candidate() -> MontageCandidate:
    return MontageCandidate(
        title="Result",
        hook="Voici le résultat",
        segments=[
            MontageSegment("setup", 0.0, 0.9),
            MontageSegment("payoff", 2.0, 3.5),
        ],
        rationale="proof",
        score_total=80,
        score_breakdown={},
    )


def _video_map(*, proof: bool = True) -> VideoMap:
    events = [
        VideoEvent(
            "talk", 0.0, 1.1, "studio", "one person", [], "talking head", "intro", 65, "setup"
        ),
        VideoEvent(
            "proof",
            2.0,
            3.6,
            "desktop screen" if proof else "studio",
            "one person",
            ["dashboard"] if proof else [],
            "screen demonstration" if proof else "talking head",
            "result",
            95,
            "payoff",
        ),
    ]
    return VideoMap("result video", events)


def test_builds_evidence_backed_graph_with_overlapping_visual_events_and_pause() -> None:
    video = _video_map()
    # A second event deliberately overlaps the screen proof; the graph preserves
    # both observations instead of flattening unverified vision into one event.
    video.events.append(
        VideoEvent(
            "gesture", 2.4, 3.2, "studio", "one person", [], "reaction", "reaction", 70, "payoff"
        )
    )
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=video,
        audio_map=AudioMap(4.0, (SilenceInterval(0.92, 1.90),)),
        protected_pause_ranges=(InclusiveWordRange(2, 3),),
        readable_visual_event_ids={"proof"},
        verified_visual_event_ids={"talk", "proof", "gesture"},
        visual_focus_regions={"proof": VisualFocusRegion(0.1, 0.2, 0.7, 0.5)},
    )

    assert [item.moment_id for item in graph.source_moments] == ["moment_00", "moment_01"]
    assert [item.kind for item in graph.visual_beats] == [
        "talking_head",
        "screen_proof",
        "reaction",
    ]
    assert graph.audio_beats[0].kind == "dramatic_pause"
    assert graph.editorial_beats[1].available_framings == (
        "source_safe",
        "locked_face",
        "fit_blur",
        "screen_focus",
    )
    assert graph.edges[0].relation == "answers"
    assert graph.edges[0].visual_continuity == "scene_change"


def test_visible_proof_requirement_rejects_moment_without_qualifying_visual_evidence() -> None:
    with pytest.raises(EditorialBeatError, match="requires visible proof"):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=_scope(),
            candidate=_candidate(),
            video_map=_video_map(proof=False),
            proof_requirements={"moment_01": "visible"},
        )


def test_global_video_map_demo_cannot_satisfy_visible_proof_until_verified() -> None:
    video = _video_map(proof=False)
    video.events[1] = VideoEvent(
        "cheap_demo",
        2.0,
        3.6,
        "studio",
        "one person",
        [],
        "demo claim from coarse map",
        "result",
        0,
        "payoff",
    )
    with pytest.raises(EditorialBeatError, match="requires visible proof"):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=_scope(),
            candidate=_candidate(),
            video_map=video,
            proof_requirements={"moment_01": "visible"},
        )

    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=video,
        proof_requirements={"moment_01": "visible"},
        verified_visual_event_ids={"cheap_demo"},
    )
    demo = graph.visual_beats[1]
    assert demo.kind == "demo"
    assert demo.confidence == 0
    assert demo.provenance == "verified_candidate"


def test_unverified_global_talking_head_never_unlocks_locked_face() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
    )

    assert graph.visual_beats[0].face_state == "primary"
    assert graph.visual_beats[0].provenance == "video_map"
    assert graph.editorial_beats[0].available_framings == ("source_safe",)


def test_readable_screen_without_roi_never_unlocks_screen_focus() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        proof_requirements={"moment_01": "both"},
        readable_visual_event_ids={"proof"},
        verified_visual_event_ids={"proof"},
    )
    assert graph.source_moments[1].proof_requirement == "both"
    assert graph.editorial_beats[1].visual_ids == ("visual_001",)
    assert graph.editorial_beats[1].available_framings == ("source_safe", "fit_blur")


def test_readable_screen_with_trusted_roi_unlocks_screen_focus_and_serializes_it() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        readable_visual_event_ids={"proof"},
        verified_visual_event_ids={"proof"},
        visual_focus_regions={"proof": VisualFocusRegion(0.1, 0.2, 0.7, 0.5)},
    )

    assert graph.editorial_beats[1].available_framings == (
        "source_safe",
        "fit_blur",
        "screen_focus",
    )
    assert graph.to_prompt_payload()["visual_beats"][1]["focus_region"] == {
        "x": 0.1,
        "y": 0.2,
        "width": 0.7,
        "height": 0.5,
    }


def test_screen_proof_defaults_to_unknown_readability_and_never_unlocks_screen_focus() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        proof_requirements={"moment_01": "visible"},
        verified_visual_event_ids={"proof"},
    )

    proof = graph.visual_beats[1]
    assert proof.kind == "screen_proof"
    assert proof.screen_readability == "unknown"
    assert graph.editorial_beats[1].available_framings == ("source_safe", "fit_blur")


@pytest.mark.parametrize(
    "regions, message",
    [
        ({"proof": VisualFocusRegion(0.9, 0.2, 0.2, 0.5)}, "contained"),
        ({"proof": VisualFocusRegion(0.1, 0.2, 0.01, 0.5)}, "at least 0.05"),
        ({"missing": VisualFocusRegion(0.1, 0.2, 0.7, 0.5)}, "unknown"),
        ({"talk": VisualFocusRegion(0.1, 0.2, 0.7, 0.5)}, "not a screen"),
    ],
)
def test_focus_regions_must_be_valid_and_tied_to_known_screen_evidence(
    regions: dict[str, VisualFocusRegion], message: str
) -> None:
    with pytest.raises(EditorialBeatError, match=message):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=_scope(),
            candidate=_candidate(),
            video_map=_video_map(),
            verified_visual_event_ids=set(regions),
            visual_focus_regions=regions,
        )


def test_visual_evidence_without_a_video_map_is_rejected_instead_of_ignored() -> None:
    with pytest.raises(EditorialBeatError, match="requires a VideoMap"):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=_scope(),
            candidate=_candidate(),
            verified_visual_event_ids={"proof"},
        )


def test_validator_rejects_persisted_screen_focus_without_readable_roi() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        readable_visual_event_ids={"proof"},
        verified_visual_event_ids={"proof"},
    )
    altered = replace(
        graph,
        editorial_beats=(
            graph.editorial_beats[0],
            replace(
                graph.editorial_beats[1],
                available_framings=("source_safe", "fit_blur", "screen_focus"),
            ),
        ),
    )

    with pytest.raises(EditorialBeatError, match="screen_focus"):
        validate_editorial_beat_graph(altered)


def test_unknown_proof_requirement_and_scope_escape_are_rejected() -> None:
    with pytest.raises(EditorialBeatError, match="unknown moments"):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=_scope(),
            proof_requirements={"not_a_moment": "visible"},
        )
    with pytest.raises(EditorialBeatError, match="outside the explicitly authorised"):
        build_editorial_beat_graph(
            transcript=_transcript(),
            scope=EditScope((InclusiveWordRange(0, 2),)),
            candidate=_candidate(),
        )


def test_validator_rejects_unknown_beat_references_and_invalid_edges() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(), scope=_scope(), candidate=_candidate()
    )
    broken_beat = replace(graph.editorial_beats[0], visual_ids=("missing",))
    with pytest.raises(EditorialBeatError, match="unknown visual/audio"):
        validate_editorial_beat_graph(
            replace(graph, editorial_beats=(broken_beat, *graph.editorial_beats[1:]))
        )
    broken_edge = BeatEdge(
        "edge_bad", "beat_00", "missing", "continues", "continuous", "unknown", "unknown"
    )
    with pytest.raises(EditorialBeatError, match="unknown/self"):
        validate_editorial_beat_graph(replace(graph, edges=(broken_edge,)))


def test_prompt_payload_is_json_serialisable_and_uses_word_ids_not_raw_transcript() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(), scope=_scope(), candidate=_candidate(), video_map=_video_map()
    )
    payload = graph.to_prompt_payload()
    encoded = graph.to_prompt_json()

    assert json.loads(encoded) == payload
    assert payload["source_moments"][0]["word_range"] == {
        "from_word_id": "w_000000",
        "to_word_id": "w_000002",
    }
    assert "Voici le résultat" not in encoded


def test_validator_rejects_persisted_visual_proof_removed_after_build() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        proof_requirements={"moment_01": "visible"},
        verified_visual_event_ids={"proof"},
    )
    fake = VisualBeat(
        "visual_fake", "fake", 2000, 3500, "talking_head", "primary", "none", "still", "lower", 80
    )
    altered = replace(
        graph,
        visual_beats=(graph.visual_beats[0], fake),
        editorial_beats=(
            graph.editorial_beats[0],
            replace(graph.editorial_beats[1], visual_ids=("visual_fake",)),
        ),
    )
    with pytest.raises(EditorialBeatError, match="requires visible proof"):
        validate_editorial_beat_graph(altered)


def test_validator_rejects_persisted_evidence_outside_its_source_moment() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(), scope=_scope(), candidate=_candidate(), video_map=_video_map()
    )
    far_away = VisualBeat(
        "visual_far",
        "far",
        9_000,
        10_000,
        "screen_proof",
        "none",
        "unknown",
        "still",
        "unknown",
        80,
    )
    altered = replace(
        graph,
        visual_beats=(*graph.visual_beats, far_away),
        editorial_beats=(
            graph.editorial_beats[0],
            replace(graph.editorial_beats[1], visual_ids=("visual_far",)),
        ),
    )

    with pytest.raises(EditorialBeatError, match="outside its source moment"):
        validate_editorial_beat_graph(altered)


def test_validator_rejects_unverified_persisted_readability_and_unknown_provenance() -> None:
    graph = build_editorial_beat_graph(
        transcript=_transcript(),
        scope=_scope(),
        candidate=_candidate(),
        video_map=_video_map(),
        verified_visual_event_ids={"proof"},
    )
    readable_without_verification = replace(
        graph.visual_beats[1], screen_readability="readable", provenance="video_map"
    )
    with pytest.raises(EditorialBeatError, match="readable screen requires verified"):
        validate_editorial_beat_graph(
            replace(graph, visual_beats=(graph.visual_beats[0], readable_without_verification))
        )

    unknown_provenance = replace(graph.visual_beats[1], provenance="invented")
    with pytest.raises(EditorialBeatError, match="invalid"):
        validate_editorial_beat_graph(
            replace(graph, visual_beats=(graph.visual_beats[0], unknown_provenance))
        )
