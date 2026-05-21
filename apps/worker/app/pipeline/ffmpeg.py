from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from ..settings import get_settings


class FFmpegError(RuntimeError):
    pass


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


async def render_vertical_clip(
    *,
    source: str,
    start: float,
    end: float,
    out_path: str,
    subtitles_path: str | None = None,
) -> None:
    """Render a 1080x1920 vertical clip from a horizontal source.

    Strategy V1: scale to fit height, center-crop horizontally. No face tracking.
    """
    settings = get_settings()
    duration = max(0.1, end - start)
    vf_chain = [
        # Scale so the source fills the vertical frame, keeping aspect.
        "scale=-2:1920",
        "crop=1080:1920",
        "setsar=1",
    ]
    if subtitles_path:
        # Escape the subtitle path for FFmpeg filter syntax.
        sub_esc = subtitles_path.replace(":", "\\:").replace("'", "\\'")
        vf_chain.append(f"subtitles='{sub_esc}'")

    cmd = [
        settings.ffmpeg_bin,
        "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",
        "-i", source,
        "-t", f"{duration:.3f}",
        "-vf", ",".join(vf_chain),
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


async def yt_dlp_download(url: str, out_dir: str) -> str:
    """Download a video. Returns absolute path to the merged mp4."""
    settings = get_settings()
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_template = os.path.join(out_dir, "source.%(ext)s")

    cmd = [
        settings.yt_dlp_bin,
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--quiet", "--no-warnings",
        "-o", out_template,
        url,
    ]
    code, _, err = await _run(cmd)
    if code != 0:
        raise FFmpegError(f"yt-dlp failed: {err.strip()[-2000:]}")

    # yt-dlp may name the file source.mp4 or source.mkv (we forced mp4).
    candidates = list(Path(out_dir).glob("source.*"))
    if not candidates:
        raise FFmpegError("yt-dlp produced no output file")
    return str(candidates[0].resolve())
