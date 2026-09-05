from __future__ import annotations

import base64
from typing import Any

import httpx
import structlog

from ..settings import get_settings
from ._jsonparse import extract_json
from .base import ImageInput, LLMCallResult, LLMProvider, ProviderError

log = structlog.get_logger()


class OpenRouterProvider(LLMProvider):
    """OpenAI-compatible HTTP client for OpenRouter.

    Used for:
      - Text: DeepSeek V3.2 (story arcs, segment selection)
      - Vision deep: Gemini 2.5 Flash (top arcs verification)
      - Vision cheap: Qwen3-VL Flash (global video map)
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
            raise ProviderError(
                f"openrouter {resp.status_code}: {resp.text[:300]}", kind="http"
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError(f"non-json response: {exc}", kind="parse") from exc

    @staticmethod
    def _extract_text(data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError("no choices in response", kind="empty")
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

    # A provider that refuses a zeroed reasoning budget says so in the 400 body.
    # The wording differs per upstream, so match on the parts that do not move.
    _REASONING_REFUSALS = (
        "reasoning is mandatory",
        "cannot be disabled",
        "thinking_budget",
        "thinking budget",
    )

    @classmethod
    def _refuses_disabled_reasoning(cls, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(needle in message for needle in cls._REASONING_REFUSALS)

    async def _post_and_extract(
        self, body: dict[str, Any], model: str, label: str, attempts: int = 5
    ) -> LLMCallResult:
        """POST then JSON-parse, retrying when the model returns non-JSON.

        Some OpenRouter models intermittently ignore ``response_format`` and
        answer with prose/empty content; a fresh sample almost always parses.

        We ask for reasoning to be switched off because reasoning tokens
        otherwise eat the max_tokens budget and truncate the JSON — that was
        measured on Gemini 2.5 Flash. But a whole generation of newer models
        REFUSES to run without reasoning and answers 400. Rather than keep a
        list of model names (the catalogue moves faster than we do — two
        configured IDs were retired under us in a month), we drop the flag on
        that specific refusal and retry. Losing the cap costs tokens; keeping
        it would cost us the model entirely.
        """
        last_exc: Exception | None = None
        for _ in range(attempts):
            try:
                data = await self._post_chat(body)
                text = self._extract_text(data)
                tin, tout = self._extract_usage(data)
                payload = extract_json(text)
                return LLMCallResult(payload=payload, tokens_in=tin, tokens_out=tout, model=model)
            except (ProviderError, ValueError) as exc:
                if "reasoning" in body and self._refuses_disabled_reasoning(exc):
                    log.info(
                        "openrouter.reasoning_required",
                        model=model,
                        detail="retrying without the disabled-reasoning flag",
                    )
                    body = {k: v for k, v in body.items() if k != "reasoning"}
                    # Reasoning now shares the output budget, so give the JSON
                    # room to survive it.
                    body["max_tokens"] = max(int(body.get("max_tokens") or 0), 16384)
                    continue
                # Retry on transient network errors and non-JSON responses alike.
                last_exc = exc
                continue
        if isinstance(last_exc, ProviderError):
            raise last_exc
        raise ProviderError(f"{label} failed after {attempts} tries: {last_exc}", kind="parse")

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
        return await self._post_and_extract(body, model, "parse")

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
        return await self._post_and_extract(body, model, "vision parse")
