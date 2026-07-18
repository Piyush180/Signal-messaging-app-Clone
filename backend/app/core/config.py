"""
Application configuration.

Everything that can differ between environments (local laptop vs. deployed
server) lives here and is read from environment variables. Nothing secret is
hard-coded: `SECRET_KEY` has a *development-only* default and MUST be overridden
in production via a real environment variable or a `.env` file.

We use pydantic-settings so that:
  - values are validated and type-cast automatically,
  - a local `.env` file is loaded for convenience during development,
  - real environment variables always win over the `.env` file.
"""
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App metadata ---
    PROJECT_NAME: str = "Signal Clone API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"  # "development" | "production"

    # --- Auth / JWT ---
    # NOTE: this default is intentionally obviously-a-dev-key. In production the
    # deploy platform injects a strong random value via the SECRET_KEY env var.
    SECRET_KEY: str = "dev-only-insecure-key-change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Fixed mock OTP. The assignment explicitly allows mocking verification.
    MOCK_OTP_CODE: str = "123456"

    # --- Database ---
    # Async SQLite by default so the project runs with zero external setup.
    DATABASE_URL: str = "sqlite+aiosqlite:///./signal.db"

    # --- CORS ---
    # Comma-separated list of allowed browser origins. We NEVER use "*" together
    # with credentials because the browser forbids that combination.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Auto-create tables + seed demo data on startup (fine for SQLite demo).
    AUTO_INIT_DB: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    # lru_cache => the Settings object is built once and reused (a cheap singleton).
    return Settings()


settings = get_settings()
