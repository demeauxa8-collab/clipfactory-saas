"""models.lock.toml is the single source of truth for model defaults."""

import tomllib
from datetime import date

import pytest

from app import models_lock
from app.settings import Settings

# Models with an announced OpenRouter expiry: no default may point at them.
EXPIRING = {
    "qwen/qwen3-vl-32b-instruct": date(2026, 10, 9),
    "google/gemini-2.5-flash": date(2026, 10, 20),
}
RETIRED = {"deepseek/deepseek-chat-v3.2", "qwen/qwen3-vl-flash", "gpt-4o-mini-transcribe"}


def settings(**overrides):
    return Settings(
        database_url="postgresql://x@127.0.0.1/x",
        r2_account_id="x",
        r2_access_key_id="x",
        r2_secret_access_key="x",
        r2_endpoint_url="https://example.com",
        openai_api_key="x",
        **overrides,
    )


def test_every_stage_default_comes_from_the_lock(monkeypatch):
    for env in (
        "OPENAI_TRANSCRIBE_MODEL",
        "PRIMARY_TEXT_MODEL",
        "PRIMARY_VISION_DEEP_MODEL",
        "VISION_CHEAP_MODEL",
        "FALLBACK_TEXT_MODEL",
        "FALLBACK_VISION_MODEL",
        "CLIP_JUDGE_MODEL",
    ):
        monkeypatch.delenv(env, raising=False)
    s = settings(_env_file=None)
    assert s.openai_transcribe_model == models_lock.stage_model("transcription")
    assert s.primary_text_model == models_lock.stage_model("text")
    assert s.primary_vision_deep_model == models_lock.stage_model("vision_deep")
    assert s.vision_cheap_model == models_lock.stage_model("vision_cheap")
    assert s.fallback_text_model == models_lock.stage_model("fallback_text")
    assert s.fallback_vision_model == models_lock.stage_model("fallback_vision")
    assert s.clip_judge_model == models_lock.stage_model("clip_judge")
    assert s.clip_judge_enabled is False


def test_no_default_points_at_an_expiring_or_retired_model():
    models = {models_lock.stage_model(stage) for stage in models_lock.STAGES}
    assert not models & set(EXPIRING)
    assert not models & RETIRED


def test_lock_is_marked_provisional():
    assert "provisional — pending benchmark 2026-09-29" in models_lock.lock_path().read_text()


def test_swapping_a_model_needs_no_code_change(tmp_path, monkeypatch):
    text = models_lock.lock_path().read_text().replace(
        'model = "qwen/qwen3-vl-30b-a3b-instruct"', 'model = "vendor/other-vl"'
    )
    alt = tmp_path / "models.lock.toml"
    alt.write_text(text)
    monkeypatch.setenv("MODELS_LOCK_PATH", str(alt))
    monkeypatch.delenv("VISION_CHEAP_MODEL", raising=False)
    assert settings(_env_file=None).vision_cheap_model == "vendor/other-vl"
    # Env still overrides the lock for a single host.
    monkeypatch.setenv("VISION_CHEAP_MODEL", "vendor/env-vl")
    assert settings(_env_file=None).vision_cheap_model == "vendor/env-vl"


def test_costs_follow_the_configured_models(monkeypatch):
    for env in ("PRIMARY_TEXT_MODEL", "COST_TEXT_CENTS_PER_1K_TOKENS"):
        monkeypatch.delenv(env, raising=False)
    s = settings(_env_file=None)
    # gemini-3.8-flash: 0.8 * 0.75 + 0.2 * 3.75 = 1.35 $/Mtok = 0.135 c/1k tokens
    assert s.cost_text_cents_per_1k_tokens == pytest.approx(0.135)
    # whisper-1: 0.006 $/min
    assert s.cost_transcribe_cents_per_min == pytest.approx(0.6)
    pinned = settings(_env_file=None, cost_text_cents_per_1k_tokens=1.0)
    assert pinned.cost_text_cents_per_1k_tokens == 1.0


def test_env_example_matches_the_lock():
    env = {}
    for line in (models_lock.DEFAULT_LOCK_PATH.parent / ".env.example").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    lock = tomllib.loads(models_lock.DEFAULT_LOCK_PATH.read_text())
    for stage in lock["stages"].values():
        assert env.get(stage["env"]) == stage["model"], stage["env"]
