from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


class ProviderError(RuntimeError):
    """Raised when a provider call fails for a recoverable reason (HTTP error,
    JSON parse failure, empty response). Used by the runner to decide whether
    to fall back to a secondary provider.
    """

    def __init__(self, message: str, *, kind: str = "unknown") -> None:
        super().__init__(message)
        self.kind = kind  # "http" | "parse" | "empty" | "timeout" | "unknown"


@dataclass
class LLMCallResult:
    """Wraps a parsed LLM response plus the metadata needed for cost logging."""

    payload: Any                   # parsed JSON (dict / list / object) or raw text
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""

    @property
    def tokens_total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass
class ImageInput:
    """Carries an image to a vision provider. Either raw bytes (preferred for
    base64 transport) or a URL — providers convert as needed.
    """

    bytes_jpeg: bytes | None = None
    url: str | None = None
    label: str | None = None


class LLMProvider(ABC):
    """Common interface used by the pipeline so we can swap providers per call.

    Implementations:
      - OpenRouterProvider  -> primary (DeepSeek text + Gemini vision deep + Qwen vision cheap)
      - AnthropicProvider   -> fallback (Claude Haiku everywhere)
    """

    name: str = "abstract"

    # ---------- Text JSON tasks ----------

    @abstractmethod
    async def chat_json(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        """Send a text-only message, expect JSON in the response.
        Implementations MUST parse the JSON and raise ProviderError(kind='parse')
        if parsing fails. They MUST raise ProviderError(kind='http'|'timeout') on
        transport errors. They MUST return the parsed object in .payload.
        """

    # ---------- Vision JSON tasks ----------

    @abstractmethod
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
        """Same contract as chat_json but with a list of images attached."""
