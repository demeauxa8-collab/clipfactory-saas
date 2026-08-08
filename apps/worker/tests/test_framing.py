import shutil

import pytest

from app.pipeline.ffmpeg import (
    OUTPUT_AUDIO_SAMPLE_RATE,
    OUTPUT_VIDEO_FPS,
    WHITE_DIP_SECONDS,
    FFmpegError,
    _build_single_pass_montage,
    _framing_vf,
    _normalize_framings,
    _normalize_transitions,
    _segment_intermediate_vf,
    _vertical_face_crop_vf,
    _vertical_fit_blur_vf,
    probe_media,
    render_montage_clip,
)
from app.pipeline.vision import _coerce_face_center_x, _parse_vision


def test_face_crop_builds_full_height_9_16_window() -> None:
    vf = _vertical_face_crop_vf(0.5)
    # Full-height crop, even 9:16 width, then scale to the vertical canvas.
    assert vf.startswith("crop=floor(ih*9/16/2)*2:ih:")
    assert vf.endswith(",scale=1080:1920,setsar=1")
    # Commas inside min/max stay escaped so the filtergraph parser keeps one filter.
    assert "max(0\\,min(iw-ow\\,0.5000*iw-ow/2)):0" in vf


def test_face_crop_clamps_center_x() -> None:
    assert "1.0000*iw-ow/2" in _vertical_face_crop_vf(9.0)
    assert "0.0000*iw-ow/2" in _vertical_face_crop_vf(-3.0)


def test_face_crop_appends_subtitles_last() -> None:
    vf = _vertical_face_crop_vf(0.5, subtitles_path="/tmp/a:b/clip.ass")
    assert vf.rstrip().endswith("clip.ass'")
    # Same escaping as the fit+blur builder (colon escaped for the subtitles path).
    assert "subtitles='/tmp/a\\:b/clip.ass'" in vf


def test_framing_vf_defaults_to_fit_blur() -> None:
    assert _framing_vf(None) == _vertical_fit_blur_vf()
    assert _framing_vf(("fit_blur", 0.5)) == _vertical_fit_blur_vf()


def test_framing_vf_selects_face_crop() -> None:
    assert _framing_vf(("face_crop", 0.3)) == _vertical_face_crop_vf(0.3)


def test_coerce_face_center_x_clamps_and_tolerates_garbage() -> None:
    assert _coerce_face_center_x(0.42) == 0.42
    assert _coerce_face_center_x(2.0) == 1.0
    assert _coerce_face_center_x(-1.0) == 0.0
    assert _coerce_face_center_x(None) is None
    assert _coerce_face_center_x("nope") is None


def test_parse_vision_reads_new_fields() -> None:
    v = _parse_vision(
        {
            "decor": "studio",
            "person_visible": True,
            "energy": 80,
            "action": "talking head",
            "visual_score": 75,
            "face_center_x": 0.6,
            "burned_captions": True,
        }
    )
    assert v is not None
    assert v.face_center_x == 0.6
    assert v.burned_captions is True


def test_parse_vision_defaults_new_fields_when_absent() -> None:
    v = _parse_vision({"decor": "car", "visual_score": 50})
    assert v is not None
    assert v.face_center_x is None
    assert v.burned_captions is False


# ---------------- per-segment framing normalisation ----------------


def test_normalize_framings_none_is_fit_blur_per_segment() -> None:
    assert _normalize_framings(None, 3) == [None, None, None]


def test_normalize_framings_single_tuple_replicated() -> None:
    # Legacy single-framing input applies to every segment.
    assert _normalize_framings(("face_crop", 0.4), 3) == [
        ("face_crop", 0.4),
        ("face_crop", 0.4),
        ("face_crop", 0.4),
    ]


def test_normalize_framings_single_entry_list_replicated() -> None:
    assert _normalize_framings([("fit_blur", 0.5)], 2) == [
        ("fit_blur", 0.5),
        ("fit_blur", 0.5),
    ]


def test_normalize_framings_per_segment_list_preserved() -> None:
    framings = [("face_crop", 0.3), None, ("fit_blur", 0.5)]
    assert _normalize_framings(framings, 3) == framings


def test_normalize_framings_empty_list_is_fit_blur() -> None:
    assert _normalize_framings([], 2) == [None, None]


def test_normalize_framings_length_mismatch_raises() -> None:
    with pytest.raises(FFmpegError):
        _normalize_framings([("face_crop", 0.3), None], 3)


# ---------------- transition normalisation ----------------


def test_normalize_transitions_none_is_all_cuts() -> None:
    # n segments -> n-1 joints.
    assert _normalize_transitions(None, 3) == ["cut", "cut"]
    assert _normalize_transitions(None, 1) == []


def test_normalize_transitions_valid_values_preserved() -> None:
    assert _normalize_transitions(["cut", "white_dip"], 3) == ["cut", "white_dip"]


def test_normalize_transitions_wrong_length_raises() -> None:
    with pytest.raises(FFmpegError):
        _normalize_transitions(["cut"], 3)  # needs 2 joints


def test_normalize_transitions_unknown_value_raises() -> None:
    with pytest.raises(FFmpegError):
        _normalize_transitions(["fade_black"], 2)


# ---------------- white-dip filtergraph ----------------


def test_segment_intermediate_vf_cut_has_no_fade() -> None:
    # A plain 'cut' segment is exactly its framing chain, no fade appended.
    vf = _segment_intermediate_vf(None, duration=5.0)
    assert vf == _framing_vf(None)
    assert "fade=" not in vf


def test_segment_intermediate_vf_fade_out_at_tail() -> None:
    # Outgoing segment of a white_dip joint: fade to white over the last 0.10s.
    vf = _segment_intermediate_vf(None, duration=4.0, fade_out_white=True)
    assert vf.startswith(_framing_vf(None))
    assert "fade=t=out:st=3.900:d=0.10:color=white" in vf
    assert "fade=t=in" not in vf


def test_segment_intermediate_vf_fade_in_at_head() -> None:
    # Incoming segment of a white_dip joint: fade in from white at st=0.
    vf = _segment_intermediate_vf(("face_crop", 0.5), duration=6.0, fade_in_white=True)
    # Framing (face-crop) is preserved before the fade.
    assert vf.startswith(_vertical_face_crop_vf(0.5))
    assert "fade=t=in:st=0:d=0.10:color=white" in vf
    assert "fade=t=out" not in vf


def test_segment_intermediate_vf_middle_segment_has_both_fades() -> None:
    # A middle segment can dip to white on both joints at once.
    vf = _segment_intermediate_vf(None, duration=3.0, fade_in_white=True, fade_out_white=True)
    assert "fade=t=in:st=0:d=0.10:color=white" in vf
    assert f"fade=t=out:st={3.0 - WHITE_DIP_SECONDS:.3f}:d=0.10:color=white" in vf


def test_white_dip_seconds_is_short() -> None:
    assert WHITE_DIP_SECONDS == 0.10


# ---------------- ClipFactory single-pass render engine ----------------


def test_single_pass_engine_uses_word_cut_windows_without_intermediates() -> None:
    inputs, graph, rendered = _build_single_pass_montage(
        source="/tmp/source.mp4",
        segments=[(12.123456, 18.654321), (90.25, 96.75)],
        framings=[("face_crop", 0.42), ("fit_blur", 0.5)],
        transitions=["white_dip"],
        audio_crossfade_seconds=0.15,
        subtitles_path=None,
    )
    # Each source window is decoded directly and precisely; no _seg_*.mp4 is
    # produced and the final output is the only encode.
    assert inputs.count("-i") == 2
    assert "12.123456" in inputs
    assert "6.530865" in inputs
    assert "trim=start=0:end=6.530865" in graph
    assert "atrim=start=0:end=6.530865" in graph
    assert "setpts=PTS-STARTPTS" in graph
    assert "asetpts=PTS-STARTPTS" in graph
    assert "acrossfade=d=0.150:o=0" in graph
    assert "atrim=start=0:end=13.030865,asetpts=PTS-STARTPTS[anorm]" in graph
    assert "concat=n=2:v=1:a=0[vconcat]" in graph
    assert f"[vconcat]fps={OUTPUT_VIDEO_FPS:g}" in graph
    assert "trim=start=0:end=13.030865" in graph
    assert "_seg_" not in " ".join(inputs)
    assert rendered == pytest.approx(13.030865, abs=1e-6)


def test_single_pass_engine_names_fit_blur_labels_per_segment() -> None:
    _inputs, graph, _rendered = _build_single_pass_montage(
        source="source.mp4",
        segments=[(0.0, 1.0), (1.0, 2.0)],
        framings=[None, None],
        transitions=["cut"],
        audio_crossfade_seconds=0.15,
        subtitles_path="/tmp/captions.ass",
    )
    assert "[v0bg]" in graph and "[v1bg]" in graph
    assert "[v0bgb]" in graph and "[v1bgb]" in graph
    assert "subtitles='/tmp/captions.ass'" in graph


# ---------------- real render on a synthetic source ----------------


async def _synthesize_and_montage(tmp_path):
    """Build a 3s color+tone source, then montage two windows of it with a
    white_dip joint. Returns (rendered_duration, probe of the output)."""
    import asyncio

    from app.settings import get_settings

    source = tmp_path / "source.mp4"
    settings = get_settings()
    proc = await asyncio.create_subprocess_exec(
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=25:duration=3",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=3",
        "-shortest",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        str(source),
    )
    await proc.communicate()
    assert source.exists()

    out = tmp_path / "montage.mp4"
    rendered = await render_montage_clip(
        source=str(source),
        segments=[(0.0, 1.5), (1.6, 2.9)],
        out_path=str(out),
        workdir=str(tmp_path / "wd"),
        framings=[("fit_blur", 0.5), ("face_crop", 0.5)],
        transitions=["white_dip"],
    )
    assert out.exists()
    return rendered, await probe_media(str(out))


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_render_montage_white_dip_produces_playable_clip(tmp_path) -> None:
    # Real end-to-end render on a synthetic source. Driven via asyncio.run so it
    # runs without an async pytest plugin.
    import asyncio

    rendered, probe = asyncio.run(_synthesize_and_montage(tmp_path))
    # The new non-overlapping joint fade keeps audio and video on the same
    # 2.80s timeline instead of shortening audio by 150ms.
    assert abs(rendered - 2.80) <= (1 / OUTPUT_VIDEO_FPS) + 0.012
    assert probe.has_video and probe.has_audio
    assert probe.duration_seconds == pytest.approx(rendered, abs=1e-6)
    assert probe.video_fps == pytest.approx(OUTPUT_VIDEO_FPS, abs=0.01)
    assert probe.audio_sample_rate == OUTPUT_AUDIO_SAMPLE_RATE
    assert probe.audio_channels == 2
    assert probe.video_duration_seconds is not None
    assert probe.audio_duration_seconds is not None
    assert (
        abs(probe.video_duration_seconds - probe.audio_duration_seconds)
        <= (1 / OUTPUT_VIDEO_FPS) + 0.012
    )


async def _render_silent_source_paths(tmp_path):
    """Exercise both render routes with a video-only source."""
    import asyncio

    from app.settings import get_settings

    settings = get_settings()
    source = tmp_path / "silent_source.mp4"
    proc = await asyncio.create_subprocess_exec(
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=size=640x360:rate=25:duration=4",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        str(source),
    )
    await proc.communicate()
    assert source.exists()

    single = tmp_path / "single_silent.mp4"
    single_duration = await render_montage_clip(
        source=str(source),
        segments=[(0.2, 1.4)],
        out_path=str(single),
        workdir=str(tmp_path / "single_wd"),
    )
    montage = tmp_path / "montage_silent.mp4"
    montage_duration = await render_montage_clip(
        source=str(source),
        segments=[(0.0, 0.7), (1.0, 1.65), (2.0, 2.73)],
        out_path=str(montage),
        workdir=str(tmp_path / "montage_wd"),
        transitions=["cut", "white_dip"],
    )
    return (
        single_duration,
        await probe_media(str(single)),
        montage_duration,
        await probe_media(str(montage)),
    )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)
def test_video_only_source_gets_silent_48khz_audio_in_both_render_routes(
    tmp_path,
) -> None:
    import asyncio

    single_duration, single, montage_duration, montage = asyncio.run(
        _render_silent_source_paths(tmp_path)
    )
    assert single_duration > 0
    assert montage_duration > 0
    for probe in (single, montage):
        assert probe.has_video and probe.has_audio
        assert probe.audio_sample_rate == OUTPUT_AUDIO_SAMPLE_RATE
        assert probe.audio_channels == 2
        assert probe.video_fps == pytest.approx(OUTPUT_VIDEO_FPS, abs=0.01)
