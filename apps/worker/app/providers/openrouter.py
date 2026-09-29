from __future__ import annotations

import asyncio
import base64
import math
from typing import Any

import httpx
import structlog

from ..models_lock import model_profile
from ..settings import get_settings
from ._jsonparse import extract_json
from .base import ImageInput, LLMCallResult, LLMProvider, ProviderError

log = structlog.get_logger()

# Ceiling for the automatic budget increase after a truncated answer.
MAX_OUTPUT_TOKENS = 32_000


def _apply_model_profile(body: dict[str, Any], model: str) -> dict[str, Any]:
    """Output floor and reasoning budget from models.lock.toml, per model.

    A reasoning model needs headroom: its thinking tokens count against
    max_tokens, and a too-small budget truncates the JSON. Reasoning is sent
    disabled (or capped) when the lock says so; a model that refuses gets the
    field removed by the retry loop while keeping this floor.
    """
    profile = model_profile(model)
    body["max_tokens"] = max(int(body["max_tokens"]), profile.min_output_tokens)
    if profile.reasoning_max_tokens is None:
        body.pop("reasoning", None)
    else:
        body["reasoning"] = {"max_tokens": profile.reasoning_max_tokens}
    return body


class OpenRouterProvider(LLMProvider):
    """OpenAI-compatible HTTP client for OpenRouter.

    Serves the text, vision-deep, vision-cheap and clip-judge stages; which
    model each stage uses comes from models.lock.toml via settings.
    """

    name = "openrouter"

    def __init__(self, timeout_seconds: float = 90.0) -> None:
        self._timeout = timeout_seconds

    # ----- internal -----

    def _client(self) -> httpx.AsyncClient:
        s = get_settings()
        if not s.openrouter_api_key:
            raise ProviderError("OPENROUTER_API_KEY not set", kind="http")
        return httpx.AsyncClient(
            base_url=s.openrouter_base_url,
            timeout=self._timeout,
            headers={
                "Authorization": f"Bearer {s.openrouter_api_key}",
                "HTTP-Referer": s.openrouter_http_referer,
                "X-Title": s.openrouter_app_name,
                "Content-Type": "application/json",
            },
        )

    async def _post_chat(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._client() as client:
                resp = await client.post("/chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise ProviderError(f"timeout: {exc}", kind="timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"http error: {exc}", kind="http") from exc

        if resp.status_code >= 400:
            try:
                retry_after = float(resp.headers.get("retry-after", "0"))
                retry_after = min(10, max(0, retry_after)) if math.isfinite(retry_after) else None
            except ValueError:
                retry_after = None
            raise ProviderError(
                f"openrouter {resp.status_code}: {resp.text[:300]}",
                kind="http",
                status_code=resp.status_code,
                retry_after=retry_after,
            )

        try:
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            if isinstance(data.get("error"), dict):
                error = data["error"]
                raise ProviderError(
                    str(error.get("message", "upstream error"))[:300],
                    kind="http",
                    status_code=error.get("code"),
                )
            return data
        except ValueError as exc:
            raise ProviderError(f"non-json response: {exc}", kind="parse") from exc

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("no choices in response", kind="empty")
        if choices[0].get("finish_reason") == "length":
            # Output budget exhausted (often by reasoning tokens): the JSON is
            # cut. Retry with a larger budget instead of parsing a fragment.
            raise ProviderError("response truncated (finish_reason=length)", kind="truncated")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            # OpenRouter sometimes returns a content array (vision style).
            parts = [c.get("text", "") for c in content if isinstance(c, dict)]
            return "".join(parts)
        return str(content or "")

    @staticmethod
    def _extract_usage(data: dict[str, Any]) -> tuple[int, int]:
        usage = data.get("usage") or {}
        return int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0)

    async def _post_and_extract(
        self, body: dict[str, Any], model: str, label: str, attempts: int = 3
    ) -> LLMCallResult:
        """POST then JSON-parse, retrying when the model returns non-JSON.

        Some OpenRouter models intermittently ignore ``response_format`` and
        answer with prose/empty content; a fresh sample almost always parses.
        """
        if attempts < 1:
            raise ValueError("attempts must be positive")
        body = dict(body)
        last_exc: Exception | None = None
        total_in = total_out = 0
        for attempt in range(attempts):
            try:
                data = await self._post_chat(body)
                tin, tout = self._extract_usage(data)
                total_in += tin
                total_out += tout
                text = self._extract_text(data)
                payload = extract_json(text)
                return LLMCallResult(
                    payload=payload, tokens_in=total_in, tokens_out=total_out, model=model
                )
            except (ProviderError, ValueError) as exc:
                last_exc = exc
                # Port the useful reasoning-refusal recovery from the backend
                # branch, while retaining the caller's explicit output budget.
                reasoning_refused = (
                    isinstance(exc, ProviderError)
                    and exc.status_code in {400, 422}
                    and "reasoning" in body
                    and any(
                        needle in str(exc).lower()
                        for needle in (
                            "reasoning is mandatory",
                            "cannot be disabled",
                            "thinking_budget",
                            "thinking budget",
                        )
                    )
                )
                if reasoning_refused:
                    body.pop("reasoning")
                    log.info("openrouter.reasoning_required", model=model)
                elif isinstance(exc, ProviderError) and exc.kind == "truncated":
                    body["max_tokens"] = min(
                        MAX_OUTPUT_TOKENS, max(int(body.get("max_tokens") or 0) * 2, 1024)
                    )
                    log.info(
                        "openrouter.truncated_retry", model=model, max_tokens=body["max_tokens"]
                    )
                elif isinstance(exc, ProviderError) and exc.status_code is not None:
                    if exc.status_code not in {408, 409, 429} and not (
                        isinstance(exc.status_code, int) and 500 <= exc.status_code <= 599
                    ):
                        break
                if attempt + 1 < attempts:
                    delay = min(2, 0.25 * 2**attempt)
                    if isinstance(exc, ProviderError) and exc.retry_after is not None:
                        delay = max(delay, min(10, max(0, exc.retry_after)))
                    await asyncio.sleep(delay)
        if isinstance(last_exc, ProviderError):
            last_exc.tokens_in, last_exc.tokens_out = total_in, total_out
            raise last_exc
        error = ProviderError(f"{label} failed after {attempts} tries: {last_exc}", kind="parse")
        error.tokens_in, error.tokens_out = total_in, total_out
        raise error

    # ----- public API -----

    async def chat_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Disable model "thinking": reasoning tokens otherwise eat the
            # max_tokens budget and truncate the JSON (e.g. Gemini 2.5 Flash).
            "reasoning": {"max_tokens": 0},
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        return await self._post_and_extract(_apply_model_profile(body, model), model, "parse")

    async def vision_json(
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        images: list[ImageInput],
        max_tokens: int = 2048,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        # Build OpenAI-style content array with image_url entries.
        content: list[dict[str, Any]] = []
        for img in images:
            if img.url:
                content.append({"type": "image_url", "image_url": {"url": img.url}})
            elif img.bytes_jpeg:
                b64 = base64.b64encode(img.bytes_jpeg).decode("ascii")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    }
                )
        content.append({"type": "text", "text": user_text})

        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            # Disable "thinking" here too: on vision calls Gemini's reasoning
            # tokens otherwise consume the whole max_tokens budget and truncate
            # the JSON to a few characters.
            "reasoning": {"max_tokens": 0},
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        return await self._post_and_extract(
            _apply_model_profile(body, model), model, "vision parse"
        )

    async def video_json(
        self,
        *,
        model: str,
        system: str,
        user_text: str,
        video_mp4: bytes,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMCallResult:
        """Native video input (e.g. Gemini) as an inline mp4 data URL."""
        b64 = base64.b64encode(video_mp4).decode("ascii")
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "reasoning": {"max_tokens": 0},
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "video_url",
                            "video_url": {"url": f"data:video/mp4;base64,{b64}"},
                        },
                        {"type": "text", "text": user_text},
                    ],
                },
            ],
        }
        return await self._post_and_extract(
            _apply_model_profile(body, model), model, "video parse"
        )
