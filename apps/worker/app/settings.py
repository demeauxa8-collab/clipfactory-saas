from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # DB / Redis
    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    # R2
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_clips: str = "clipfactory-clips"
    r2_endpoint_url: str

    # ---------------- Providers ----------------

    # Transcription (OpenAI direct — no equivalent cheaper)
    openai_api_key: str
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"

    # Primary LLM stack (OpenRouter — text + vision deep + vision cheap)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = "https://clipfactory.app"
    openrouter_app_name: str = "ClipFactory"

    primary_text_model: str = "deepseek/deepseek-chat-v3.2"
    primary_vision_deep_model: str = "google/gemini-2.5-flash"
    vision_cheap_model: str = "qwen/qwen3-vl-flash"

    # Fallback / eval stack (Anthropic)
    anthropic_api_key: str = ""
    fallback_text_model: str = "claude-haiku-4-5-20251001"
    fallback_vision_model: str = "claude-haiku-4-5-20251001"

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

    # ---------------- Pipeline routing ----------------

    # Below this duration in seconds: simple single-window pipeline.
    # At/above: story-first multi-segment pipeline.
    story_pipeline_threshold_seconds: int = 300

    # ---------------- App ----------------

    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"

    # ---------------- Cost model (cents) ----------------

    cost_transcribe_cents_per_min: float = 0.3
    cost_vision_cheap_cents_per_frame: float = 0.02
    cost_vision_deep_cents_per_frame: float = 0.04
    cost_text_cents_per_1k_tokens: float = 0.03


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
