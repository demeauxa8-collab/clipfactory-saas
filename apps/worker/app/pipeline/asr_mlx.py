"""Optional Apple Silicon Whisper backend. Import mlx-whisper only when selected."""

from __future__ import annotations

import asyncio
import threading

from ..models import Transcript
from .transcribe import build_transcript

_decode_lock = threading.Lock()


def _decode(audio_path: str, model: str) -> dict:
    import mlx_whisper  # optional dependency, unavailable in Linux CI

    with _decode_lock:
        return mlx_whisper.transcribe(
            audio_path, path_or_hf_repo=model, word_timestamps=True,
            condition_on_previous_text=False,
        )


async def transcribe_mlx(audio_path: str, model: str) -> Transcript:
    result = await asyncio.to_thread(_decode, audio_path, model)
    segments = result.get("segments") or []
    words = [word for segment in segments for word in segment.get("words", [])]
    return build_transcript(
        text=result.get("text") or "", raw_words=words, raw_segments=segments,
        language=result.get("language"), backend="mlx_whisper",
    )
