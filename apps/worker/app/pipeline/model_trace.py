"""Per-attempt observations; no routing, prompts, retries or paid calls here."""

from __future__ import annotations

import asyncio
from typing import Any

from ..models import JobContext
from ..providers.base import LLMProvider
from ..settings import Settings


def initialize_trace(settings: Settings) -> dict[str, Any]:
    configured = {
        "transcription": (
            settings.asr_backend,
            settings.mlx_whisper_model if settings.asr_backend == "mlx_whisper"
            else settings.openai_transcribe_model,
        ),
        "text": ("primary", settings.primary_text_model),
        "vision_deep": ("primary", settings.primary_vision_deep_model),
        "vision_cheap": ("primary", settings.vision_cheap_model),
        "judge": ("openrouter", settings.clip_judge_model),
    }
    return {
        "schema_version": "1.0",
        "fallback_used": False,
        "stages": {
            stage: {
                "configured_provider": provider,
                "configured_model": model,
                "status": "disabled" if stage == "judge" and not settings.clip_judge_enabled
                else "not_called",
                "calls": [],
            }
            for stage, (provider, model) in configured.items()
        },
    }


def record_call(ctx: JobContext, stage: str, **observation: Any) -> None:
    entry = ctx.model_trace["stages"][stage]
    entry["calls"].append(observation)
    entry["status"] = "called"
    if observation["status"] == "succeeded" and observation["fallback"]:
        ctx.model_trace["fallback_used"] = True


class TracedProvider(LLMProvider):
    """Delegate unchanged calls/results and retain safe model metadata only."""

    def __init__(
        self, provider: LLMProvider, ctx: JobContext, stage: str, step: str,
        *, fallback: bool = False,
    ) -> None:
        self.provider = provider
        self.name = provider.name
        self.ctx = ctx
        self.stage = stage
        self.step = step
        self.fallback = fallback

    async def _call(self, operation: str, kwargs: dict):
        observation = {
            "step": self.step, "operation": operation, "provider": self.name,
            "requested_model": kwargs["model"], "fallback": self.fallback,
        }
        try:
            result = await getattr(self.provider, operation)(**kwargs)
        except (Exception, asyncio.CancelledError) as exc:
            record_call(
                self.ctx, self.stage, **observation,
                status="canceled" if isinstance(exc, asyncio.CancelledError) else "failed",
                model=None, model_source=None, error_type=type(exc).__name__,
            )
            raise
        record_call(
            self.ctx, self.stage, **observation, status="succeeded",
            model=result.model or kwargs["model"],
            model_source=result.model_source,
        )
        return result

    async def chat_json(self, **kwargs):
        return await self._call("chat_json", kwargs)

    async def vision_json(self, **kwargs):
        return await self._call("vision_json", kwargs)

    async def video_json(self, **kwargs):
        return await self._call("video_json", kwargs)
