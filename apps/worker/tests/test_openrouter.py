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
