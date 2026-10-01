"""Clip judge: strict JSON verdicts, mocked providers only (no paid call)."""

import json

import httpx
import pytest
import structlog

from app.pipeline import runner
from app.pipeline.clip_judge import ClipJudgeError, judge_clip, parse_verdict
from app.providers import openrouter
from app.providers.base import LLMCallResult
from app.providers.openrouter import OpenRouterProvider

GOOD = {
    "publishable": True,
    "hook_0_3s": True,
    "cut_mid_sentence": False,
    "framing_ok": True,
    "caption_overlap": False,
    "reason": "Clear hook and a complete thought.",
}


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def video_json(self, **kwargs):
        self.calls.append(kwargs)
        return LLMCallResult(payload=self.payload, tokens_in=900, tokens_out=40, model="m")


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
    return str(path)


async def test_valid_verdict_is_returned_with_usage(clip):
    provider = FakeProvider(GOOD)
    verdict = await judge_clip(clip, provider=provider, model="judge-model")
    assert verdict.publishable is True and verdict.cut_mid_sentence is False
    assert (verdict.tokens_in, verdict.tokens_out) == (900, 40)
    assert provider.calls[0]["model"] == "judge-model"
    assert provider.calls[0]["video_mp4"].startswith(b"\x00\x00\x00\x18ftyp")


@pytest.mark.parametrize(
    "payload",
    [
        [GOOD],
        {k: v for k, v in GOOD.items() if k != "framing_ok"},
        {**GOOD, "score": 7},
        {**GOOD, "publishable": "true"},
        {**GOOD, "hook_0_3s": 1},
        {**GOOD, "reason": "   "},
    ],
)
async def test_non_strict_answers_are_rejected(clip, payload):
    with pytest.raises(ClipJudgeError):
        await judge_clip(clip, provider=FakeProvider(payload), model="m")


async def test_oversized_or_empty_clip_is_not_sent(tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    provider = FakeProvider(GOOD)
    with pytest.raises(ClipJudgeError):
        await judge_clip(str(empty), provider=provider, model="m")
    big = tmp_path / "big.mp4"
    big.write_bytes(b"x" * 2048)
    with pytest.raises(ClipJudgeError):
        await judge_clip(str(big), provider=provider, model="m", max_video_mb=0.001)
    assert provider.calls == []


def test_parse_trims_reason():
    assert parse_verdict({**GOOD, "reason": "  ok  "})["reason"] == "ok"


async def test_runner_judge_is_off_by_default(monkeypatch, clip):
    def boom(*_a, **_k):
        raise AssertionError("judge must not be called when disabled")

    monkeypatch.setattr(runner, "judge_clip", boom)
    monkeypatch.setattr(runner, "OpenRouterProvider", boom)
    assert runner.get_settings().clip_judge_enabled is False
    assert await runner._advisory_clip_verdict(clip, log_ctx=structlog.get_logger()) is None


async def test_openrouter_sends_native_video(monkeypatch):
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(GOOD)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            },
        )

    provider = OpenRouterProvider()
    monkeypatch.setattr(
        provider,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.com"
        ),
    )
    monkeypatch.setattr(openrouter.asyncio, "sleep", lambda *_: None)
    result = await provider.video_json(
        model="google/gemini-3.8-flash", system="s", user_text="u", video_mp4=b"mp4"
    )
    assert result.payload == GOOD
    part = requests[0]["messages"][1]["content"][0]
    assert part["type"] == "video_url"
    assert part["video_url"]["url"].startswith("data:video/mp4;base64,")
    assert requests[0]["max_tokens"] >= 6000
