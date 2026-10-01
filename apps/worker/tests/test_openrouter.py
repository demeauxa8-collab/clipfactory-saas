import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.providers import openrouter
from app.providers.base import ProviderError
from app.providers.openrouter import OpenRouterProvider


def response(text='{"ok":true}', tokens=10):
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": tokens, "completion_tokens": tokens},
    }


def client(monkeypatch, replies):
    requests = []

    async def handler(request):
        requests.append(json.loads(request.content))
        return replies[len(requests) - 1]

    provider = OpenRouterProvider()
    monkeypatch.setattr(
        provider,
        "_client",
        lambda: httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://example.com"
        ),
    )
    sleeper = AsyncMock()
    monkeypatch.setattr(openrouter.asyncio, "sleep", sleeper)
    return provider, requests, sleeper


async def call(provider):
    return await provider.chat_json(
        model="test", system="Return JSON.", user="Test", max_tokens=2048
    )


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422])
async def test_permanent_http_failures_do_not_spend_five_retries(monkeypatch, status):
    provider, requests, sleeper = client(
        monkeypatch, [httpx.Response(status, text="request rejected")]
    )
    with pytest.raises(ProviderError) as error:
        await call(provider)
    assert error.value.status_code == status
    assert len(requests) == 1
    sleeper.assert_not_awaited()


async def test_reasoning_recovery_keeps_original_budget(monkeypatch):
    provider, requests, _ = client(
        monkeypatch,
        [
            httpx.Response(400, text="reasoning is mandatory and cannot be disabled"),
            httpx.Response(200, json=response()),
        ],
    )
    assert (await call(provider)).payload == {"ok": True}
    assert requests[0]["reasoning"] == {"max_tokens": 0}
    assert "reasoning" not in requests[1]
    assert [request["max_tokens"] for request in requests] == [2048, 2048]


async def test_usage_includes_discarded_non_json_response(monkeypatch):
    provider, requests, _ = client(
        monkeypatch,
        [
            httpx.Response(200, json=response("invalid output", 20)),
            httpx.Response(200, json=response(tokens=10)),
        ],
    )
    result = await call(provider)
    assert result.tokens_total == 60
    assert len(requests) == 2


@pytest.mark.parametrize("actual", ["resolved-version", None])
async def test_model_metadata_uses_response_when_available(monkeypatch, actual):
    data = response()
    if actual:
        data["model"] = actual
    provider, _, _ = client(monkeypatch, [httpx.Response(200, json=data)])
    result = await call(provider)
    assert result.model == (actual or "test")
    assert result.model_source == ("response" if actual else "request")


async def test_rate_limit_retries_with_bounded_retry_after(monkeypatch):
    provider, requests, sleeper = client(
        monkeypatch,
        [
            httpx.Response(429, text="rate limit", headers={"retry-after": "3600"}),
            httpx.Response(200, json=response()),
        ],
    )
    await call(provider)
    sleeper.assert_awaited_once_with(10)
    assert len(requests) == 2


async def test_retries_and_failed_usage_are_bounded(monkeypatch):
    provider, requests, sleeper = client(
        monkeypatch, [httpx.Response(200, json=response("not json")) for _ in range(3)]
    )
    with pytest.raises(ProviderError) as error:
        await call(provider)
    assert len(requests) == 3
    assert sleeper.await_count == 2
    assert error.value.tokens_in + error.value.tokens_out == 60


async def call_model(provider, model, max_tokens=512):
    return await provider.chat_json(
        model=model, system="Return JSON.", user="Test", max_tokens=max_tokens
    )


async def test_locked_reasoning_model_gets_output_floor(monkeypatch):
    provider, requests, _ = client(monkeypatch, [httpx.Response(200, json=response())])
    await call_model(provider, "google/gemini-3.8-flash", max_tokens=512)
    assert requests[0]["max_tokens"] >= 6000
    assert requests[0]["reasoning"] == {"max_tokens": 0}


async def test_reasoning_refusal_keeps_the_output_floor(monkeypatch):
    provider, requests, _ = client(
        monkeypatch,
        [
            httpx.Response(400, text="Reasoning is mandatory for this endpoint"),
            httpx.Response(200, json=response()),
        ],
    )
    await call_model(provider, "google/gemini-3.8-flash", max_tokens=512)
    assert "reasoning" not in requests[1]
    assert requests[1]["max_tokens"] >= 6000


async def test_truncated_json_is_detected_and_retried_with_a_larger_budget(monkeypatch):
    truncated = {
        "choices": [{"message": {"content": '{"arcs": [{"sta'}, "finish_reason": "length"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2048},
    }
    provider, requests, _ = client(
        monkeypatch,
        [httpx.Response(200, json=truncated), httpx.Response(200, json=response())],
    )
    result = await call(provider)
    assert result.payload == {"ok": True}
    assert [r["max_tokens"] for r in requests] == [2048, 4096]


async def test_truncation_never_parses_a_complete_looking_fragment(monkeypatch):
    # A cut answer can still be valid JSON (e.g. an early-closed object): the
    # finish_reason, not the parser, decides.
    cut = {
        "choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "length"}],
        "usage": {},
    }
    provider, requests, _ = client(monkeypatch, [httpx.Response(200, json=cut)] * 3)
    with pytest.raises(ProviderError) as error:
        await call(provider)
    assert error.value.kind == "truncated"
    assert len(requests) == 3
