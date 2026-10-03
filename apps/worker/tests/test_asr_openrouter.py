from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.pipeline import transcribe


def _settings(**overrides):
    base = dict(
        asr_backend="openrouter", ffmpeg_bin="ffmpeg",
        openrouter_base_url="https://openrouter.test/api/v1",
        openrouter_api_key="test-key",
        openrouter_transcribe_model="openai/whisper-large-v3",
        openai_transcribe_model="whisper-1",
        asr_fallback_to_openai=True,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _patch_http(monkeypatch, handler):
    real_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(transcribe.httpx, "AsyncClient", client_factory)


@pytest.mark.asyncio
async def test_openrouter_maps_verbose_json_with_shared_cleanup(monkeypatch, tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"mp3")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(200, json={
            "text": "J ai parlé", "language": "fr",
            "segments": [{"text": "J ai parlé", "start": 0.0, "end": 1.0}],
            "words": [{"word": " J", "start": 0.0, "end": 0.1},
                      {"word": " ai", "start": 0.1, "end": 0.1},
                      {"word": " parlé", "start": 0.2, "end": 1.0}],
        })

    _patch_http(monkeypatch, handler)
    result = await transcribe._transcribe_openrouter(str(audio), _settings())

    assert seen["url"] == "https://openrouter.test/api/v1/audio/transcriptions"
    assert seen["auth"] == "Bearer test-key"
    assert b"openai/whisper-large-v3" in seen["body"]
    assert b"verbose_json" in seen["body"]
    assert result.asr_backend == "openrouter"
    assert result.words[0].word == "J\u2019ai"
    assert all(w.end > w.start for w in result.words)
    assert result.sentences[0].text == "J ai parlé"


@pytest.mark.asyncio
async def test_openrouter_reads_words_nested_in_segments(monkeypatch, tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"mp3")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({
            "text": "bonjour",
            "segments": [{"text": "bonjour", "start": 0.0, "end": 0.5,
                          "words": [{"word": "bonjour", "start": 0.0, "end": 0.5}]}],
        }))

    _patch_http(monkeypatch, handler)
    result = await transcribe._transcribe_openrouter(str(audio), _settings())
    assert [w.word for w in result.words] == ["bonjour"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "payload", "message"), [
    (402, {"error": "insufficient credits"}, "openrouter_transcription_http_402"),
    (200, {"text": "sans mots", "segments": []}, "openrouter_transcription_no_word_timestamps"),
])
async def test_openrouter_failures_are_explicit(monkeypatch, tmp_path, status, payload, message):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"mp3")
    _patch_http(monkeypatch, lambda _r: httpx.Response(status, json=payload))
    with pytest.raises(RuntimeError, match=message):
        await transcribe._transcribe_openrouter(str(audio), _settings())


@pytest.mark.asyncio
async def test_transcribe_routes_to_openrouter(monkeypatch, tmp_path):
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"test")
    monkeypatch.setattr(transcribe, "get_settings", lambda: _settings())

    async def extract(*_):
        return str(audio)

    async def openrouter(*_):
        return "openrouter-result"

    async def openai(*_):
        raise AssertionError("OpenAI must not be called when OpenRouter succeeds")

    monkeypatch.setattr(transcribe, "_extract_audio", extract)
    monkeypatch.setattr(transcribe, "_transcribe_openrouter", openrouter)
    monkeypatch.setattr(transcribe, "_transcribe_openai", openai)
    assert await transcribe.transcribe("unused") == "openrouter-result"


@pytest.mark.asyncio
async def test_openrouter_failure_falls_back_or_raises(monkeypatch, tmp_path):
    async def openrouter(*_):
        raise RuntimeError("openrouter down")

    async def openai(*_):
        return "fallback"

    for fallback_enabled, expected in ((True, "fallback"), (False, None)):
        audio = tmp_path / f"audio-{fallback_enabled}.mp3"
        audio.write_bytes(b"test")

        async def extract(*_, _path=str(audio)):
            return _path

        monkeypatch.setattr(transcribe, "get_settings",
                            lambda f=fallback_enabled: _settings(asr_fallback_to_openai=f))
        monkeypatch.setattr(transcribe, "_extract_audio", extract)
        monkeypatch.setattr(transcribe, "_transcribe_openrouter", openrouter)
        monkeypatch.setattr(transcribe, "_transcribe_openai", openai)
        if expected is None:
            with pytest.raises(RuntimeError, match="openrouter down"):
                await transcribe.transcribe("unused")
        else:
            assert await transcribe.transcribe("unused") == expected
