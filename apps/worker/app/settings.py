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

    # LLM providers
    openai_api_key: str
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"

    anthropic_api_key: str
    anthropic_text_model: str = "claude-haiku-4-5-20251001"
    anthropic_vision_model: str = "claude-haiku-4-5-20251001"

    # Worker
    worker_concurrency: int = 1
    worker_tmp_dir: str = "/tmp/clipfactory"
    worker_poll_interval: int = 2
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    yt_dlp_bin: str = "yt-dlp"

    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"

    # Cost model (cents)
    cost_transcribe_cents_per_min: float = 0.3
    cost_vision_cents_per_frame: float = 0.05
    cost_text_cents_per_1k_tokens: float = 0.08


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
