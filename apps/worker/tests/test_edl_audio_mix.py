import asyncio
import hashlib
import shutil

import pytest

from app.models import Transcript, TranscriptWord
from app.pipeline.audio_assets import parse_audio_asset_manifest
from app.pipeline.audio_render_plan import resolve_audio_render_plan
from app.pipeline.edl import (
    EditIntentPlan,
    EditShotIntent,
    MusicIntent,
    SFXCueIntent,
    compile_edit_intent,
)
from app.pipeline.ffmpeg import probe_media, render_compiled_edl


def _digest(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _make_tone(path, *, frequency: int, duration: float, ffmpeg: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:sample_rate=48000:duration={duration}",
        str(path),
    )
    _, stderr = await proc.communicate()
    assert proc.returncode == 0, stderr.decode("utf-8", "replace")


def _asset(
    *,
    asset_id: str,
    kind: str,
    path,
    duration: float,
    loop_safe: bool,
) -> dict[str, object]:
    value: dict[str, object] = {
        "id": asset_id,
        "kind": kind,
        "relative_path": path.name,
        "sha256": _digest(path),
        "duration_seconds": duration,
        "license": {
            "status": "cleared",
            "scopes": ["commercial_social_paid"],
            "source": "test_generated",
            "attribution_required": False,
        },
        "moods": ["modern"],
        "tags": ["test"],
        "energy": 50,
        "mix": {
            "default_gain_db": -24.0,
            "max_gain_db": -10.0 if kind == "music" else -6.0,
            "fade_in_ms": 20,
            "fade_out_ms": 40,
        },
        "loop_safe": loop_safe,
    }
    if kind == "music":
        value["bpm"] = 120
        value["beat_offset_seconds"] = 0.0
    return value


async def _render_with_audio_assets(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    assert ffmpeg is not None and ffprobe is not None

    source = tmp_path / "source.mp4"
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=25:duration=4",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100:duration=4",
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

    music_path = tmp_path / "music.wav"
    sfx_path = tmp_path / "sfx.wav"
    await _make_tone(music_path, frequency=220, duration=1.0, ffmpeg=ffmpeg)
    await _make_tone(sfx_path, frequency=880, duration=0.2, ffmpeg=ffmpeg)
    registry = parse_audio_asset_manifest(
        {
            "version": 1,
            "assets": [
                _asset(
                    asset_id="music_bed_01",
                    kind="music",
                    path=music_path,
                    duration=1.0,
                    loop_safe=True,
                ),
                _asset(
                    asset_id="sfx_hit_01",
                    kind="sfx",
                    path=sfx_path,
                    duration=0.2,
                    loop_safe=False,
                ),
            ],
        },
        asset_root=tmp_path,
    )
    transcript = Transcript(
        text="alpha bravo charlie delta",
        words=[
            TranscriptWord("alpha", 0.20, 0.55),
            TranscriptWord("bravo", 0.56, 1.00),
            TranscriptWord("charlie", 2.00, 2.35),
            TranscriptWord("delta", 2.36, 2.90),
        ],
    )
    intent = EditIntentPlan(
        "2.0",
        "Dialogue stays primary over one verified bed and one word hit.",
        (
            EditShotIntent("hook", "hook", 0, 1),
            EditShotIntent("payoff", "payoff", 2, 3),
        ),
        music=(MusicIntent("music_bed_01", ducking_db=-14.0),),
        sfx=(SFXCueIntent("sfx_hit_01", "payoff", 2, gain_db=-8.0),),
    )
    edl = compile_edit_intent(
        intent,
        transcript,
        source_duration_ms=4_000,
        width=360,
        height=640,
        allowed_music_asset_ids={"music_bed_01"},
        allowed_sfx_asset_ids={"sfx_hit_01"},
    )
    audio_plan = resolve_audio_render_plan(edl, registry)
    output = tmp_path / "mixed.mp4"
    duration = await render_compiled_edl(
        source=str(source),
        edl=edl,
        transcript=transcript,
        out_path=str(output),
        audio_plan=audio_plan,
        ffmpeg_bin=ffmpeg,
        ffprobe_bin=ffprobe,
    )
    return edl, duration, await probe_media(str(output), ffprobe_bin=ffprobe)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_real_edl_render_mixes_verified_music_ducking_and_word_sfx(tmp_path) -> None:
    edl, duration, probe = asyncio.run(_render_with_audio_assets(tmp_path))
    intended = edl.duration_frames / edl.fps

    assert duration == pytest.approx(intended, abs=(1 / edl.fps) + 0.012)
    assert probe.has_video and probe.has_audio
    assert probe.video_fps == pytest.approx(edl.fps, abs=0.01)
    assert probe.audio_sample_rate == 48_000
    assert probe.audio_channels == 2
