"""Application configuration loaded from environment variables.

Central place for all settings. Values are read from the environment (or a
`.env` file) at import time and never hardcoded. Secrets must never be logged.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")
    pricepilot_enable_fixtures: bool = Field(default=False)
    app_name: str = Field(default="PricePilot API")
    api_prefix: str = Field(default="/api/v1")

    # --- Runtime ---
    database_url: str = Field(
        default="postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    db_pool_recycle: int = Field(default=1800, ge=60)
    jwt_secret: str = Field(default="change-me-in-prod")
    pricepilot_public_base_url: str = Field(default="http://localhost:8000")
    cors_origin: str = Field(default="http://localhost:3000")

    # --- Price monitoring (Phase 5) ---
    monitor_enabled: bool = Field(default=True)
    monitor_poll_interval_seconds: int = Field(default=3600)
    monitor_provider_timeout_seconds: float = Field(default=15.0)
    monitor_max_concurrency: int = Field(default=4)
    monitor_retry_count: int = Field(default=2)
    monitor_observation_window_seconds: int = Field(default=3600)

    # --- Notifications ---
    pricepilot_notification_provider: str = Field(default="")
    smtp_host: str | None = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: str | None = Field(default=None)
    smtp_password: str | None = Field(default=None)
    smtp_sender: str | None = Field(default=None)

    # --- AI providers ---
    ai_provider: str | None = Field(default=None)  # e.g. "openai-compatible" | "ollama"
    ai_model: str | None = Field(default=None)
    ai_api_key: str | None = Field(default=None)
    ai_base_url: str | None = Field(default=None)
    ai_temperature: float = Field(default=0.2)
    ai_max_tokens: int = Field(default=2048)
    ai_embedding_model: str | None = Field(default=None)  # e.g. text-embedding-3-small

    # --- Embedding / vision / review providers (comma-sep names) ---
    pricepilot_embedding_provider: str = Field(default="")
    pricepilot_vision_provider: str = Field(default="")
    pricepilot_review_provider: str = Field(default="")

    # --- Search & Page Reader APIs ---
    google_cse_api_key: str | None = Field(default=None)
    google_cse_cx: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)
    serper_api_key: str | None = Field(default=None)
    jina_api_key: str | None = Field(default=None)

    # --- Search providers ---
    pricepilot_search_provider: str = Field(default="google_cse,tavily,serper,web_search,wholesale_supplier")
    off_api_base_url: str = Field(default="https://world.openfoodfacts.org")
    off_timeout_seconds: float = Field(default=12.0)
    off_max_page_size: int = Field(default=20)

    # --- Web ---
    next_public_api_base_url: str = Field(default="http://localhost:8000")

    @field_validator("log_level")
    @classmethod
    def _coerce_log_level(cls, v: str) -> str:
        return v.upper()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def search_providers_enabled(self) -> bool:
        """Slots currently enabled, driving provider availability in the API response."""
        slots: list[str] = []
        if self.pricepilot_search_provider.strip():
            slots.append(self.pricepilot_search_provider)
        if self.ai_provider and self.ai_api_key:
            slots.append(self.ai_provider)
        return bool(slots)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()