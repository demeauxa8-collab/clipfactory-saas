from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pytest

from app.pipeline import asr_mlx, transcribe


@pytest.mark.asyncio
async def test_mlx_mapping_uses_shared_cleanup(monkeypatch):
    monkeypatch.setattr(asr_mlx, "_decode", lambda *_: {
        "text": "J'ai parlé.", "language": "fr",
        "segments": [{"text": "J'ai parlé.", "start": 0.0, "end": 1.0,
                      "words": [{"word": " J", "start": 0.0, "end": 0.1, "probability": 0.9},
                                {"word": " ai", "start": 0.1, "end": 0.1, "probability": 0.8},
                                {"word": " parlé", "start": 0.2, "end": 1.0}]}],
    })
    result = await asr_mlx.transcribe_mlx("unused", "unused")
    assert result.asr_backend == "mlx_whisper"
    assert result.words[0].word == "J\u2019ai"
    assert result.words[0].probability == 0.8
    assert all(w.end > w.start for w in result.words)
    assert result.sentences[0].text == "J'ai parlé."


@pytest.mark.asyncio
async def test_openai_path_never_imports_mlx(monkeypatch, tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"test")
    settings = SimpleNamespace(asr_backend="openai", ffmpeg_bin="ffmpeg")
    monkeypatch.setattr(transcribe, "get_settings", lambda: settings)
    async def extract(*_):
        return str(audio)
    async def openai(*_):
        return "openai-result"
    monkeypatch.setattr(transcribe, "_extract_audio", extract)
    monkeypatch.setattr(transcribe, "_transcribe_openai", openai)
    sys.modules.pop("mlx_whisper", None)
    assert await transcribe.transcribe("unused") == "openai-result"
    assert "mlx_whisper" not in sys.modules


@pytest.mark.asyncio
async def test_mlx_failure_falls_back_to_openai(monkeypatch, tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"test")
    settings = SimpleNamespace(asr_backend="mlx_whisper", ffmpeg_bin="ffmpeg",
                               mlx_whisper_model="model", asr_fallback_to_openai=True)
    monkeypatch.setattr(transcribe, "get_settings", lambda: settings)
    async def extract(*_):
        return str(audio)
    async def fail(*_):
        raise RuntimeError("GPU failure")
    async def openai(*_):
        return "fallback"
    monkeypatch.setattr(transcribe, "_extract_audio", extract)
    monkeypatch.setattr(asr_mlx, "transcribe_mlx", fail)
    monkeypatch.setattr(transcribe, "_transcribe_openai", openai)
    assert await transcribe.transcribe("unused") == "fallback"


@pytest.mark.mlx
@pytest.mark.asyncio
async def test_local_mlx_twenty_second_speech():
    path = os.environ.get("MLX_TEST_AUDIO")
    if not path:
        pytest.skip("set MLX_TEST_AUDIO to a 20-second speech sample")
    result = await asr_mlx.transcribe_mlx(path, "mlx-community/whisper-large-v3-turbo")
    assert result.words
    assert all(word.end >= word.start for word in result.words)
    assert all(a.start <= b.start for a, b in zip(result.words, result.words[1:], strict=False))
