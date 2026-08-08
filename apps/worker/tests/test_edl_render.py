from dataclasses import replace

import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.edl import (
    EditIntentPlan,
    EditShotIntent,
    EffectIntent,
    FramingIntent,
    compile_edit_intent,
)
from app.pipeline.edl_render import EDLRenderError, compile_ffmpeg_render_plan


def _transcript() -> Transcript:
    words = [
        TranscriptWord("alpha", 0.00, 0.35),
        TranscriptWord("bravo", 0.36, 0.70),
        TranscriptWord("charlie", 0.71, 1.05),
        TranscriptWord("delta", 1.06, 1.40),
        TranscriptWord("echo", 8.00, 8.35),
        TranscriptWord("foxtrot", 8.36, 8.70),
        TranscriptWord("golf", 8.71, 9.05),
        TranscriptWord("hotel", 9.06, 9.40),
    ]
    return Transcript(text=" ".join(word.word for word in words), words=words)


def _edl():
    transcript = _transcript()
    plan = EditIntentPlan(
        schema_version="2.0",
        editorial_thesis="Open late, then explain with a visual accent.",
        shots=(
            EditShotIntent(
                shot_id="hook",
                role="hook",
                from_word_id=4,
                to_word_id=7,
                framing=FramingIntent("locked_face", center_x=0.3, base_scale=1.1),
                effects=(
                    EffectIntent("punch_in", at_word_id=5, duration_ms=200, intensity=0.6),
                    EffectIntent("flash", at_word_id=6, duration_ms=150, intensity=0.5),
                ),
                speed=1.25,
            ),
            EditShotIntent(
                shot_id="setup",
                role="setup",
                from_word_id=0,
                to_word_id=3,
                framing=FramingIntent("screen_focus", center_x=0.8, base_scale=1.0),
                effects=(
                    EffectIntent("freeze", at_word_id=2, duration_ms=150, intensity=0.5),
                    EffectIntent("color_pop", at_word_id=3, duration_ms=100, intensity=0.4),
                ),
            ),
            # Reuse is legal in the EDL and makes this fixture long enough for
            # the compiler's intentional effect-density budget.
            EditShotIntent(
                shot_id="hook_reprise",
                role="reaction",
                from_word_id=4,
                to_word_id=7,
            ),
            EditShotIntent(
                shot_id="setup_reprise",
                role="bridge",
                from_word_id=0,
                to_word_id=3,
            ),
            EditShotIntent(
                shot_id="hook_payoff",
                role="payoff",
                from_word_id=4,
                to_word_id=7,
            ),
            EditShotIntent(
                shot_id="setup_cta",
                role="cta",
                from_word_id=0,
                to_word_id=3,
            ),
        ),
    )
    return compile_edit_intent(plan, transcript, source_duration_ms=20_000), transcript


def test_plan_uses_one_input_per_decode_island_and_reorders_shots() -> None:
    edl, transcript = _edl()
    render_plan = compile_ffmpeg_render_plan(edl, transcript)

    assert len(edl.decode_islands) == 2
    assert len(render_plan.inputs) == 2
    assert [shot.shot_id for shot in render_plan.shots] == [
        "hook",
        "setup",
        "hook_reprise",
        "setup_reprise",
        "hook_payoff",
        "setup_cta",
    ]
    assert [shot.input_index for shot in render_plan.shots] == [1, 0, 1, 0, 1, 0]
    assert render_plan.shots[0].island_offset_in_ms == 0
    assert render_plan.shots[1].island_offset_in_ms == 0
    assert "[1:v]trim=start=0.000" in render_plan.filter_complex
    assert "[0:v]trim=start=0.000" in render_plan.filter_complex
    assert "concat=n=6:v=1:a=1[v_concat][a_concat]" in render_plan.filter_complex
    assert "trim=duration=" in render_plan.filter_complex


def test_plan_realises_closed_effects_with_word_timed_intervals() -> None:
    edl, transcript = _edl()
    render_plan = compile_ffmpeg_render_plan(edl, transcript)

    assert [effect.kind for effect in render_plan.effects] == [
        "punch_in",
        "flash",
        "freeze",
        "color_pop",
    ]
    punch = render_plan.effects[0]
    assert punch.timeline_in_ms > edl.shots[0].timeline_in_ms
    assert punch.timeline_out_ms - punch.timeline_in_ms == 200
    assert "drawbox=x=0:y=0:w=iw:h=ih:color=white@" in render_plan.filter_complex
    assert "tpad=stop_mode=clone:stop_duration=0.150" in render_plan.filter_complex
    assert "eq=contrast=" in render_plan.filter_complex


def test_input_args_are_argv_and_share_the_trusted_source_path() -> None:
    edl, transcript = _edl()
    render_plan = compile_ffmpeg_render_plan(edl, transcript)

    assert render_plan.input_args("/private/source.mp4") == [
        "-ss",
        "0.000",
        "-t",
        "1.520",
        "-i",
        "/private/source.mp4",
        "-ss",
        "8.000",
        "-t",
        "1.520",
        "-i",
        "/private/source.mp4",
    ]


def test_unsafe_handcrafted_edl_is_rejected_before_graph_generation() -> None:
    edl, transcript = _edl()
    bad_island = replace(edl.decode_islands[0], shot_ids=("unknown",))
    unsafe = replace(edl, decode_islands=(bad_island, *edl.decode_islands[1:]))

    with pytest.raises(EDLRenderError, match=r"not assigned|unknown shot"):
        compile_ffmpeg_render_plan(unsafe, transcript)


def test_asset_ids_stay_deferred_and_framing_fallbacks_are_explicit() -> None:
    edl, transcript = _edl()
    render_plan = compile_ffmpeg_render_plan(edl, transcript)

    assert render_plan.deferred_music_asset_ids == ()
    assert render_plan.deferred_sfx_asset_ids == ()
    assert any("fit_blur" in limitation for limitation in render_plan.limitations)


def test_closed_transition_catalogue_becomes_duration_preserving_filters() -> None:
    edl, transcript = _edl()
    first = replace(edl.shots[0], transition_out="hard_impact")
    second = replace(edl.shots[1], transition_out="reveal")
    third = replace(edl.shots[2], transition_out="contrast")
    transitioned = replace(edl, shots=(first, second, third, *edl.shots[3:]))

    render_plan = compile_ffmpeg_render_plan(transitioned, transcript)

    assert [item.kind for item in render_plan.transitions[:3]] == [
        "hard_impact",
        "reveal",
        "contrast",
    ]
    assert "drawbox=x=0:y=0:w=iw:h=ih:color=white@0.45" in render_plan.filter_complex
    assert "fade=t=out" in render_plan.filter_complex
    assert "eq=contrast=1.18:saturation=1.12" in render_plan.filter_complex
