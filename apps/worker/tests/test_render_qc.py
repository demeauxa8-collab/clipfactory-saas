import shutil

import pytest

from app.pipeline.ffmpeg import FFmpegError, _run, validate_rendered_clip

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg is required")


async def make_clip(path, *, black_edge=None, silent_opening=False):
    video = "color=c=white:s=160x284:r=30:d=2"
    if black_edge:
        condition = "lt(t,0.5)" if black_edge == "opening" else "gte(t,1.5)"
        video += f",drawbox=color=black:t=fill:enable='{condition}'"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", video,
           "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=2"]
    if silent_opening:
        cmd.extend(["-af", "volume=0:enable='lt(t,0.95)'"])
    cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", str(path)])
    code, _, err = await _run(cmd)
    assert code == 0, err


async def test_clean_render_passes_full_temporal_qc(tmp_path):
    path = tmp_path / "clean.mp4"
    await make_clip(path)
    report = await validate_rendered_clip(path=str(path), expected_duration_seconds=2,
                                         expected_width=160, expected_height=284)
    assert report.ok, report.problems
    assert report.black_intervals == ()
    assert report.mean_volume_db is not None


@pytest.mark.parametrize("edge", ["opening", "ending"])
async def test_temporal_qc_catches_black_edges_despite_a_bright_middle(tmp_path, edge):
    path = tmp_path / f"black_{edge}.mp4"
    await make_clip(path, black_edge=edge)
    report = await validate_rendered_clip(path=str(path), expected_duration_seconds=2)
    assert report.mid_frame_luma > 100
    assert f"black_{edge}" in report.problems
    assert not report.ok


async def test_temporal_qc_catches_silent_opening_despite_audible_average(tmp_path):
    path = tmp_path / "silence.mp4"
    await make_clip(path, silent_opening=True)
    report = await validate_rendered_clip(path=str(path), expected_duration_seconds=2)
    assert report.mean_volume_db > -55
    assert "silence_opening" in report.problems


async def test_qc_compares_the_render_to_the_planned_duration(tmp_path):
    path = tmp_path / "truncated.mp4"
    await make_clip(path)
    report = await validate_rendered_clip(path=str(path), expected_duration_seconds=2.4,
                                         expected_width=1080, expected_height=1920)
    assert not report.ok
    assert any("timeline_mismatch" in p for p in report.problems)
    assert "width_mismatch:160!=1080" in report.problems


async def test_unmeasurable_temporal_analysis_cannot_pass(monkeypatch, tmp_path):
    from app.pipeline import ffmpeg

    path = tmp_path / "unreadable.mp4"
    await make_clip(path)
    original = ffmpeg._run

    async def fail_analysis(cmd, **kwargs):
        if "silencedetect" in " ".join(cmd):
            raise FFmpegError("decoder failure")
        return await original(cmd, **kwargs)

    monkeypatch.setattr(ffmpeg, "_run", fail_analysis)
    report = await validate_rendered_clip(path=str(path), expected_duration_seconds=2)
    assert "temporal_analysis_unreadable" in report.problems
    assert not report.ok
