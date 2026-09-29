from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import models_lock


def _locked(stage: str):
    return Field(default_factory=lambda: models_lock.stage_model(stage))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB / Redis
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # Storage backend: "r2" (prod) uploads to Cloudflare R2; "local" (dev)
    # copies clips into storage_local_dir so the pipeline runs without R2 creds.
    storage_backend: Literal["r2", "local"] = "r2"
    storage_local_dir: str = "/tmp/clipfactory-clips"

    # R2
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_clips: str = "clipfactory-clips"
    r2_endpoint_url: str

    # ---------------- Providers ----------------

    # Transcription (OpenAI direct — no equivalent cheaper)
    openai_api_key: str
    # Every model default below comes from apps/worker/models.lock.toml (the
    # single source of truth). Env vars still override a stage for one host.
    # whisper-1 is required for word timestamps: the gpt-4o-*-transcribe family
    # rejects verbose_json, which transcribe() asks for.
    openai_transcribe_model: str = _locked("transcription")

    # Primary LLM stack (OpenRouter — text + vision deep + vision cheap)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://clipfactory.app"
    openrouter_app_name: str = "ClipFactory"

    # A dead or expired ID returns a 400 and the job silently falls through to
    # the fallback provider: keep the lock free of models with an announced
    # expiry. Vision cost scales with our own frame size (ffmpeg.extract_frame
    # caps frames at 512 px wide) — see docs/model-landscape.md §6.
    primary_text_model: str = _locked("text")
    primary_vision_deep_model: str = _locked("vision_deep")
    vision_cheap_model: str = _locked("vision_cheap")

    # Fallback / eval stack (Anthropic)
    anthropic_api_key: str = ""
    fallback_text_model: str = _locked("fallback_text")
    fallback_vision_model: str = _locked("fallback_vision")

    # Clip judge: sends each rendered clip as native video to the judge model.
    # Off by default; it is a paid call per delivered clip.
    clip_judge_enabled: bool = False
    clip_judge_model: str = _locked("clip_judge")
    clip_judge_max_video_mb: float = 18.0

    # Fallback toggle and eval sampling
    enable_fallback: bool = True
    eval_sample_rate: float = 0.0   # 0..1, fraction of jobs that run secondary in parallel for A/B

    # ---------------- Worker ----------------

    worker_concurrency: int = 1
    worker_tmp_dir: str = "/tmp/clipfactory"
    worker_poll_interval: int = 2
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    yt_dlp_bin: str = "yt-dlp"
    # Bound stalled decoders/downloaders and reap their children on cancellation.
    subprocess_timeout_seconds: float = 900.0
    # Optional browser to pull YouTube cookies from (e.g. "chrome") — helps dodge
    # 403 bot-blocks when downloading. Empty disables the flag.
    yt_dlp_cookies_from_browser: str = ""

    # ---------------- Pipeline routing ----------------

    # Below this duration in seconds: simple single-window pipeline.
    # At/above: story-first multi-segment pipeline.
    story_pipeline_threshold_seconds: int = 300

    # ---------------- App ----------------

    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"

    # Analytics — first-party always on; PostHog mirror optional (empty key = off)
    posthog_api_key: str = ""
    posthog_host: str = "https://eu.posthog.com"

    # ---------------- Cost model (cents) ----------------

    # Left unset, each is derived from models.lock.toml prices for the model
    # actually configured for that stage. Used for cost logging only.
    cost_transcribe_cents_per_min: float | None = None
    cost_vision_cheap_cents_per_frame: float | None = None
    cost_vision_deep_cents_per_frame: float | None = None
    cost_text_cents_per_1k_tokens: float | None = None

    @model_validator(mode="after")
    def _derive_costs(self) -> "Settings":
        if self.cost_transcribe_cents_per_min is None:
            self.cost_transcribe_cents_per_min = models_lock.transcribe_cents_per_minute(
                self.openai_transcribe_model
            )
        if self.cost_vision_cheap_cents_per_frame is None:
            self.cost_vision_cheap_cents_per_frame = models_lock.vision_cents_per_frame(
                self.vision_cheap_model, deep=False
            )
        if self.cost_vision_deep_cents_per_frame is None:
            self.cost_vision_deep_cents_per_frame = models_lock.vision_cents_per_frame(
                self.primary_vision_deep_model, deep=True
            )
        if self.cost_text_cents_per_1k_tokens is None:
            self.cost_text_cents_per_1k_tokens = models_lock.text_cents_per_1k_tokens(
                self.primary_text_model
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
