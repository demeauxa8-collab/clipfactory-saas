"""Read ``apps/worker/models.lock.toml``, the single source of truth for models.

Settings take their model defaults from here; env vars still override them.
The lock is read once per process. ``MODELS_LOCK_PATH`` points at another file
(tests, benchmarks) without touching code.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_LOCK_PATH = Path(__file__).resolve().parents[1] / "models.lock.toml"
STAGES = (
    "transcription",
    "transcription_local",
    "text",
    "vision_deep",
    "vision_cheap",
    "fallback_text",
    "fallback_vision",
    "clip_judge",
)


class ModelsLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelProfile:
    """Call handling for one model. Unknown models get neutral defaults."""

    min_output_tokens: int = 0
    reasoning_max_tokens: int | None = 0
    usd_per_mtok_input: float = 0.0
    usd_per_mtok_output: float = 0.0
    usd_per_minute: float = 0.0


def lock_path() -> Path:
    return Path(os.environ.get("MODELS_LOCK_PATH") or DEFAULT_LOCK_PATH)


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    try:
        data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ModelsLockError(f"models lock not found: {path}") from exc
    stages = data.get("stages")
    if not isinstance(stages, dict):
        raise ModelsLockError("models lock has no [stages] table")
    for stage in STAGES:
        model = (stages.get(stage) or {}).get("model")
        if not isinstance(model, str) or not model.strip():
            raise ModelsLockError(f"models lock: stage '{stage}' has no model")
    return data


def load_lock() -> dict[str, Any]:
    return _load(str(lock_path()))


def stage_model(stage: str) -> str:
    if stage not in STAGES:
        raise KeyError(stage)
    return str(load_lock()["stages"][stage]["model"])


def model_profile(model: str) -> ModelProfile:
    raw = (load_lock().get("models") or {}).get(model) or {}
    reasoning = raw.get("reasoning_max_tokens", 0)
    return ModelProfile(
        min_output_tokens=int(raw.get("min_output_tokens", 0)),
        reasoning_max_tokens=None if reasoning is None else int(reasoning),
        usd_per_mtok_input=float(raw.get("usd_per_mtok_input", 0.0)),
        usd_per_mtok_output=float(raw.get("usd_per_mtok_output", 0.0)),
        usd_per_minute=float(raw.get("usd_per_minute", 0.0)),
    )


def _assumption(name: str, default: float) -> float:
    return float((load_lock().get("cost_assumptions") or {}).get(name, default))


def text_cents_per_1k_tokens(model: str) -> float:
    """Blended price of mixed prompt/output tokens, in cents per 1k tokens."""
    p = model_profile(model)
    share = _assumption("text_input_share", 0.8)
    usd_per_mtok = share * p.usd_per_mtok_input + (1 - share) * p.usd_per_mtok_output
    return round(usd_per_mtok / 1000 * 100, 6)


def vision_cents_per_frame(model: str, *, deep: bool) -> float:
    tokens = _assumption(
        "vision_deep_tokens_per_frame" if deep else "vision_cheap_tokens_per_frame",
        600 if deep else 300,
    )
    p = model_profile(model)
    share = _assumption("text_input_share", 0.8)
    usd_per_mtok = share * p.usd_per_mtok_input + (1 - share) * p.usd_per_mtok_output
    return round(tokens * usd_per_mtok / 1_000_000 * 100, 6)


def transcribe_cents_per_minute(model: str) -> float:
    return round(model_profile(model).usd_per_minute * 100, 6)
