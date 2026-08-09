import asyncio
import shutil
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
from app.pipeline.edl_captions import build_caption_plan, write_ass_for_edl
from app.pipeline.edl_render import EDLRenderError, compile_ffmpeg_render_plan
from app.pipeline.ffmpeg import detect_black_intervals, probe_media, render_compiled_edl


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


def _edl(*, width: int = 1080, height: int = 1920):
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
    return (
        compile_edit_intent(
            plan,
            transcript,
            source_duration_ms=20_000,
            width=width,
            height=height,
        ),
        transcript,
    )


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
    assert "[1:v]split=3" in render_plan.filter_complex
    assert "[0:v]split=3" in render_plan.filter_complex
    assert "[1:a]asplit=3" in render_plan.filter_complex
    assert "[0:a]asplit=3" in render_plan.filter_complex
    assert "[island_1_v_0]trim=start=0.000" in render_plan.filter_complex
    assert "[island_0_v_0]trim=start=0.000" in render_plan.filter_complex
    assert "concat=n=6:v=1:a=0[v_concat]" in render_plan.filter_complex
    assert "acrossfade=d=0.008:o=0:c1=tri:c2=tri[a_concat]" in render_plan.filter_complex
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
    punch_word = next(
        item for item in edl.shots[0].word_occurrences if item.word_id == 5
    )
    assert punch.timeline_in_ms > edl.shots[0].timeline_in_ms
    assert punch.timeline_in_frame == punch_word.timeline_in_frame
    assert punch.timeline_out_ms - punch.timeline_in_ms == 200
    assert punch.timeline_in_ms == round(punch.timeline_in_frame * 1000 / edl.fps)
    assert punch.timeline_out_ms == round(punch.timeline_out_frame * 1000 / edl.fps)
    assert "drawbox=x=0:y=0:w=iw:h=ih:color=white@" in render_plan.filter_complex
    assert "tpad=stop_mode=clone:stop_duration=0.133333" in render_plan.filter_complex
    assert "eq=contrast=" in render_plan.filter_complex


def test_input_args_are_argv_and_share_the_trusted_source_path() -> None:
    edl, transcript = _edl()
    render_plan = compile_ffmpeg_render_plan(edl, transcript)

    assert render_plan.input_args("/private/source.mp4") == [
        "-ss",
        "0.000",
        "-t",
        "1.520",
        "-accurate_seek",
        "-i",
        "/private/source.mp4",
        "-ss",
        "8.000",
        "-t",
        "1.520",
        "-accurate_seek",
        "-i",
        "/private/source.mp4",
    ]


def test_unsafe_handcrafted_edl_is_rejected_before_graph_generation() -> None:
    edl, transcript = _edl()
    bad_island = replace(edl.decode_islands[0], shot_ids=("unknown",))
    unsafe = replace(edl, decode_islands=(bad_island, *edl.decode_islands[1:]))

    with pytest.raises(EDLRenderError, match=r"not assigned|unknown shot"):
        compile_ffmpeg_render_plan(unsafe, transcript)


def test_asset_ids_stay_deferred_and_fit_blur_is_a_real_composition() -> None:
    edl, transcript = _edl()
    first = replace(edl.shots[0], framing=FramingIntent("fit_blur"))
    edited = replace(edl, shots=(first, *edl.shots[1:]))
    render_plan = compile_ffmpeg_render_plan(edited, transcript)

    assert render_plan.deferred_music_asset_ids == ()
    assert render_plan.deferred_sfx_asset_ids == ()
    assert "boxblur=20:2" in render_plan.filter_complex
    assert "overlay=(W-w)/2:(H-h)/2" in render_plan.filter_complex
    assert not any("fit_blur" in limitation for limitation in render_plan.limitations)


def test_video_only_source_gets_deterministic_silent_dialogue() -> None:
    edl, transcript = _edl()

    render_plan = compile_ffmpeg_render_plan(edl, transcript, source_has_audio=False)

    assert render_plan.requires_source_audio is False
    assert "[0:a]" not in render_plan.filter_complex
    assert "[1:a]" not in render_plan.filter_complex
    assert render_plan.filter_complex.count("anullsrc=r=48000:cl=stereo") == len(edl.shots)


def test_visual_insert_mode_is_rejected_instead_of_faked() -> None:
    edl, transcript = _edl()
    first = replace(edl.shots[0], framing=FramingIntent("pip_proof"))
    edited = replace(edl, shots=(first, *edl.shots[1:]))

    with pytest.raises(EDLRenderError, match="authorised visual insert"):
        compile_ffmpeg_render_plan(edited, transcript)


def test_handcrafted_effect_cannot_escape_its_compiled_word_occurrences() -> None:
    edl, transcript = _edl()
    escaped_effect = EffectIntent("flash", at_word_id=0, duration_ms=100)
    first = replace(edl.shots[0], effects=(escaped_effect,))
    edited = replace(edl, shots=(first, *edl.shots[1:]))

    with pytest.raises(EDLRenderError, match="effect word 0 is outside"):
        compile_ffmpeg_render_plan(edited, transcript)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda shot: replace(shot, speed=float("nan")), "unsupported speed"),
        (lambda shot: replace(shot, source_out_ms=shot.source_in_ms), "source timing"),
        (lambda shot: replace(shot, timeline_out_ms=shot.timeline_out_ms + 1), "timeline"),
        (
            lambda shot: replace(
                shot,
                word_occurrences=(
                    replace(shot.word_occurrences[0], shot_id="other"),
                    *shot.word_occurrences[1:],
                ),
            ),
            "belongs to another shot",
        ),
    ],
)
def test_handcrafted_compiled_edl_is_revalidated_at_renderer_boundary(
    mutation,
    message: str,
) -> None:
    edl, transcript = _edl()
    first = mutation(edl.shots[0])
    edited = replace(edl, shots=(first, *edl.shots[1:]))

    with pytest.raises(EDLRenderError, match=message):
        compile_ffmpeg_render_plan(edited, transcript)


def test_edl_duration_milliseconds_must_match_authoritative_frames() -> None:
    edl, transcript = _edl()

    with pytest.raises(EDLRenderError, match="milliseconds"):
        compile_ffmpeg_render_plan(replace(edl, duration_ms=edl.duration_ms + 1), transcript)


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
    assert "brightness='if(between(t," in render_plan.filter_complex
    assert "contrast='if(between(t," in render_plan.filter_complex
    assert "fade=t=out" not in render_plan.filter_complex
    assert "eq=contrast=1.18:saturation=1.12" in render_plan.filter_complex


async def _render_synthetic_edl(tmp_path):
    source = tmp_path / "source.mp4"
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg is not None
    assert ffprobe is not None
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=25:duration=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100:duration=10",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(source),
    )
    _, stderr = await proc.communicate()
    assert proc.returncode == 0, stderr.decode("utf-8", "replace")

    edl, transcript = _edl(width=360, height=640)
    first = replace(edl.shots[0], transition_out="reveal")
    edl = replace(edl, shots=(first, *edl.shots[1:]))
    captions = tmp_path / "captions.ass"
    assert write_ass_for_edl(
        build_caption_plan(edl, transcript),
        out_path=str(captions),
    )
    output = tmp_path / "edl.mp4"
    duration = await render_compiled_edl(
        source=str(source),
        edl=edl,
        transcript=transcript,
        out_path=str(output),
        subtitles_path=str(captions),
        ffmpeg_bin=ffmpeg,
        ffprobe_bin=ffprobe,
    )
    black_intervals = await detect_black_intervals(
        str(output),
        0.0,
        window_seconds=duration,
        min_black_seconds=0.25,
        ffmpeg_bin=ffmpeg,
    )
    return (
        edl,
        duration,
        await probe_media(str(output), ffprobe_bin=ffprobe),
        black_intervals,
    )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_real_edl_render_reorders_replays_effects_and_captions(tmp_path) -> None:
    edl, duration, probe, black_intervals = asyncio.run(_render_synthetic_edl(tmp_path))
    intended = edl.duration_frames / edl.fps

    assert duration == pytest.approx(intended, abs=(1 / edl.fps) + 0.012)
    assert probe.has_video and probe.has_audio
    assert probe.video_fps == pytest.approx(edl.fps, abs=0.01)
    assert probe.audio_sample_rate == 48_000
    assert probe.audio_channels == 2
    assert probe.video_duration_seconds is not None
    assert probe.audio_duration_seconds is not None
    assert abs(probe.video_duration_seconds - probe.audio_duration_seconds) <= (
        1 / edl.fps
    ) + 0.012
    assert sum(end - start for start, end in black_intervals) < 0.25
