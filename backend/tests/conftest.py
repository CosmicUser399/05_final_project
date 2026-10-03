"""Shared fixtures for API and database integration tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.config import Settings
from app.config import get_settings
from app.infrastructure.db.session import create_db_engine
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    # Absolute path so Alembic and the app engine share one file.
    if database_url.startswith("sqlite:///"):
        raw = database_url[len("sqlite:///") :]
        absolute = Path(raw).resolve().as_posix()
        database_url = f"sqlite:///{absolute}"
    config.set_main_option("sqlalchemy.url", database_url)
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    return config


def apply_migrations(database_url: str) -> None:
    """Apply all Alembic migrations to ``database_url``."""
    command.upgrade(_alembic_config(database_url), "head")


def downgrade_migrations(database_url: str) -> None:
    """Downgrade the database to base."""
    command.downgrade(_alembic_config(database_url), "base")


@pytest.fixture()
def sqlite_url(tmp_path: Path) -> str:
    """Return a file-based SQLite URL (WAL-capable)."""
    db_path = (tmp_path / "test.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


@pytest.fixture()
def engine(sqlite_url: str) -> Iterator[Engine]:
    """Create an engine with PRAGMAs and a migrated schema."""
    apply_migrations(sqlite_url)
    get_settings.cache_clear()
    eng = create_db_engine(sqlite_url, busy_timeout_ms=5000)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to the test engine."""
    return create_session_factory(engine)


@pytest.fixture()
def uow_factory(
    session_factory: sessionmaker[Session],
) -> Iterator[object]:
    """Return a factory that builds a unit of work."""

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    yield factory


@pytest.fixture()
def client(sqlite_url: str) -> Iterator[TestClient]:
    """HTTP client against an app with a migrated SQLite database."""
    apply_migrations(sqlite_url)
    get_settings.cache_clear()
    settings = Settings(
        app_env="test",
        database_url=sqlite_url,
        log_json=False,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client
