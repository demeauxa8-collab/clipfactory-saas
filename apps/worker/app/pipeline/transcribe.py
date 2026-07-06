from __future__ import annotations

import asyncio
import os
import tempfile

import structlog
from openai import AsyncOpenAI

from ..models import Transcript, TranscriptWord
from ..settings import get_settings

log = structlog.get_logger()


async def _extract_audio(src_path: str, ffmpeg_bin: str) -> str:
    """Downmix to a compact 16 kHz mono MP3.

    OpenAI's transcription endpoint caps uploads at 25 MB. Sending the raw video
    blows past that on ~10 min clips, so we strip the video track and compress
    the audio (a 30 min plan-cap clip lands around ~14 MB at 64 kbps).
    """
    fd, out_path = tempfile.mkstemp(suffix=".mp3", prefix="cf_audio_")
    os.close(fd)
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_bin, "-y", "-i", src_path,
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
        out_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extract failed: {stderr.decode()[-400:]}")
    return out_path


async def transcribe(audio_or_video_path: str) -> Transcript:
    settings = get_settings()
    # Generous timeout + retries: whisper-1 on a ~30 min clip can be slow, and a
    # single transient timeout should not fail the whole job.
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=180.0, max_retries=3)

    audio_path = await _extract_audio(audio_or_video_path, settings.ffmpeg_bin)
    try:
        with open(audio_path, "rb") as fh:
            resp = await client.audio.transcriptions.create(
                file=fh,
                model=settings.openai_transcribe_model,
                response_format="verbose_json",
                timestamp_granularities=["word"],
            )
    finally:
        try:
            os.remove(audio_path)
        except OSError:
            pass

    text = getattr(resp, "text", "") or ""
    words: list[TranscriptWord] = []
    raw_words = getattr(resp, "words", None) or []
    for w in raw_words:
        try:
            words.append(
                TranscriptWord(
                    word=str(w.get("word") if isinstance(w, dict) else w.word),
                    start=float(w.get("start") if isinstance(w, dict) else w.start),
                    end=float(w.get("end") if isinstance(w, dict) else w.end),
                )
            )
        except Exception:
            continue

    lang = getattr(resp, "language", None)
    log.info("transcribe.done", words=len(words), language=lang)
    return Transcript(text=text, words=words, language=lang)


def transcript_to_timestamped_lines(t: Transcript, line_seconds: float = 12.0) -> str:
    """Compact representation used in the candidate prompt.

    We chunk the transcript words into ~12 second lines so the LLM gets explicit
    timestamps without exploding the token budget.
    """
    if not t.words:
        return f"[0.0] {t.text.strip()}"

    lines: list[str] = []
    bucket: list[str] = []
    bucket_start = t.words[0].start
    for w in t.words:
        if w.start - bucket_start >= line_seconds:
            lines.append(f"[{bucket_start:.1f}] {' '.join(bucket).strip()}")
            bucket = []
            bucket_start = w.start
        bucket.append(w.word)
    if bucket:
        lines.append(f"[{bucket_start:.1f}] {' '.join(bucket).strip()}")
    return "\n".join(lines)


def words_in_window(t: Transcript, start: float, end: float) -> list[TranscriptWord]:
    return [w for w in t.words if w.end >= start and w.start <= end]
