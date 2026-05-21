from __future__ import annotations

import structlog
from openai import AsyncOpenAI

from ..models import Transcript, TranscriptWord
from ..settings import get_settings

log = structlog.get_logger()


async def transcribe(audio_or_video_path: str) -> Transcript:
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    def _open():
        return open(audio_or_video_path, "rb")

    # The transcribe endpoint accepts the video file directly; OpenAI extracts
    # audio server-side. For long videos we might need to chunk — V1 keeps it
    # simple and relies on the 30 min plan cap.
    with _open() as fh:
        resp = await client.audio.transcriptions.create(
            file=fh,
            model=settings.openai_transcribe_model,
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )

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
