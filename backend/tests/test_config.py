"""Tests for application settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT
from app.config import Settings


def test_relative_sqlite_url_is_anchored_to_project_root() -> None:
    settings = Settings(database_url="sqlite:///./data/app.db")

    expected = (PROJECT_ROOT / "data" / "app.db").resolve().as_posix()
    assert settings.resolved_database_url == f"sqlite:///{expected}"


def test_absolute_and_non_sqlite_urls_are_unchanged(
    tmp_path: Path,
) -> None:
    absolute = f"sqlite:///{(tmp_path / 'x.db').as_posix()}"
    postgres = "postgresql+psycopg://u:p@localhost/db"

    assert Settings(database_url=absolute).resolved_database_url == absolute
    assert Settings(database_url=postgres).resolved_database_url == postgres


def test_cors_origins_are_split_and_trimmed() -> None:
    settings = Settings(cors_origins=" http://a.test , ,http://b.test ")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_secrets_are_not_exposed_in_repr() -> None:
    settings = Settings(openai_api_key="sk-secret-value")

    assert "sk-secret-value" not in repr(settings)


def test_invalid_env_is_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(app_env="staging")
