from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..settings import get_settings


class FFmpegError(RuntimeError):
    pass


LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11"


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: float
    has_audio: bool
    has_video: bool


@dataclass(frozen=True)
class RenderQualityReport:
    ok: bool
    problems: list[str]
    duration_seconds: float | None
    expected_duration_seconds: float
    has_audio: bool
    mean_volume_db: float | None
    mid_frame_luma: float | None


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", "replace"),
        stderr.decode("utf-8", "replace"),
    )


# ---------------- probe / scene detection ----------------


async def probe_duration_seconds(path: str) -> float:
    settings = get_settings()
    code, out, err = await _run(
        [
            settings.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            path,
        ]
    )
    if code != 0:
        raise FFmpegError(f"ffprobe failed: {err.strip()}")
    data = json.loads(out)
    return float(data["format"]["duration"])


async def probe_media(path: str) -> MediaProbe:
    settings = get_settings()
    code, out, err = await _run(
        [
            settings.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-show_streams",
            "-of", "json",
            path,
        ]
    )
    if code != 0:
        raise FFmpegError(f"ffprobe failed: {err.strip()}")
    data = json.loads(out)
    streams = data.get("streams") or []
    return MediaProbe(
        duration_seconds=float(data["format"]["duration"]),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        has_video=any(s.get("codec_type") == "video" for s in streams),
    )


_SCENE_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


async def detect_scene_changes(path: str, threshold: float = 0.4) -> list[float]:
    """Return a list of timestamps (seconds) where a scene change is detected."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner", "-nostats",
            "-i", path,
            "-filter:v", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-",
        ]
    )
    if code != 0:
        raise FFmpegError(f"scene detection failed: {err.strip()[-400:]}")
    timestamps = [float(m.group(1)) for m in _SCENE_PTS_RE.finditer(err)]
    return timestamps


_BLACK_RE = re.compile(r"black_start:(-?\d+(?:\.\d+)?)\s+black_end:(-?\d+(?:\.\d+)?)")


async def detect_black_intervals(
    source: str,
    start: float,
    *,
    window_seconds: float = 1.5,
    min_black_seconds: float = 0.1,
    pix_threshold: float = 0.10,
) -> list[tuple[float, float]]:
    """Detect black (near-fully dark) intervals in [start, start+window] of the
    source. Returns (black_start, black_end) offsets RELATIVE to `start` — the
    input-seek resets output timestamps so 0.0 is the window start. Used to catch
    clips that open on a black frame. Best-effort: any ffmpeg error yields []."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner", "-nostats",
            "-ss", f"{max(0.0, start):.3f}",
            "-t", f"{max(0.1, window_seconds):.3f}",
            "-i", source,
            "-vf", f"blackdetect=d={min_black_seconds}:pix_th={pix_threshold}",
            "-an",
            "-f", "null", "-",
        ]
    )
    if code != 0:
        return []
    return [(float(m.group(1)), float(m.group(2))) for m in _BLACK_RE.finditer(err)]


# ---------------- frame extraction ----------------


async def extract_frame(source: str, at_seconds: float, out_path: str) -> None:
    """Extract a single frame at the given timestamp as JPEG."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{at_seconds:.3f}",
            "-i", source,
            "-frames:v", "1",
            "-vf", "scale='min(512,iw)':-2",
            "-q:v", "5",
            out_path,
        ]
    )
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"frame extract failed at {at_seconds}: {err.strip()}")


_MEAN_VOLUME_RE = re.compile(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB")
_YAVG_RE = re.compile(r"lavfi\.signalstats\.YAVG=(\d+(?:\.\d+)?)")


async def measure_mean_volume_db(path: str) -> float | None:
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner", "-nostats",
            "-i", path,
            "-af", "volumedetect",
            "-f", "null", "-",
        ]
    )
    if code != 0:
        return None
    match = _MEAN_VOLUME_RE.search(err)
    return float(match.group(1)) if match else None


async def sample_mid_frame_luma(path: str, duration_seconds: float) -> float | None:
    settings = get_settings()
    code, out, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner", "-nostats",
            "-ss", f"{max(0.0, duration_seconds / 2.0):.3f}",
            "-i", path,
            "-frames:v", "1",
            "-vf", "signalstats,metadata=mode=print:file=-",
            "-f", "null", "-",
        ]
    )
    if code != 0:
        return None
    match = _YAVG_RE.search(out + err)
    return float(match.group(1)) if match else None


async def validate_rendered_clip(
    *,
    path: str,
    expected_duration_seconds: float,
    duration_tolerance_seconds: float = 0.5,
    min_mean_volume_db: float = -55.0,
    min_mid_frame_luma: float = 4.0,
) -> RenderQualityReport:
    problems: list[str] = []
    try:
        probe = await probe_media(path)
    except FFmpegError as exc:
        return RenderQualityReport(
            ok=False,
            problems=[f"probe_failed:{str(exc)[:120]}"],
            duration_seconds=None,
            expected_duration_seconds=expected_duration_seconds,
            has_audio=False,
            mean_volume_db=None,
            mid_frame_luma=None,
        )

    if abs(probe.duration_seconds - expected_duration_seconds) > duration_tolerance_seconds:
        problems.append(
            f"duration_mismatch:{probe.duration_seconds:.2f}!={expected_duration_seconds:.2f}"
        )
    if not probe.has_video:
        problems.append("missing_video")
    if not probe.has_audio:
        problems.append("missing_audio")

    mean_volume = await measure_mean_volume_db(path) if probe.has_audio else None
    if probe.has_audio and mean_volume is None:
        problems.append("volume_unreadable")
    elif mean_volume is not None and mean_volume < min_mean_volume_db:
        problems.append(f"volume_too_low:{mean_volume:.1f}dB")

    luma = await sample_mid_frame_luma(path, probe.duration_seconds) if probe.has_video else None
    if probe.has_video and luma is None:
        problems.append("mid_frame_unreadable")
    elif luma is not None and luma < min_mid_frame_luma:
        problems.append(f"mid_frame_too_dark:{luma:.1f}")

    return RenderQualityReport(
        ok=not problems,
        problems=problems,
        duration_seconds=probe.duration_seconds,
        expected_duration_seconds=expected_duration_seconds,
        has_audio=probe.has_audio,
        mean_volume_db=mean_volume,
        mid_frame_luma=luma,
    )


# ---------------- download ----------------


async def yt_dlp_download(url: str, out_dir: str) -> str:
    settings = get_settings()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_template = os.path.join(out_dir, "source.%(ext)s")

    cmd = [
        settings.yt_dlp_bin,
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        # YouTube gates media behind a JS "n challenge": needs a JS runtime (deno)
        # plus the EJS solver script, and browser cookies to dodge 403 bot-blocks.
        "--remote-components", "ejs:github",
        "--retries", "5",
        "--fragment-retries", "10",
        "--quiet", "--no-warnings",
        "-o", out_template,
    ]
    if settings.yt_dlp_cookies_from_browser:
        cmd += ["--cookies-from-browser", settings.yt_dlp_cookies_from_browser]
    cmd.append(url)
    code, _, err = await _run(cmd)
    if code != 0:
        raise FFmpegError(f"yt-dlp failed: {err.strip()[-2000:]}")

    candidates = list(Path(out_dir).glob("source.*"))
    if not candidates:
        raise FFmpegError("yt-dlp produced no output file")
    return str(candidates[0].resolve())


# ---------------- render: single-window ----------------


def _vertical_fit_blur_vf(subtitles_path: str | None = None) -> str:
    """Fit the whole (usually 16:9) frame into 1080x1920 over a blurred fill of
    itself, so screen recordings, chats and slides stay readable instead of being
    centre-cropped into an unreadable strip. Optional caption burn-in comes last.
    """
    graph = (
        "split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=20:2[bgb];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fgf];"
        "[bgb][fgf]overlay=(W-w)/2:(H-h)/2,setsar=1"
    )
    if subtitles_path:
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        graph += f",subtitles='{sub_esc}'"
    return graph


def _vertical_face_crop_vf(center_x: float, subtitles_path: str | None = None) -> str:
    """Crop a full-height 9:16 window centred on the main speaker's face, then
    scale to 1080x1920. Unlike the fit+blur builder this fills the frame edge to
    edge (no letterbox), so a talking head reads at full size instead of a thin
    strip. Reserve this for talking-head shots; keep fit+blur for screens/slides.

    `center_x` (0..1) is the average horizontal face position. The window width
    is 9:16 of the source height, and its x is clamped so it never leaves the
    frame. Expressions use iw/ih so it stays resolution-independent. Optional
    caption burn-in comes last (same escaping as `_vertical_fit_blur_vf`).
    """
    cx = max(0.0, min(1.0, center_x))
    # w = even 9:16 slice of the full height; x centres on the face (cx*iw) minus
    # half the window, clamped to [0, iw-ow]. In crop's x expr, `ow` is the crop
    # output width and `iw` the source width; commas inside min/max must be
    # escaped so the filtergraph parser keeps this as one filter.
    crop = (
        "crop=floor(ih*9/16/2)*2:ih:"
        f"max(0\\,min(iw-ow\\,{cx:.4f}*iw-ow/2)):0"
    )
    graph = f"{crop},scale=1080:1920,setsar=1"
    if subtitles_path:
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        graph += f",subtitles='{sub_esc}'"
    return graph


def _framing_vf(
    framing: tuple[str, float] | None, subtitles_path: str | None = None
) -> str:
    """Pick the vertical filter chain. `framing` is ('face_crop', center_x) or
    ('fit_blur', _)/None. Default = fit+blur (current behaviour), so nothing
    changes until the caller opts into face-crop.
    """
    if framing is not None and framing[0] == "face_crop":
        return _vertical_face_crop_vf(framing[1], subtitles_path)
    return _vertical_fit_blur_vf(subtitles_path)


async def render_vertical_clip(
    *,
    source: str,
    start: float,
    end: float,
    out_path: str,
    subtitles_path: str | None = None,
    framing: tuple[str, float] | None = None,
) -> None:
    settings = get_settings()
    duration = max(0.1, end - start)

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
        "-vf", _framing_vf(framing, subtitles_path),
        "-af", LOUDNORM_FILTER,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main", "-level", "4.1",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"render failed: {err.strip()}")


# ---------------- render: multi-segment montage ----------------


async def _render_single_segment_intermediate(
    *,
    source: str,
    start: float,
    end: float,
    out_path: str,
    framing: tuple[str, float] | None = None,
) -> None:
    """Render a single segment as a temporary file. Used as input to the concat."""
    settings = get_settings()
    duration = max(0.1, end - start)
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
        "-vf", _framing_vf(framing),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main", "-level", "4.1",
        "-c:a", "aac", "-b:a", "128k",
        "-ar", "48000", "-ac", "2",
        out_path,
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"segment render failed: {err.strip()}")


async def render_montage_clip(
    *,
    source: str,
    segments: list[tuple[float, float]],     # list of (start, end) in source seconds
    out_path: str,
    workdir: str,
    subtitles_path: str | None = None,
    audio_crossfade_seconds: float = 0.15,
    framing: tuple[str, float] | None = None,
) -> float:
    """Render a multi-segment vertical clip from a horizontal source.

    Strategy:
      1. Render each segment to an intermediate mp4 (vertical, AAC audio).
      2. Concat with filter_complex: video = hard cut concat, audio = acrossfade
         between adjacent segments (default 150 ms), then loudness-normalize.
      3. Optional subtitles burn-in on the final mux.

    Returns the rendered duration in seconds.
    """
    settings = get_settings()
    if not segments:
        raise FFmpegError("no segments to render")
    if len(segments) == 1:
        # Single segment — use the simpler renderer
        s, e = segments[0]
        await render_vertical_clip(
            source=source, start=s, end=e, out_path=out_path,
            subtitles_path=subtitles_path, framing=framing,
        )
        return max(0.1, e - s)

    Path(workdir).mkdir(parents=True, exist_ok=True)
    intermediate_paths: list[str] = []
    seg_durations: list[float] = []
    for idx, (s, e) in enumerate(segments):
        seg_path = os.path.join(workdir, f"_seg_{idx:02d}.mp4")
        await _render_single_segment_intermediate(
            source=source, start=s, end=e, out_path=seg_path, framing=framing
        )
        intermediate_paths.append(seg_path)
        seg_durations.append(max(0.1, e - s))

    # Build filter_complex string
    inputs_args: list[str] = []
    for path in intermediate_paths:
        inputs_args.extend(["-i", path])

    n = len(intermediate_paths)
    # Video: pure concat (cut transitions)
    v_chain = "".join(f"[{i}:v:0]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vraw]"
    # Audio: pairwise acrossfade
    a_steps: list[str] = []
    if n == 2:
        a_steps.append(
            f"[0:a:0][1:a:0]acrossfade=d={audio_crossfade_seconds}:c1=tri:c2=tri[aout]"
        )
    else:
        # Cascade: a01 = 0+1, then a012 = a01+2, etc.
        prev = "[0:a:0]"
        for i in range(1, n):
            out_label = "[aout]" if i == n - 1 else f"[a{i}]"
            a_steps.append(
                f"{prev}[{i}:a:0]acrossfade=d={audio_crossfade_seconds}:c1=tri:c2=tri{out_label}"
            )
            prev = out_label

    filter_parts = [v_chain, *a_steps]
    audio_map = "[aout]"
    if a_steps:
        filter_parts.append(f"[aout]{LOUDNORM_FILTER}[anorm]")
        audio_map = "[anorm]"

    # Add subtitles burn-in on video chain if requested
    if subtitles_path:
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        filter_parts.append(f"[vraw]subtitles='{sub_esc}'[v]")
        v_map = "[v]"
    else:
        v_map = "[vraw]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner", "-loglevel", "error", "-y",
        *inputs_args,
        "-filter_complex", filter_complex,
        "-map", v_map, "-map", audio_map,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main", "-level", "4.1",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        out_path,
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"montage render failed: {err.strip()[-400:]}")

    # Crossfade overlaps reduce final duration: total = sum(durations) - (n-1)*crossfade
    rendered = sum(seg_durations) - max(0, (n - 1)) * audio_crossfade_seconds

    # Cleanup intermediates
    for path in intermediate_paths:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    return max(0.1, rendered)
