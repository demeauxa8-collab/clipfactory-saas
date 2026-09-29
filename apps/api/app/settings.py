from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Postgres
    database_url: str
    database_pool_min: int = 1
    database_pool_max: int = 10

    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Stripe
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_starter_price_id: str

    # R2
    storage_backend: Literal["r2", "local"] = "r2"
    storage_local_dir: str = ""
    media_signing_secret: str = ""
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_clips: str = "clipfactory-clips"
    r2_endpoint_url: str = ""

    # LLM
    openai_api_key: str
    anthropic_api_key: str

    # App
    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"
    turnstile_secret_key: str = ""
    env: Literal["dev", "prod"] = "dev"
    cors_allow_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Analytics — first-party always on; PostHog mirror optional (empty key = off)
    posthog_api_key: str = ""
    posthog_host: str = "https://eu.posthog.com"

    @model_validator(mode="after")
    def _validate_storage(self) -> "Settings":
        if self.storage_backend == "local":
            if not self.storage_local_dir:
                raise ValueError("STORAGE_LOCAL_DIR is required for local storage")
            if len(self.media_signing_secret.encode("utf-8")) < 32:
                raise ValueError("MEDIA_SIGNING_SECRET must be at least 32 bytes")
        elif not all((self.r2_account_id, self.r2_access_key_id,
                      self.r2_secret_access_key, self.r2_endpoint_url)):
            raise ValueError("R2 credentials are required for R2 storage")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
