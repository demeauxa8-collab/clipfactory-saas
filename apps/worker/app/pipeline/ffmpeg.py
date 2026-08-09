from __future__ import annotations

import asyncio
import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..settings import get_settings

if TYPE_CHECKING:
    from ..models import Transcript
    from .audio_map import AudioMap
    from .audio_render_plan import AudioRenderPlan
    from .edl import CompiledEDL


class FFmpegError(RuntimeError):
    pass


LOUDNORM_FILTER = "loudnorm=I=-14:TP=-1.5:LRA=11"
OUTPUT_VIDEO_FPS = 30.0
OUTPUT_AUDIO_SAMPLE_RATE = 48_000

# Intentional dip-to-white at a montage joint: the outgoing segment fades to
# white over its last WHITE_DIP_SECONDS and the incoming one fades in from white
# over its first WHITE_DIP_SECONDS. Baked into the intermediates so the concat
# stays a hard cut; the audio acrossfade is unchanged and no frames are trimmed.
WHITE_DIP_SECONDS = 0.10


@dataclass(frozen=True)
class MediaProbe:
    duration_seconds: float
    has_audio: bool
    has_video: bool
    video_duration_seconds: float | None = None
    audio_duration_seconds: float | None = None
    video_fps: float | None = None
    audio_sample_rate: int | None = None
    audio_channels: int | None = None


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
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            path,
        ]
    )
    if code != 0:
        raise FFmpegError(f"ffprobe failed: {err.strip()}")
    data = json.loads(out)
    return float(data["format"]["duration"])


async def probe_media(path: str, *, ffprobe_bin: str | None = None) -> MediaProbe:
    probe_binary = ffprobe_bin or get_settings().ffprobe_bin
    code, out, err = await _run(
        [
            probe_binary,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_streams",
            "-of",
            "json",
            path,
        ]
    )
    if code != 0:
        raise FFmpegError(f"ffprobe failed: {err.strip()}")
    data = json.loads(out)
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    def optional_float(value: object) -> float | None:
        try:
            return float(value) if value not in (None, "N/A") else None
        except (TypeError, ValueError):
            return None

    def stream_duration(stream: dict[str, object] | None) -> float | None:
        if not stream:
            return None
        direct = optional_float(stream.get("duration"))
        if direct is not None:
            return direct
        ticks = optional_float(stream.get("duration_ts"))
        time_base = str(stream.get("time_base") or "")
        if ticks is not None and "/" in time_base:
            numerator, denominator = time_base.split("/", 1)
            try:
                return ticks * float(numerator) / float(denominator)
            except (TypeError, ValueError, ZeroDivisionError):
                return None
        return None

    def frame_rate(stream: dict[str, object] | None) -> float | None:
        if not stream:
            return None
        rate = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "")
        if "/" not in rate:
            return optional_float(rate)
        numerator, denominator = rate.split("/", 1)
        try:
            value = float(numerator) / float(denominator)
            return value if value > 0 else None
        except (TypeError, ValueError, ZeroDivisionError):
            return None

    return MediaProbe(
        duration_seconds=float(data["format"]["duration"]),
        has_audio=audio is not None,
        has_video=video is not None,
        video_duration_seconds=stream_duration(video),
        audio_duration_seconds=stream_duration(audio),
        video_fps=frame_rate(video),
        audio_sample_rate=(
            int(str(audio["sample_rate"])) if audio and audio.get("sample_rate") else None
        ),
        audio_channels=(int(str(audio["channels"])) if audio and audio.get("channels") else None),
    )


async def analyze_audio_map(
    path: str,
    *,
    silence_noise_db: float = -38.0,
    min_silence_seconds: float = 0.30,
    ffmpeg_bin: str | None = None,
    ffprobe_bin: str | None = None,
) -> AudioMap:
    """Measure silence, loudness and peaks in one local audio decode pass."""
    from .audio_map import build_audio_map

    if not math.isfinite(silence_noise_db) or not -100.0 <= silence_noise_db <= 0.0:
        raise FFmpegError("silence_noise_db must be finite and in [-100, 0]")
    if not math.isfinite(min_silence_seconds) or not 0.05 <= min_silence_seconds <= 5.0:
        raise FFmpegError("min_silence_seconds must be finite and in [0.05, 5]")
    probe = await probe_media(path, ffprobe_bin=ffprobe_bin)
    if not probe.has_audio:
        raise FFmpegError("audio analysis source has no audio stream")
    binary = ffmpeg_bin or get_settings().ffmpeg_bin
    noise = _ffmpeg_number(silence_noise_db, label="silence noise")
    silence_duration = _ffmpeg_number(
        min_silence_seconds,
        label="minimum silence duration",
    )
    graph = (
        "[0:a]asplit=3[a_silence][a_loudness][a_stats];"
        f"[a_silence]silencedetect=noise={noise}dB:d={silence_duration}[a_silence_out];"
        "[a_loudness]ebur128=peak=true[a_loudness_out];"
        "[a_stats]astats=metadata=1:reset=0[a_stats_out]"
    )
    code, _, err = await _run(
        [
            binary,
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-filter_complex",
            graph,
            "-map",
            "[a_silence_out]",
            "-map",
            "[a_loudness_out]",
            "-map",
            "[a_stats_out]",
            "-f",
            "null",
            "-",
        ]
    )
    if code != 0:
        raise FFmpegError(f"audio analysis failed: {err.strip()[-800:]}")
    return build_audio_map(
        silencedetect_output=err,
        duration_seconds=probe.duration_seconds,
        ebur128_output=err,
        astats_output=err,
    )


_SCENE_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


async def detect_scene_changes(path: str, threshold: float = 0.4) -> list[float]:
    """Return a list of timestamps (seconds) where a scene change is detected."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-filter:v",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
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
    ffmpeg_bin: str | None = None,
) -> list[tuple[float, float]]:
    """Detect black (near-fully dark) intervals in [start, start+window] of the
    source. Returns (black_start, black_end) offsets RELATIVE to `start` — the
    input-seek resets output timestamps so 0.0 is the window start. Used to catch
    clips that open on a black frame. Best-effort: any ffmpeg error yields []."""
    binary = ffmpeg_bin or get_settings().ffmpeg_bin
    code, _, err = await _run(
        [
            binary,
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{max(0.0, start):.3f}",
            "-t",
            f"{max(0.1, window_seconds):.3f}",
            "-i",
            source,
            "-vf",
            f"blackdetect=d={min_black_seconds}:pix_th={pix_threshold}",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    if code != 0:
        return []
    return [(float(m.group(1)), float(m.group(2))) for m in _BLACK_RE.finditer(err)]


async def detect_black_open_for_segments(
    source: str,
    segments: list[tuple[float, float]],
    *,
    window_seconds: float = 1.5,
    min_black_seconds: float = 0.1,
    pix_threshold: float = 0.10,
) -> list[list[tuple[float, float]]]:
    """Per-segment black-open detection for montages. Runs `detect_black_intervals`
    at the opening of each segment and returns one interval list per segment (same
    index order). Lets the runner guard every joint of a multi-segment clip, not
    just the first segment's opening, without changing `detect_black_intervals`.
    Offsets are RELATIVE to each segment's own start (0.0 == that segment's start).
    """
    results: list[list[tuple[float, float]]] = []
    for start, _end in segments:
        results.append(
            await detect_black_intervals(
                source,
                start,
                window_seconds=window_seconds,
                min_black_seconds=min_black_seconds,
                pix_threshold=pix_threshold,
            )
        )
    return results


# ---------------- frame extraction ----------------


async def extract_frame(source: str, at_seconds: float, out_path: str) -> None:
    """Extract a single frame at the given timestamp as JPEG."""
    settings = get_settings()
    code, _, err = await _run(
        [
            settings.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{at_seconds:.3f}",
            "-i",
            source,
            "-frames:v",
            "1",
            "-vf",
            "scale='min(512,iw)':-2",
            "-q:v",
            "5",
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
            "-hide_banner",
            "-nostats",
            "-i",
            path,
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
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
            "-hide_banner",
            "-nostats",
            "-ss",
            f"{max(0.0, duration_seconds / 2.0):.3f}",
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            "signalstats,metadata=mode=print:file=-",
            "-f",
            "null",
            "-",
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

    # Idempotent re-runs: reuse a source already sitting in the workdir instead
    # of re-hitting YouTube (repeated downloads of the same video get 403'd).
    cached = [p for p in Path(out_dir).glob("source.*") if p.stat().st_size > 0]
    if cached:
        return str(cached[0].resolve())

    out_template = os.path.join(out_dir, "source.%(ext)s")

    cmd = [
        settings.yt_dlp_bin,
        "-f",
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/best[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "--no-playlist",
        # YouTube gates media behind a JS "n challenge": needs a JS runtime (deno)
        # plus the EJS solver script, and browser cookies to dodge 403 bot-blocks.
        "--remote-components",
        "ejs:github",
        "--retries",
        "5",
        "--fragment-retries",
        "10",
        "--quiet",
        "--no-warnings",
        "-o",
        out_template,
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
    crop = f"crop=floor(ih*9/16/2)*2:ih:max(0\\,min(iw-ow\\,{cx:.4f}*iw-ow/2)):0"
    graph = f"{crop},scale=1080:1920,setsar=1"
    if subtitles_path:
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        graph += f",subtitles='{sub_esc}'"
    return graph


def _framing_vf(framing: tuple[str, float] | None, subtitles_path: str | None = None) -> str:
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
    source_probe = await probe_media(source)
    if not source_probe.has_video:
        raise FFmpegError("source has no video stream")

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.6f}",
        "-accurate_seek",
        "-i",
        source,
    ]
    if not source_probe.has_audio:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
    cmd.extend(
        [
            "-t",
            f"{duration:.6f}",
            "-map",
            "0:v:0",
            "-map",
            "0:a:0" if source_probe.has_audio else "1:a:0",
            "-vf",
            _framing_vf(framing, subtitles_path) + ",fps=30",
            "-af",
            (
                f"{LOUDNORM_FILTER},aresample={OUTPUT_AUDIO_SAMPLE_RATE},"
                "aformat=channel_layouts=stereo"
                if source_probe.has_audio
                else f"aresample={OUTPUT_AUDIO_SAMPLE_RATE},aformat=channel_layouts=stereo"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "main",
            "-level",
            "4.1",
            "-r",
            f"{OUTPUT_VIDEO_FPS:g}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ar",
            str(OUTPUT_AUDIO_SAMPLE_RATE),
            "-ac",
            "2",
            "-movflags",
            "+faststart",
            out_path,
        ]
    )
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"render failed: {err.strip()}")


# ---------------- render: multi-segment montage ----------------


Framing = tuple[str, float]


def _normalize_framings(
    framings: Framing | list[Framing | None] | None,
    n: int,
) -> list[Framing | None]:
    """Normalise the montage framing input into exactly one framing per segment.

    Accepts, for backward compatibility, either a single framing tuple
    (`('face_crop', cx)` / `('fit_blur', _)`) applied to every segment, or a
    per-segment list. `None` (or a `None` entry) means fit+blur for that segment.
    A single-entry list is replicated across all segments. Any other length that
    is neither 1 nor `n` is a caller error.
    """
    if framings is None:
        return [None] * n
    if isinstance(framings, tuple):
        return [framings] * n
    items = list(framings)
    if not items:
        return [None] * n
    if len(items) == 1:
        return [items[0]] * n
    if len(items) == n:
        return items
    raise FFmpegError(f"framings length {len(items)} does not match {n} segments")


def _normalize_transitions(transitions: list[str] | None, n: int) -> list[str]:
    """Normalise the per-joint transition list. A montage of `n` segments has
    `n - 1` joints; `None` means all hard cuts. Valid values: 'cut' | 'white_dip'.
    """
    joints = max(0, n - 1)
    if transitions is None:
        return ["cut"] * joints
    items = list(transitions)
    if len(items) != joints:
        raise FFmpegError(f"transitions length {len(items)} must equal segments-1 ({joints})")
    for value in items:
        if value not in ("cut", "white_dip"):
            raise FFmpegError(f"unknown transition {value!r}")
    return items


def _segment_intermediate_vf(
    framing: Framing | None,
    *,
    duration: float,
    fade_in_white: bool = False,
    fade_out_white: bool = False,
) -> str:
    """Build the video filter chain for one montage intermediate: the segment's
    own framing first, then any dip-to-white fades at joints handled by THIS
    segment. Fade-in sits at the head (st=0) and fade-out at the tail
    (st=duration-WHITE_DIP_SECONDS); neither trims frames, so durations are
    unchanged. Pure/deterministic so the command builder is testable.
    """
    vf = _framing_vf(framing)
    fades: list[str] = []
    if fade_in_white:
        fades.append(f"fade=t=in:st=0:d={WHITE_DIP_SECONDS:.2f}:color=white")
    if fade_out_white:
        st = max(0.0, duration - WHITE_DIP_SECONDS)
        fades.append(f"fade=t=out:st={st:.3f}:d={WHITE_DIP_SECONDS:.2f}:color=white")
    if fades:
        vf = vf + "," + ",".join(fades)
    return vf


async def _render_single_segment_intermediate(
    *,
    source: str,
    start: float,
    end: float,
    out_path: str,
    framing: Framing | None = None,
    fade_in_white: bool = False,
    fade_out_white: bool = False,
) -> None:
    """Render a single segment as a temporary file. Used as input to the concat.

    `fade_in_white` / `fade_out_white` bake the dip-to-white at the joints this
    segment touches; the caller decides them from the transition list.
    """
    settings = get_settings()
    duration = max(0.1, end - start)
    vf = _segment_intermediate_vf(
        framing,
        duration=duration,
        fade_in_white=fade_in_white,
        fade_out_white=fade_out_white,
    )
    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        source,
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "main",
        "-level",
        "4.1",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        out_path,
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"segment render failed: {err.strip()}")


def _single_pass_video_parts(
    *,
    input_idx: int,
    duration: float,
    framing: Framing | None,
    fade_in_white: bool,
    fade_out_white: bool,
) -> list[str]:
    """Video graph for one ClipFactory edit segment.

    Every label includes ``input_idx`` so several fit+blur graphs can coexist in
    one filter_complex. The source input is already accurately seeked near the
    requested word boundary; trim is the final guard that fixes the decoded
    window duration, and setpts creates a zero-based montage segment.
    """
    dur = f"{duration:.6f}"
    parts = [f"[{input_idx}:v:0]trim=start=0:end={dur},setpts=PTS-STARTPTS[vt{input_idx}]"]
    if framing is not None and framing[0] == "face_crop":
        cx = max(0.0, min(1.0, framing[1]))
        chain = (
            f"[vt{input_idx}]crop=floor(ih*9/16/2)*2:ih:"
            f"max(0\\,min(iw-ow\\,{cx:.4f}*iw-ow/2)):0,"
            f"scale=1080:1920,setsar=1"
        )
    else:
        parts.extend(
            [
                f"[vt{input_idx}]split=2[v{input_idx}bg][v{input_idx}fg]",
                f"[v{input_idx}bg]scale=1080:1920:"
                "force_original_aspect_ratio=increase,crop=1080:1920,"
                f"boxblur=20:2[v{input_idx}bgb]",
                f"[v{input_idx}fg]scale=1080:1920:"
                f"force_original_aspect_ratio=decrease[v{input_idx}fgf]",
            ]
        )
        chain = f"[v{input_idx}bgb][v{input_idx}fgf]overlay=(W-w)/2:(H-h)/2,setsar=1"

    fades: list[str] = []
    if fade_in_white:
        fades.append(f"fade=t=in:st=0:d={WHITE_DIP_SECONDS:.2f}:color=white")
    if fade_out_white:
        fade_start = max(0.0, duration - WHITE_DIP_SECONDS)
        fades.append(f"fade=t=out:st={fade_start:.6f}:d={WHITE_DIP_SECONDS:.2f}:color=white")
    if fades:
        chain += "," + ",".join(fades)
    parts.append(chain + f"[v{input_idx}]")
    return parts


def _build_single_pass_montage(
    *,
    source: str,
    segments: list[tuple[float, float]],
    framings: Framing | list[Framing | None] | None,
    transitions: list[str] | None,
    audio_crossfade_seconds: float,
    subtitles_path: str | None,
    source_has_audio: bool = True,
) -> tuple[list[str], str, float]:
    """Compile the proprietary ClipFactory edit plan into one FFmpeg graph.

    There is one accurately-seeked decoder input per source window, but only one
    video/audio encode: the final output. This removes the old intermediate MP4
    generation and its second lossy encode. ``trim``/``atrim`` plus timestamp
    resets make the transcript-derived boundaries authoritative inside FFmpeg.

    Audio joints use ``acrossfade overlap=0``. The old overlapping crossfade
    shortened audio by 150ms per joint while video and captions kept their full
    length; after several joints they described different instants. A sequential
    fade keeps the smoothing without shortening the intended timeline. Video
    boundaries remain quantized to the source frame grid (for example 40ms at
    25fps); audio boundaries are sample-accurate.
    """
    if not segments:
        raise FFmpegError("no segments to render")
    n = len(segments)
    seg_framings = _normalize_framings(framings, n)
    seg_transitions = _normalize_transitions(transitions, n)
    durations: list[float] = []
    inputs: list[str] = []
    parts: list[str] = []

    for idx, (start, end) in enumerate(segments):
        duration = end - start
        if duration <= 0:
            raise FFmpegError(f"invalid segment {idx}: end must be after start")
        durations.append(duration)
        inputs.extend(
            [
                "-ss",
                f"{max(0.0, start):.6f}",
                "-t",
                f"{duration:.6f}",
                "-accurate_seek",
                "-i",
                source,
            ]
        )
        fade_in = idx > 0 and seg_transitions[idx - 1] == "white_dip"
        fade_out = idx < n - 1 and seg_transitions[idx] == "white_dip"
        parts.extend(
            _single_pass_video_parts(
                input_idx=idx,
                duration=duration,
                framing=seg_framings[idx],
                fade_in_white=fade_in,
                fade_out_white=fade_out,
            )
        )
        if source_has_audio:
            parts.append(
                f"[{idx}:a:0]atrim=start=0:end={duration:.6f},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=channel_layouts=stereo[a{idx}]"
            )

    if not source_has_audio:
        silent_input_idx = n
        inputs.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
        split_labels = "".join(f"[asilent{i}]" for i in range(n))
        parts.append(f"[{silent_input_idx}:a:0]asplit={n}{split_labels}")
        for idx, duration in enumerate(durations):
            parts.append(
                f"[asilent{idx}]atrim=start=0:end={duration:.6f},asetpts=PTS-STARTPTS[a{idx}]"
            )

    parts.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vconcat]")
    intended = sum(durations)
    parts.append(
        f"[vconcat]fps={OUTPUT_VIDEO_FPS:g},"
        "tpad=stop_mode=clone:stop_duration=0.100,"
        f"trim=start=0:end={intended:.6f},setpts=PTS-STARTPTS[vraw]"
    )

    if n == 1:
        audio_label = "[a0]"
    else:
        previous = "[a0]"
        for idx in range(1, n):
            out = "[ajoin]" if idx == n - 1 else f"[ajoin{idx}]"
            parts.append(
                f"{previous}[a{idx}]acrossfade=d={audio_crossfade_seconds:.3f}:"
                f"o=0:c1=tri:c2=tri{out}"
            )
            previous = out
        audio_label = "[ajoin]"
    audio_finish = (
        f"{LOUDNORM_FILTER},aresample={OUTPUT_AUDIO_SAMPLE_RATE},aformat=channel_layouts=stereo"
        if source_has_audio
        else f"aresample={OUTPUT_AUDIO_SAMPLE_RATE},aformat=channel_layouts=stereo"
    )
    # loudnorm can add a short filter tail on real material (60ms observed on
    # the reference fixture). Re-trim after normalization so muxing cannot move
    # the edit's final word or exceed the shared intended timeline.
    parts.append(
        f"{audio_label}{audio_finish},atrim=start=0:end={intended:.6f},"
        "asetpts=PTS-STARTPTS[anorm]"
    )

    if subtitles_path:
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        parts.append(f"[vraw]subtitles='{sub_esc}'[vout]")

    return inputs, ";".join(parts), intended


def _validate_mux_timeline(
    probe: MediaProbe,
    intended_seconds: float,
    *,
    expected_fps: float = OUTPUT_VIDEO_FPS,
) -> None:
    """Enforce the physical A/V precision contract of the render engine.

    Transcript/audio boundaries are continuous-time values; encoded video is
    quantized to frames. With the fixed 30 fps output policy, every stream and
    the container must stay within one frame (plus a small mux allowance) of
    the intended edit timeline, and audio/video may not drift further apart.
    """
    fps = probe.video_fps or expected_fps
    tolerance = (1.0 / fps) + 0.012
    measured = {
        "container": probe.duration_seconds,
        "video": probe.video_duration_seconds,
        "audio": probe.audio_duration_seconds,
    }
    for label, duration in measured.items():
        if duration is not None and abs(duration - intended_seconds) > tolerance:
            raise FFmpegError(
                f"{label} timeline drift {duration:.6f}s vs "
                f"{intended_seconds:.6f}s exceeds {tolerance:.6f}s"
            )
    if (
        probe.video_duration_seconds is not None
        and probe.audio_duration_seconds is not None
        and abs(probe.video_duration_seconds - probe.audio_duration_seconds) > tolerance
    ):
        raise FFmpegError(
            "audio/video timeline drift exceeds one output frame: "
            f"video={probe.video_duration_seconds:.6f}s "
            f"audio={probe.audio_duration_seconds:.6f}s"
        )
    if probe.video_fps is not None and abs(probe.video_fps - expected_fps) > 0.01:
        raise FFmpegError(
            f"unexpected output frame rate {probe.video_fps:.6f}; expected {expected_fps:.6f}"
        )
    if probe.audio_sample_rate != OUTPUT_AUDIO_SAMPLE_RATE or probe.audio_channels != 2:
        raise FFmpegError(
            "unexpected output audio format: "
            f"sample_rate={probe.audio_sample_rate} channels={probe.audio_channels}"
        )


def _escape_subtitles_filter_path(path: str) -> str:
    """Escape a trusted local path for one quoted FFmpeg filter argument."""
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _ffmpeg_number(value: float, *, label: str) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise FFmpegError(f"{label} must be finite")
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def _resolved_audio_mix_graph(
    *,
    edl: CompiledEDL,
    audio_plan: AudioRenderPlan | None,
    first_input_index: int,
    dialogue_label: str,
    source_has_audio: bool,
) -> tuple[list[str], list[str]]:
    """Build trusted asset inputs and the final dialogue/music/SFX master.

    Paths come only from ``ResolvedAudioAsset`` objects produced by the local
    registry.  No EDL asset ID or model-controlled path is interpolated into
    FFmpeg syntax.
    """
    intended_seconds = edl.duration_frames / edl.fps
    intended = f"{intended_seconds:.6f}"
    asset_input_args: list[str] = []
    graph: list[str] = []
    mix_labels: list[str] = []

    if audio_plan is not None:
        if audio_plan.duration_ms != edl.duration_ms:
            raise FFmpegError("resolved audio plan duration does not match the EDL")
        expected_music = Counter(track.asset_id for track in edl.music)
        resolved_music = Counter(item.track.asset_id for item in audio_plan.music)
        expected_sfx = Counter((cue.asset_id, cue.timeline_at_ms) for cue in edl.sfx)
        resolved_sfx = Counter(
            (item.cue.asset_id, item.cue.timeline_at_ms) for item in audio_plan.sfx
        )
        if expected_music != resolved_music or expected_sfx != resolved_sfx:
            raise FFmpegError("resolved audio plan assets do not match the compiled EDL")

    music_needs_sidechain = bool(
        audio_plan
        and any(item.ducking.id != "none" for item in audio_plan.music)
    )
    if music_needs_sidechain:
        graph.append(
            f"[{dialogue_label}]asplit=2[a_dialogue_mix][a_dialogue_sidechain]"
        )
        mix_labels.append("[a_dialogue_mix]")
    else:
        mix_labels.append(f"[{dialogue_label}]")

    next_input = first_input_index
    if audio_plan is not None:
        for track_index, item in enumerate(audio_plan.music):
            if not item.asset.path.is_file():
                raise FFmpegError("resolved music asset file is missing")
            if item.track.loop:
                asset_input_args.extend(("-stream_loop", "-1"))
            asset_input_args.extend(("-i", str(item.asset.path)))
            duration_seconds = (item.track.timeline_out_ms - item.track.timeline_in_ms) / 1000
            duration = _ffmpeg_number(duration_seconds, label="music duration")
            gain = _ffmpeg_number(item.effective_gain_db, label="music gain")
            fade_in_ms = min(
                item.track.fade_in_ms,
                round(duration_seconds * 1000),
            )
            fade_out_ms = min(
                item.track.fade_out_ms,
                round(duration_seconds * 1000),
            )
            chain = (
                f"[{next_input}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                "aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
                f"apad=pad_dur={duration},atrim=duration={duration},volume={gain}dB"
            )
            if fade_in_ms > 0:
                chain += f",afade=t=in:st=0:d={fade_in_ms / 1000:.3f}"
            if fade_out_ms > 0:
                fade_start = max(0.0, duration_seconds - fade_out_ms / 1000)
                chain += f",afade=t=out:st={fade_start:.3f}:d={fade_out_ms / 1000:.3f}"
            chain += (
                f",adelay=delays={item.track.timeline_in_ms}:all=1"
                f"[a_music_{track_index}]"
            )
            graph.append(chain)
            music_label = f"[a_music_{track_index}]"
            if item.ducking.id != "none":
                preset = item.ducking
                threshold = _ffmpeg_number(preset.threshold or 0.0, label="duck threshold")
                ratio = _ffmpeg_number(preset.ratio or 1.0, label="duck ratio")
                attack = _ffmpeg_number(preset.attack_ms or 0.0, label="duck attack")
                release = _ffmpeg_number(preset.release_ms or 0.0, label="duck release")
                graph.append(
                    f"{music_label}[a_dialogue_sidechain]"
                    f"sidechaincompress=threshold={threshold}:ratio={ratio}:"
                    f"attack={attack}:release={release}[a_music_ducked_{track_index}]"
                )
                music_label = f"[a_music_ducked_{track_index}]"
            mix_labels.append(music_label)
            next_input += 1

        for cue_index, item in enumerate(audio_plan.sfx):
            if not item.asset.path.is_file():
                raise FFmpegError("resolved SFX asset file is missing")
            asset_input_args.extend(("-i", str(item.asset.path)))
            duration_seconds = item.asset.asset.duration_seconds
            duration = _ffmpeg_number(duration_seconds, label="SFX duration")
            gain = _ffmpeg_number(item.effective_gain_db, label="SFX gain")
            fade_in_ms = min(item.asset.asset.mix.fade_in_ms, round(duration_seconds * 1000))
            fade_out_ms = min(item.asset.asset.mix.fade_out_ms, round(duration_seconds * 1000))
            chain = (
                f"[{next_input}:a]atrim=duration={duration},asetpts=PTS-STARTPTS,"
                "aresample=48000,aformat=sample_rates=48000:channel_layouts=stereo,"
                f"volume={gain}dB"
            )
            if fade_in_ms > 0:
                chain += f",afade=t=in:st=0:d={fade_in_ms / 1000:.3f}"
            if fade_out_ms > 0:
                fade_start = max(0.0, duration_seconds - fade_out_ms / 1000)
                chain += f",afade=t=out:st={fade_start:.3f}:d={fade_out_ms / 1000:.3f}"
            chain += (
                f",adelay=delays={item.cue.timeline_at_ms}:all=1"
                f"[a_sfx_{cue_index}]"
            )
            graph.append(chain)
            mix_labels.append(f"[a_sfx_{cue_index}]")
            next_input += 1

    if len(mix_labels) == 1:
        master_input = mix_labels[0]
    else:
        graph.append(
            "".join(mix_labels)
            + f"amix=inputs={len(mix_labels)}:duration=longest:"
            "dropout_transition=0:normalize=0[a_edl_mix]"
        )
        master_input = "[a_edl_mix]"

    has_resolved_assets = bool(audio_plan and (audio_plan.music or audio_plan.sfx))
    if audio_plan is not None:
        target_lufs = _ffmpeg_number(
            audio_plan.master_target_lufs,
            label="master target LUFS",
        )
        true_peak = _ffmpeg_number(
            audio_plan.master_true_peak_db,
            label="master true peak",
        )
        loudnorm = f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11"
    else:
        loudnorm = LOUDNORM_FILTER
    audio_finish = (
        f"{loudnorm},aresample={OUTPUT_AUDIO_SAMPLE_RATE},"
        "aformat=sample_rates=48000:channel_layouts=stereo"
        if source_has_audio or has_resolved_assets
        else (
            f"aresample={OUTPUT_AUDIO_SAMPLE_RATE},"
            "aformat=sample_rates=48000:channel_layouts=stereo"
        )
    )
    graph.append(
        f"{master_input}{audio_finish},apad=pad_dur={intended},"
        f"atrim=duration={intended},asetpts=PTS-STARTPTS[a_edl_out]"
    )
    return asset_input_args, graph


async def render_compiled_edl(
    *,
    source: str,
    edl: CompiledEDL,
    transcript: Transcript,
    out_path: str,
    subtitles_path: str | None = None,
    audio_plan: AudioRenderPlan | None = None,
    ffmpeg_bin: str | None = None,
    ffprobe_bin: str | None = None,
) -> float:
    """Execute a validated V2 EDL as one island-aware FFmpeg render.

    The EDL and renderer compiler are the trust boundary: source ranges,
    filters, labels and timings have already been reduced to closed
    vocabularies.  External music/SFX IDs are deliberately rejected here until
    a trusted asset resolver supplies concrete inputs; they are never ignored
    and an LLM-provided path can never reach this command.
    """
    from .edl_render import EDLRenderError, compile_ffmpeg_render_plan

    if ffmpeg_bin is None or ffprobe_bin is None:
        settings = get_settings()
        ffmpeg_bin = ffmpeg_bin or settings.ffmpeg_bin
        ffprobe_bin = ffprobe_bin or settings.ffprobe_bin
    source_probe = await probe_media(source, ffprobe_bin=ffprobe_bin)
    if not source_probe.has_video:
        raise FFmpegError("EDL source has no video stream")
    if subtitles_path is not None and not Path(subtitles_path).is_file():
        raise FFmpegError(f"EDL subtitles file does not exist: {subtitles_path}")

    try:
        plan = compile_ffmpeg_render_plan(
            edl,
            transcript,
            source_has_audio=source_probe.has_audio,
        )
    except EDLRenderError as exc:
        raise FFmpegError(f"EDL render plan is invalid: {exc}") from exc
    if (plan.deferred_music_asset_ids or plan.deferred_sfx_asset_ids) and audio_plan is None:
        raise FFmpegError(
            "EDL contains unresolved audio catalogue assets; resolve them before rendering"
        )

    graph_parts = [plan.filter_complex]
    video_map = f"[{plan.video_label}]"
    if subtitles_path is not None:
        escaped = _escape_subtitles_filter_path(subtitles_path)
        graph_parts.append(f"[{plan.video_label}]subtitles='{escaped}'[v_edl_out]")
        video_map = "[v_edl_out]"

    asset_input_args, audio_graph = _resolved_audio_mix_graph(
        edl=edl,
        audio_plan=audio_plan,
        first_input_index=len(plan.inputs),
        dialogue_label=plan.audio_label,
        source_has_audio=source_probe.has_audio,
    )
    graph_parts.extend(audio_graph)
    intended_seconds = edl.duration_frames / edl.fps

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *plan.input_args(source),
        *asset_input_args,
        "-filter_complex",
        ";".join(graph_parts),
        "-map",
        video_map,
        "-map",
        "[a_edl_out]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "main",
        "-level",
        "4.1",
        "-r",
        str(edl.fps),
        "-frames:v",
        str(edl.duration_frames),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        str(OUTPUT_AUDIO_SAMPLE_RATE),
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(output),
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not output.exists():
        raise FFmpegError(f"EDL render failed: {err.strip()[-1200:]}")

    output_probe = await probe_media(str(output), ffprobe_bin=ffprobe_bin)
    _validate_mux_timeline(
        output_probe,
        intended_seconds,
        expected_fps=float(edl.fps),
    )
    return output_probe.duration_seconds


async def render_montage_clip(
    *,
    source: str,
    segments: list[tuple[float, float]],     # list of (start, end) in source seconds
    out_path: str,
    workdir: str,
    subtitles_path: str | None = None,
    audio_crossfade_seconds: float = 0.15,
    framings: Framing | list[Framing | None] | None = None,
    transitions: list[str] | None = None,
    framing: Framing | None = None,          # legacy single-framing alias
) -> float:
    """Render a multi-segment vertical clip from a horizontal source.

    Framing is PER-SEGMENT: pass `framings` as a list with one entry per segment
    (`('face_crop', cx)` / `('fit_blur', _)` / `None` for fit+blur). A single
    framing tuple — or the legacy `framing=` alias — is replicated across every
    segment. `transitions` has one entry per joint (`len(segments) - 1`), each
    'cut' (hard cut, current behaviour) or 'white_dip' (intentional dip-to-white
    baked into the two intermediates around the joint). `None` means all cuts.

    Strategy: compile every transcript-derived window, framing decision,
    transition and caption layer into one ClipFactory filter_complex. FFmpeg
    decodes each selected source window directly and encodes only the final MP4.

    Returns the shared audio/video timeline duration in seconds.
    """
    settings = get_settings()
    if not segments:
        raise FFmpegError("no segments to render")
    n = len(segments)
    seg_framings = _normalize_framings(framings if framings is not None else framing, n)
    seg_transitions = _normalize_transitions(transitions, n)

    if n == 1:
        # Single segment — use the simpler renderer (no joints, no fades).
        s, e = segments[0]
        await render_vertical_clip(
            source=source,
            start=s,
            end=e,
            out_path=out_path,
            subtitles_path=subtitles_path,
            framing=seg_framings[0],
        )
        output_probe = await probe_media(out_path)
        _validate_mux_timeline(output_probe, max(0.1, e - s))
        return max(0.1, output_probe.duration_seconds)

    source_probe = await probe_media(source)
    if not source_probe.has_video:
        raise FFmpegError("source has no video stream")

    # ``workdir`` remains in the public signature for compatibility with the
    # runner, but the single-pass engine intentionally creates no intermediates.
    del workdir
    inputs_args, filter_complex, rendered = _build_single_pass_montage(
        source=source,
        segments=segments,
        framings=seg_framings,
        transitions=seg_transitions,
        audio_crossfade_seconds=audio_crossfade_seconds,
        subtitles_path=subtitles_path,
        source_has_audio=source_probe.has_audio,
    )
    v_map = "[vout]" if subtitles_path else "[vraw]"

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        *inputs_args,
        "-filter_complex",
        filter_complex,
        "-map",
        v_map,
        "-map",
        "[anorm]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-profile:v",
        "main",
        "-level",
        "4.1",
        "-r",
        f"{OUTPUT_VIDEO_FPS:g}",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        out_path,
    ]
    code, _, err = await _run(cmd)
    if code != 0 or not os.path.exists(out_path):
        raise FFmpegError(f"montage render failed: {err.strip()[-400:]}")

    output_probe = await probe_media(out_path)
    _validate_mux_timeline(output_probe, rendered)
    return max(0.1, output_probe.duration_seconds)
