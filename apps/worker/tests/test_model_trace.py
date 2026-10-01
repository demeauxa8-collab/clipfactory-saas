import json
import shutil
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import structlog

from app.models import JobContext, Transcript
from app.pipeline import job_artifacts, runner, transcribe
from app.pipeline.model_trace import TracedProvider, initialize_trace
from app.providers.anthropic import AnthropicProvider
from app.providers.base import LLMCallResult, ProviderError
from app.settings import Settings


def settings(**overrides):
    return Settings(
        _env_file=None, database_url="postgresql://unused", openai_api_key="mock",
        storage_backend="local", storage_local_dir="/tmp/unused", **overrides,
    )


def context(tmp_path, **overrides):
    return JobContext(
        job_id="job", user_id="user", campaign={}, source_url="unused",
        target_clip_count=1, workdir=str(tmp_path / "work"), run_token="attempt",
        model_trace=initialize_trace(settings(**overrides)),
    )


def provider(name, result):
    return SimpleNamespace(name=name, chat_json=AsyncMock(side_effect=result))


async def test_runner_fallback_records_response_model_and_failed_primary(tmp_path):
    ctx = context(tmp_path)
    response = LLMCallResult({}, model="actual-version", model_source="response")
    primary = provider("openrouter", ProviderError("private provider body", kind="http"))
    fallback = provider("anthropic", [response])
    used, result = await runner._call_with_fallback(
        primary, fallback, "primary-alias", "fallback-alias",
        lambda p, m: p.chat_json(model=m), label="story_arcs", ctx=ctx,
    )
    assert used is fallback and result is response
    trace = ctx.model_trace
    assert trace["fallback_used"] is True
    calls = trace["stages"]["text"]["calls"]
    assert calls[0]["status"] == "failed" and calls[0]["model"] is None
    assert calls[1]["model"] == "actual-version"
    assert calls[1]["requested_model"] == "fallback-alias"
    assert calls[1]["model_source"] == "response"
    assert "private provider body" not in json.dumps(trace)
    assert trace["stages"]["vision_cheap"]["status"] == "not_called"
    assert trace["stages"]["judge"]["status"] == "disabled"
    assert context(tmp_path).model_trace["stages"]["text"]["calls"] == []


async def test_failed_fallback_is_attempted_but_not_reported_as_used(tmp_path):
    ctx = context(tmp_path)
    with pytest.raises(ProviderError):
        await runner._call_with_fallback(
            provider("openrouter", ProviderError("failed")),
            provider("anthropic", ProviderError("failed")), "a", "b",
            lambda p, m: p.chat_json(model=m), label="deep_vision", ctx=ctx,
            stage="vision_deep",
        )
    assert not ctx.model_trace["fallback_used"]
    calls = ctx.model_trace["stages"]["vision_deep"]["calls"]
    assert [c["fallback"] for c in calls] == [False, True]
    assert all(c["model"] is None for c in calls)


@pytest.mark.parametrize("stage,operation", [("vision_cheap", "vision_json"),
                                           ("vision_deep", "vision_json"),
                                           ("judge", "video_json")])
async def test_vision_and_video_preserve_payload_and_capture_model(tmp_path, stage, operation):
    ctx = context(tmp_path, clip_judge_enabled=True)
    response = LLMCallResult({"verdict": True}, model="effective")
    wrapped = SimpleNamespace(name="openrouter", **{operation: AsyncMock(return_value=response)})
    traced = TracedProvider(wrapped, ctx, stage, "step")
    assert await getattr(traced, operation)(model="alias", images=[]) is response
    call = ctx.model_trace["stages"][stage]["calls"][0]
    assert call["model"] == "effective" and call["operation"] == operation


async def test_disabled_judge_never_constructs_provider(tmp_path, monkeypatch):
    ctx = context(tmp_path)
    monkeypatch.setattr(runner, "get_settings", settings)
    constructor = AsyncMock(side_effect=AssertionError("unexpected provider"))
    monkeypatch.setattr(runner, "OpenRouterProvider", constructor)
    assert await runner._advisory_clip_verdict(
        "unused", log_ctx=structlog.get_logger(), ctx=ctx,
    ) is None
    constructor.assert_not_called()
    assert ctx.model_trace["stages"]["judge"]["status"] == "disabled"


@pytest.mark.parametrize("operation", ["chat_json", "vision_json"])
async def test_anthropic_metadata_reads_resolved_model(monkeypatch, operation):
    response = SimpleNamespace(
        model="resolved-version", content=[SimpleNamespace(type="text", text='{"ok":true}')],
        usage=SimpleNamespace(input_tokens=10, output_tokens=2),
    )
    wrapped = AnthropicProvider()
    monkeypatch.setattr(wrapped, "_client", lambda: SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(return_value=response)),
    ))
    payload = {"user": "test"} if operation == "chat_json" else {
        "user_text": "test", "images": [],
    }
    result = await getattr(wrapped, operation)(model="alias", system="test", **payload)
    assert result.model == "resolved-version" and result.model_source == "response"


async def test_local_checkpoint_survives_workdir_cleanup(tmp_path, monkeypatch):
    from app import storage

    ctx = context(tmp_path)
    local = tmp_path / "storage"
    monkeypatch.setattr(storage, "get_settings", lambda: SimpleNamespace(
        storage_backend="local", storage_local_dir=str(local),
    ))
    key = await job_artifacts.checkpoint_job(ctx, "model_trace", {})
    shutil.rmtree(ctx.workdir)
    document = json.loads((local / key).read_text())
    assert document["model_trace"] == ctx.model_trace
    assert document["attempt_id"] == "attempt"
    assert ctx.storage_bytes == (local / key).stat().st_size


async def test_asr_records_local_failure_and_actual_openai_fallback(tmp_path, monkeypatch):
    from app.pipeline import asr_mlx

    ctx = context(tmp_path, asr_backend="mlx_whisper")
    monkeypatch.setattr(transcribe, "get_settings", lambda: settings(asr_backend="mlx_whisper"))
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"mock")
    monkeypatch.setattr(transcribe, "_extract_audio", AsyncMock(return_value=str(audio)))
    monkeypatch.setattr(asr_mlx, "transcribe_mlx", AsyncMock(side_effect=RuntimeError("private")))
    transcript = Transcript(text="test", words=[], language="fr", asr_backend="openai")
    monkeypatch.setattr(transcribe, "_transcribe_openai", AsyncMock(return_value=transcript))
    assert await transcribe.transcribe("unused", trace_ctx=ctx) is transcript
    calls = ctx.model_trace["stages"]["transcription"]["calls"]
    assert [c["status"] for c in calls] == ["failed", "succeeded"]
    assert calls[1]["model"] == settings().openai_transcribe_model
    assert calls[1]["model_source"] == "request"
    assert ctx.model_trace["fallback_used"]
    assert not audio.exists()
