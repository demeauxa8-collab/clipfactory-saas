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
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = await self._post_chat(body)
        text = self._extract_text(data)
        tin, tout = self._extract_usage(data)
        try:
            payload = extract_json(text)
        except ValueError as exc:
            raise ProviderError(f"parse failed: {exc}", kind="parse") from exc
        return LLMCallResult(payload=payload, tokens_in=tin, tokens_out=tout, model=model)

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
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        }
        data = await self._post_chat(body)
        text = self._extract_text(data)
        tin, tout = self._extract_usage(data)
        try:
            payload = extract_json(text)
        except ValueError as exc:
            raise ProviderError(f"vision parse failed: {exc}", kind="parse") from exc
        return LLMCallResult(payload=payload, tokens_in=tin, tokens_out=tout, model=model)
