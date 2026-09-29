from copy import deepcopy
from dataclasses import replace

import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.editorial_beats import (
    BeatEdge,
    EditorialBeat,
    EditorialBeatGraph,
    SourceMoment,
    VisualBeat,
    VisualFocusRegion,
)
from app.pipeline.editorial_director import (
    EDITORIAL_DIRECTOR_SYSTEM_PROMPT,
    EditorialDirectorError,
    compile_editorial_director_plan,
    editorial_director_user_prompt,
    evaluate_director_variant_diversity,
    parse_editorial_director_plan,
)
from app.pipeline.edl import EditScope, InclusiveWordRange


def _transcript() -> Transcript:
    tokens = (
        ("OUTSIDE_BEFORE", 0.00, 0.30),
        ("This", 0.40, 0.70),
        ("claim", 0.70, 1.00),
        ("works", 1.00, 1.30),
        ("Here", 1.50, 1.80),
        ("is", 1.80, 2.00),
        ("proof", 2.00, 2.30),
        ("That", 2.50, 2.80),
        ("is", 2.80, 3.00),
        ("payoff", 3.00, 3.30),
        ("OUTSIDE_AFTER", 3.50, 3.80),
    )
    return Transcript(
        text=" ".join(token for token, _start, _end in tokens),
        words=[TranscriptWord(*item) for item in tokens],
    )


def _graph() -> EditorialBeatGraph:
    scope = EditScope((InclusiveWordRange(1, 9),))
    moments = (
        SourceMoment("moment_claim", InclusiveWordRange(1, 3), 400, 1300, "claim"),
        SourceMoment("moment_proof", InclusiveWordRange(4, 6), 1500, 2300, "proof", "visible"),
        SourceMoment("moment_payoff", InclusiveWordRange(7, 9), 2500, 3300, "payoff"),
    )
    proof_visual = VisualBeat(
        "visual_proof",
        "screen_event",
        1500,
        2300,
        "screen_proof",
        "none",
        "readable",
        "still",
        "upper",
        95,
        VisualFocusRegion(0.10, 0.15, 0.75, 0.60),
        "verified_candidate",
    )
    beats = (
        EditorialBeat("beat_claim", "moment_claim", (), (), "hook", ("source_safe",)),
        EditorialBeat(
            "beat_proof",
            "moment_proof",
            ("visual_proof",),
            (),
            "prove",
            ("source_safe", "fit_blur", "screen_focus"),
        ),
        EditorialBeat("beat_payoff", "moment_payoff", (), (), "payoff", ("source_safe",)),
    )
    edges = (
        BeatEdge(
            "edge_claim_proof",
            "beat_claim",
            "beat_proof",
            "proves",
            "continuous",
            "scene_change",
            "unknown",
        ),
        BeatEdge(
            "edge_proof_payoff",
            "beat_proof",
            "beat_payoff",
            "continues",
            "continuous",
            "scene_change",
            "unknown",
        ),
    )
    return EditorialBeatGraph(
        "1.0",
        len(_transcript().words),
        scope,
        moments,
        (proof_visual,),
        (),
        beats,
        edges,
    )


def _shot(
    shot_id: str,
    beat_id: str,
    role: str,
    first: int,
    last: int,
    start_anchor: str,
    end_anchor: str,
    *,
    entry: str,
    exit_reason: str,
    joint: str,
    continuity: str,
    framing: str = "source_safe",
    transition: str = "hard_cut",
    effects: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "shot_id": shot_id,
        "beat_id": beat_id,
        "role": role,
        "from_word_id": f"w_{first:06d}",
        "to_word_id": f"w_{last:06d}",
        "start_anchor": start_anchor,
        "end_anchor": end_anchor,
        "entry_motivation": entry,
        "exit_motivation": exit_reason,
        "joint_motivation": joint,
        "continuity_strategy": continuity,
        "framing": {"mode": framing, "center_x": 0.5, "base_scale": 1.0},
        "effects": effects or [],
        "transition_out": transition,
        "caption_theme": "standard_karaoke",
        "speed": 1.0,
        "pre_roll_ms": 0,
        "post_roll_ms": 0,
    }


def _payload() -> dict[str, object]:
    return {
        "schema_version": "2.1",
        "campaign_hypothesis": "proof_first",
        "editorial_thesis": "Claim, show the proof, then land the payoff.",
        "shots": [
            _shot(
                "claim",
                "beat_claim",
                "hook",
                1,
                3,
                "This",
                "works",
                entry="scroll_stop",
                exit_reason="question_open",
                joint="opening",
                continuity="establish",
                transition="reveal",
            ),
            _shot(
                "proof",
                "beat_proof",
                "proof",
                4,
                6,
                "Here",
                "proof",
                entry="proof_arrival",
                exit_reason="proof_delivered",
                joint="proof_reveal",
                continuity="match_content",
                framing="screen_focus",
                effects=[
                    {
                        "kind": "color_pop",
                        "at_word_id": "w_000006",
                        "duration_ms": 300,
                        "intensity": 0.5,
                        "reason": "proof_focus",
                    }
                ],
            ),
            _shot(
                "payoff",
                "beat_payoff",
                "payoff",
                7,
                9,
                "That",
                "payoff",
                entry="payoff_arrival",
                exit_reason="payoff_delivered",
                joint="semantic_continuity",
                continuity="preserve",
            ),
        ],
        "music": [{"asset_id": "music_good"}],
        "sfx": [
            {
                "asset_id": "hit_good",
                "shot_id": "proof",
                "at_word_id": "w_000006",
                "gain_db": -10,
            }
        ],
    }


def _compile(payload: dict[str, object], graph: EditorialBeatGraph | None = None):
    return compile_editorial_director_plan(
        parse_editorial_director_plan(payload),
        graph or _graph(),
        _transcript(),
        source_duration_ms=4_000,
        allowed_music_asset_ids={"music_good"},
        allowed_sfx_asset_ids={"hit_good"},
    )


def test_valid_claim_proof_payoff_plan_lowers_to_frame_authoritative_edl_20() -> None:
    compiled = _compile(_payload())

    assert compiled.schema_version == "2.0"
    assert [shot.role for shot in compiled.shots] == ["hook", "proof", "payoff"]
    assert compiled.shots[1].framing.mode == "screen_focus"
    assert compiled.shots[1].framing.screen_region is not None
    assert compiled.shots[1].framing.screen_region.x == 0.10
    assert compiled.shots[1].framing.screen_region.width == 0.75
    assert compiled.shots[1].effects[0].kind == "color_pop"
    assert all(shot.timeline_out_frame > shot.timeline_in_frame for shot in compiled.shots)
    assert compiled.music[0].asset_id == "music_good"
    assert compiled.sfx[0].asset_id == "hit_good"
    assert compiled.sfx[0].word_id == 6


def test_unknown_beat_is_rejected_before_edl_compilation() -> None:
    payload = deepcopy(_payload())
    payload["shots"][1]["beat_id"] = "beat_invented"  # type: ignore[index]

    with pytest.raises(EditorialDirectorError, match="unknown beat"):
        _compile(payload)


def test_shot_word_range_cannot_escape_its_source_moment() -> None:
    payload = deepcopy(_payload())
    proof = payload["shots"][1]  # type: ignore[index]
    proof["from_word_id"] = "w_000003"
    proof["start_anchor"] = "works"

    with pytest.raises(EditorialDirectorError, match="escapes source moment"):
        _compile(payload)


def test_screen_focus_is_rejected_when_the_beat_has_no_trusted_roi() -> None:
    graph = _graph()
    proof_visual = replace(graph.visual_beats[0], focus_region=None)
    proof_beat = replace(
        graph.editorial_beats[1],
        available_framings=("source_safe", "fit_blur"),
    )
    graph_without_roi = replace(
        graph,
        visual_beats=(proof_visual,),
        editorial_beats=(graph.editorial_beats[0], proof_beat, graph.editorial_beats[2]),
    )

    with pytest.raises(EditorialDirectorError, match="framing 'screen_focus' is unavailable"):
        _compile(_payload(), graph_without_roi)


def test_screen_focus_rejects_unverified_readability_and_roi_provenance() -> None:
    graph = _graph()
    unverified = replace(
        graph,
        visual_beats=(replace(graph.visual_beats[0], provenance="video_map"),),
    )

    with pytest.raises(EditorialDirectorError, match="readable screen requires verified"):
        _compile(_payload(), unverified)


def test_screen_focus_roi_must_overlap_the_selected_word_subrange() -> None:
    graph = _graph()
    # The ROI still overlaps the parent proof moment, but ends before the only
    # selected word begins. Parent-beat overlap is therefore insufficient.
    graph = replace(
        graph,
        visual_beats=(replace(graph.visual_beats[0], source_out_ms=1_950),),
    )
    payload = deepcopy(_payload())
    proof = payload["shots"][1]  # type: ignore[index]
    proof["from_word_id"] = "w_000006"
    proof["to_word_id"] = "w_000006"
    proof["start_anchor"] = "proof"
    proof["end_anchor"] = "proof"

    with pytest.raises(EditorialDirectorError, match="overlapping its selected words; found 0"):
        _compile(payload, graph)


def test_screen_focus_fails_closed_when_multiple_rois_overlap_the_selected_words() -> None:
    graph = _graph()
    second_visual = replace(
        graph.visual_beats[0],
        visual_id="visual_proof_alt",
        source_event_id="screen_event_alt",
        focus_region=VisualFocusRegion(0.15, 0.20, 0.70, 0.55),
    )
    proof_beat = replace(
        graph.editorial_beats[1],
        visual_ids=("visual_proof", "visual_proof_alt"),
    )
    ambiguous = replace(
        graph,
        visual_beats=(*graph.visual_beats, second_visual),
        editorial_beats=(graph.editorial_beats[0], proof_beat, graph.editorial_beats[2]),
    )

    with pytest.raises(EditorialDirectorError, match="selected words; found 2"):
        _compile(_payload(), ambiguous)


def test_missing_previous_to_current_graph_edge_is_rejected() -> None:
    graph = replace(_graph(), edges=(_graph().edges[0],))

    with pytest.raises(EditorialDirectorError, match="no directed graph edge"):
        _compile(_payload(), graph)


def test_stylized_transition_must_match_the_next_shot_joint_motivation() -> None:
    payload = deepcopy(_payload())
    payload["shots"][0]["transition_out"] = "hard_impact"  # type: ignore[index]

    with pytest.raises(EditorialDirectorError, match="transition 'hard_impact' is not motivated"):
        _compile(payload)


def test_effect_without_a_closed_reason_is_rejected_by_the_parser() -> None:
    payload = deepcopy(_payload())
    del payload["shots"][1]["effects"][0]["reason"]  # type: ignore[index]

    with pytest.raises(EditorialDirectorError, match=r"effects\[0\]\.reason"):
        parse_editorial_director_plan(payload)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda payload: payload.update({"ffmpeg_filter": "movie=/tmp/secret"}), "unsupported"),
        (
            lambda payload: payload["shots"][0].update(  # type: ignore[index]
                {"source_start_seconds": 0.4}
            ),
            "unsupported",
        ),
        (
            lambda payload: payload["shots"][1]["effects"][0].update(  # type: ignore[index]
                {"filter": "evil"}
            ),
            "unsupported",
        ),
    ],
)
def test_hostile_or_unknown_keys_are_rejected(mutate, message: str) -> None:
    payload = deepcopy(_payload())
    mutate(payload)

    with pytest.raises(EditorialDirectorError, match=message):
        parse_editorial_director_plan(payload)


def test_prompt_uses_graph_json_and_only_scoped_word_ids_as_cut_authority() -> None:
    graph = _graph()
    prompt = editorial_director_user_prompt(
        graph=graph,
        transcript=_transcript(),
        target_duration_seconds=30,
        music_asset_ids={"music_good"},
        sfx_asset_ids={"hit_good"},
    )

    assert graph.to_prompt_json() in prompt
    assert "OUTSIDE_BEFORE" not in prompt
    assert "OUTSIDE_AFTER" not in prompt
    assert '"word_id":"w_000001","text":"This"' in prompt
    assert "w_000000" not in prompt
    assert "@0." not in prompt
    assert "source_start_seconds" not in prompt
    assert "timeline_seconds" not in prompt
    assert "the only cut authority" in prompt
    assert "Word IDs" in EDITORIAL_DIRECTOR_SYSTEM_PROMPT


def test_proof_first_can_reset_to_earlier_context_without_inventing_an_edge() -> None:
    payload = deepcopy(_payload())
    claim, proof, payoff = payload["shots"]  # type: ignore[index]
    proof["role"] = "hook"
    proof["entry_motivation"] = "scroll_stop"
    proof["joint_motivation"] = "opening"
    proof["continuity_strategy"] = "establish"
    proof["transition_out"] = "hard_cut"
    claim["role"] = "setup"
    claim["entry_motivation"] = "context_reset"
    claim["exit_motivation"] = "question_open"
    claim["joint_motivation"] = "context_reset"
    claim["continuity_strategy"] = "hard_reset"
    claim["transition_out"] = "hard_cut"
    payoff["entry_motivation"] = "context_reset"
    payoff["joint_motivation"] = "context_reset"
    payoff["continuity_strategy"] = "hard_reset"
    payload["shots"] = [proof, claim, payoff]

    compiled = _compile(payload)
    assert [shot.from_word_id for shot in compiled.shots] == [4, 1, 7]


def test_same_beat_replay_is_explicit_and_does_not_need_a_self_edge() -> None:
    payload = deepcopy(_payload())
    replay = deepcopy(payload["shots"][2])  # type: ignore[index]
    replay["shot_id"] = "payoff_replay"
    replay["entry_motivation"] = "replay"
    replay["joint_motivation"] = "replay"
    replay["continuity_strategy"] = "preserve"
    payload["shots"].append(replay)  # type: ignore[union-attr]

    compiled = _compile(payload)
    assert compiled.shots[-1].from_word_id == compiled.shots[-2].from_word_id


@pytest.mark.parametrize(
    "effect, message",
    [
        (
            {
                "kind": "speed_ramp",
                "at_word_id": "w_000006",
                "duration_ms": 300,
                "intensity": 0.5,
                "reason": "time_compression",
            },
            "speed_ramp is not renderable",
        ),
        (
            {
                "kind": "color_pop",
                "at_word_id": None,
                "duration_ms": 300,
                "intensity": 0.5,
                "reason": "proof_focus",
            },
            "requires at_word_id",
        ),
    ],
)
def test_schema_21_rejects_effects_the_renderer_cannot_honestly_execute(
    effect: dict[str, object], message: str
) -> None:
    payload = deepcopy(_payload())
    payload["shots"][1]["effects"] = [effect]  # type: ignore[index]
    with pytest.raises(EditorialDirectorError, match=message):
        _compile(payload)


def test_three_variants_must_differ_in_hypothesis_opening_and_structure() -> None:
    base = parse_editorial_director_plan(_payload())
    duplicate_report = evaluate_director_variant_diversity((base, base, base))
    assert duplicate_report.status == "reject"
    assert "timeline_structures_are_duplicates" in duplicate_report.findings

    curiosity_payload = deepcopy(_payload())
    curiosity_payload["campaign_hypothesis"] = "curiosity_first"
    curiosity_payload["shots"] = [
        curiosity_payload["shots"][2],
        curiosity_payload["shots"][0],
    ]  # type: ignore[index]
    authority_payload = deepcopy(_payload())
    authority_payload["campaign_hypothesis"] = "authority_first"
    authority_payload["shots"] = [
        authority_payload["shots"][1],
        authority_payload["shots"][2],
    ]  # type: ignore[index]
    report = evaluate_director_variant_diversity(
        (
            base,
            parse_editorial_director_plan(curiosity_payload),
            parse_editorial_director_plan(authority_payload),
        ),
        max_pairwise_word_overlap=1.0,
    )
    assert report.status == "pass"
