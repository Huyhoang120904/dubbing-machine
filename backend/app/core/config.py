"""Application settings, loaded from the environment (and `.env`)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated configuration.

    Environment variables are matched case-insensitively to the field names,
    e.g. `DATABASE_URL`, `LOG_LEVEL`. Values in `.env` are loaded too, but the
    real environment always wins.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -----------------------------------------------------
    app_name: str = "dubbing"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # --- Database --------------------------------------------------------
    # Must use an async driver, e.g. sqlite+aiosqlite:///./dubbing.db
    database_url: str = "sqlite+aiosqlite:///./dubbing.db"
    sql_echo: bool = False

    # --- HTTP ------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=list)

    # --- Logging ---------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        """Fail fast on a sync driver, which the async engine cannot use."""
        if value.startswith("sqlite") and "+aiosqlite" not in value:
            raise ValueError(
                "SQLite URLs must use the async driver, e.g. 'sqlite+aiosqlite:///./dubbing.db'",
            )
        return value

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so it is safe (and cheap) to use as a FastAPI dependency. Tests that
    mutate the environment should call `get_settings.cache_clear()`.
    """
    return Settings()
