"""Application settings loaded from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

SOFTWARE_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SQLITE_PREFIX = "sqlite:///"


class Settings(BaseSettings):
    """Typed configuration; secrets come only from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    database_url: str = "sqlite:///./data/app.db"
    db_busy_timeout_ms: int = Field(default=5000, ge=0)

    simulation_default_seed: int = 12345
    simulation_max_runs: int = Field(default=100_000, ge=1)
    simulation_max_workers: int = Field(default=4, ge=1, le=64)
    simulation_max_horizon_years: float = Field(
        default=50.0,
        gt=0,
        le=200,
    )
    simulation_result_batch_size: int = Field(
        default=500,
        ge=1,
        le=10_000,
    )
    simulation_heartbeat_timeout_seconds: int = Field(
        default=120,
        ge=10,
    )
    simulation_worker_poll_seconds: float = Field(
        default=1.0,
        gt=0,
    )
    simulation_sse_poll_seconds: float = Field(
        default=0.5,
        gt=0,
    )
    simulation_event_log_runs: int = Field(default=5, ge=0)

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None

    fabricate_api_url: str | None = None
    fabricate_api_key: SecretStr | None = None

    petri_pilot_mcp_url: str | None = None
    petri_pilot_api_key: SecretStr | None = None

    redis_url: str | None = None

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Return CORS origins as a list of non-empty strings."""
        parts = (item.strip() for item in self.cors_origins.split(","))
        return [item for item in parts if item]

    @property
    def resolved_database_url(self) -> str:
        """Return the URL with relative SQLite paths anchored to the root.

        ``sqlite:///./data/app.db`` always means ``<repo>/data/app.db``,
        regardless of the process working directory.
        """
        if not self.database_url.startswith(_SQLITE_PREFIX):
            return self.database_url
        raw = self.database_url[len(_SQLITE_PREFIX) :]
        if not raw or raw.startswith(":memory:") or Path(raw).is_absolute():
            return self.database_url
        absolute = (PROJECT_ROOT / raw).resolve()
        return f"{_SQLITE_PREFIX}{absolute.as_posix()}"

    @property
    def software_version(self) -> str:
        """Return the application version for simulation fingerprints."""
        return SOFTWARE_VERSION


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
