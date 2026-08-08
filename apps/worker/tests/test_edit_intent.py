import pytest

from app.models import MontageCandidate, MontageSegment, Transcript, TranscriptWord
from app.pipeline.edit_intent import (
    EDIT_INTENT_SYSTEM_PROMPT,
    edit_intent_user_prompt,
    parse_edit_intent,
    transcript_to_word_id_lines,
)
from app.pipeline.edl import EDLValidationError, compile_edit_intent


def _transcript() -> Transcript:
    words = [
        TranscriptWord("J'ai", 0.0, 0.25),
        TranscriptWord("seulement", 0.26, 0.55),
        TranscriptWord("un", 0.56, 0.67),
        TranscriptWord("euro", 0.68, 0.90),
        TranscriptWord("regarde", 10.0, 10.28),
        TranscriptWord("la", 10.29, 10.38),
        TranscriptWord("preuve", 10.39, 10.70),
        TranscriptWord("maintenant", 10.71, 11.05),
    ]
    return Transcript(text=" ".join(word.word for word in words), words=words)


def _candidate() -> MontageCandidate:
    return MontageCandidate(
        title="Un euro",
        hook="J'ai seulement un euro",
        segments=[MontageSegment("setup", 0.0, 0.9, "J'ai seulement un euro")],
        rationale="Proof-first edit",
        score_total=90,
        score_breakdown={},
        arc_type="challenge_result",
    )


def _payload() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "editorial_thesis": "Open on proof, then reveal the constraint.",
        "shots": [
            {
                "shot_id": "proof_first",
                "role": "hook",
                "from_word_id": "w_000004",
                "to_word_id": "w_000007",
                "start_anchor": "regarde la",
                "end_anchor": "preuve maintenant",
                "framing": {
                    "mode": "screen_focus",
                    "center_x": 0.5,
                    "base_scale": 1.08,
                },
                "effects": [
                    {
                        "kind": "punch_in",
                        "at_word_id": "w_000006",
                        "duration_ms": 240,
                        "intensity": 0.55,
                    }
                ],
                "transition_out": "hard_impact",
                "caption_theme": "proof_clean",
                "speed": 1.0,
                "pre_roll_ms": 0,
                "post_roll_ms": 100,
            },
            {
                "shot_id": "constraint",
                "role": "setup",
                "from_word_id": "w_000000",
                "to_word_id": "w_000003",
                "start_anchor": "J'ai seulement",
                "end_anchor": "un euro",
                "framing": {"mode": "locked_face"},
                "effects": [],
                "transition_out": "hard_cut",
                "caption_theme": "hook_bold",
            },
        ],
        "music": [
            {
                "asset_id": "music_tension_01",
                "start_shot_id": "proof_first",
                "end_shot_id": "constraint",
                "gain_db": -24,
                "ducking_db": -12,
                "fade_in_ms": 100,
                "fade_out_ms": 300,
                "loop": True,
            }
        ],
        "sfx": [
            {
                "asset_id": "sfx_hit_01",
                "shot_id": "proof_first",
                "at_word_id": "w_000006",
                "gain_db": -12,
            }
        ],
    }


def test_transcript_view_has_stable_ids_and_timestamps() -> None:
    view = transcript_to_word_id_lines(_transcript(), words_per_line=4)

    assert "w_000000@0.000=J'ai" in view
    assert "w_000007@10.710=maintenant" in view
    assert len(view.splitlines()) == 2


def test_parse_then_compile_preserves_non_linear_editorial_order() -> None:
    transcript = _transcript()
    plan = parse_edit_intent(_payload())
    edl = compile_edit_intent(plan, transcript, source_duration_ms=12_000)

    assert [shot.shot_id for shot in edl.shots] == ["proof_first", "constraint"]
    assert edl.shots[0].source_in_ms == 10_000
    assert edl.shots[1].source_in_ms == 0
    assert edl.sfx[0].shot_id == "proof_first"
    assert edl.music[0].timeline_out_ms == edl.duration_ms


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["shots"][0].update(  # type: ignore[index,union-attr]
                {"from_word_id": "4"}
            ),
            "invalid word_id",
        ),
        (
            lambda payload: payload["shots"][0].update(  # type: ignore[index,union-attr]
                {"start_anchor": "invented words"}
            ),
            "start_anchor does not match",
        ),
        (
            lambda payload: payload["shots"][0]["effects"][0].update(  # type: ignore[index,union-attr]
                {"kind": "raw_ffmpeg"}
            ),
            "unsupported effect",
        ),
        (
            lambda payload: payload["music"][0].update(  # type: ignore[index,union-attr]
                {"asset_id": "https://example.com/song.mp3"}
            ),
            "catalogue-safe ID",
        ),
    ],
)
def test_hostile_or_invented_values_are_rejected(mutate, message: str) -> None:
    payload = _payload()
    mutate(payload)

    with pytest.raises(EDLValidationError, match=message):
        plan = parse_edit_intent(payload)
        compile_edit_intent(plan, _transcript(), source_duration_ms=12_000)


def test_prompt_exposes_only_closed_assets_and_forbids_raw_ffmpeg() -> None:
    prompt = edit_intent_user_prompt(
        transcript=_transcript(),
        candidate=_candidate(),
        target_duration_seconds=20,
        shot_assets=[{"id": "screen_proof_01", "kind": "screen"}],
        audio_assets=[{"id": "music_tension_01", "kind": "music"}],
    )

    assert "screen_proof_01" in prompt
    assert "music_tension_01" in prompt
    assert "w_000000" in prompt
    assert "do NOT write FFmpeg" in EDIT_INTENT_SYSTEM_PROMPT
    assert "file paths, URLs" in EDIT_INTENT_SYSTEM_PROMPT
