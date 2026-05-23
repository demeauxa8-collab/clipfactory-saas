from __future__ import annotations

import base64

import structlog
from anthropic import APIError, APIStatusError, APITimeoutError, AsyncAnthropic

from ..settings import get_settings
from ._jsonparse import extract_json
from .base import ImageInput, LLMCallResult, LLMProvider, ProviderError

log = structlog.get_logger()


class AnthropicProvider(LLMProvider):
    """Fallback / eval provider — Claude Haiku for text and vision.

    Used when:
      - The primary OpenRouter call fails (parse error, timeout, http error)
      - eval_sample_rate triggers a parallel run for benchmarking
    """

    name = "anthropic"

    def __init__(self, timeout_seconds: float = 90.0) -> None:
        self._timeout = timeout_seconds

    def _client(self) -> AsyncAnthropic:
        s = get_settings()
        if not s.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY not set", kind="http")
        return AsyncAnthropic(api_key=s.anthropic_api_key, timeout=self._timeout)

    async def chat_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        client = self._client()
        try:
            msg = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APITimeoutError as exc:
            raise ProviderError(f"anthropic timeout: {exc}", kind="timeout") from exc
        except APIStatusError as exc:
            raise ProviderError(f"anthropic {exc.status_code}: {exc}", kind="http") from exc
        except APIError as exc:
            raise ProviderError(f"anthropic error: {exc}", kind="http") from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            payload = extract_json(text)
        except ValueError as exc:
            raise ProviderError(f"parse failed: {exc}", kind="parse") from exc
        return LLMCallResult(
            payload=payload,
            tokens_in=int(msg.usage.input_tokens or 0),
            tokens_out=int(msg.usage.output_tokens or 0),
            model=model,
        )

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
        # Anthropic content shape: [{"type":"image","source":{"type":"base64",...}}, ...]
        content: list[dict] = []
        for img in images:
            if img.bytes_jpeg:
                b64 = base64.b64encode(img.bytes_jpeg).decode("ascii")
                content.append(
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    }
                )
            elif img.url:
                content.append({"type": "image", "source": {"type": "url", "url": img.url}})
        content.append({"type": "text", "text": user_text})

        client = self._client()
        try:
            msg = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": content}],
            )
        except APITimeoutError as exc:
            raise ProviderError(f"anthropic timeout: {exc}", kind="timeout") from exc
        except APIStatusError as exc:
            raise ProviderError(f"anthropic {exc.status_code}: {exc}", kind="http") from exc
        except APIError as exc:
            raise ProviderError(f"anthropic error: {exc}", kind="http") from exc

        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        try:
            payload = extract_json(text)
        except ValueError as exc:
            raise ProviderError(f"vision parse failed: {exc}", kind="parse") from exc
        return LLMCallResult(
            payload=payload,
            tokens_in=int(msg.usage.input_tokens or 0),
            tokens_out=int(msg.usage.output_tokens or 0),
            model=model,
        )
