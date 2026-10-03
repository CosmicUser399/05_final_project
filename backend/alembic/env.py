"""Alembic migration environment.

Uses ``DATABASE_URL`` / settings for the database URL. SQLite runs with
``render_as_batch=True`` so ALTER operations go through batch mode.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context

import app.infrastructure.db.models  # noqa: F401
from app.config import Settings
from app.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.session import create_db_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Resolve URL without relying on a cached Settings instance."""
    configured = config.get_main_option("sqlalchemy.url")
    placeholder = "driver://user:pass@localhost/dbname"
    if configured and configured != placeholder:
        return configured
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return Settings(database_url=env_url).resolved_database_url
    get_settings.cache_clear()
    return get_settings().resolved_database_url


def _busy_timeout_ms() -> int:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return Settings(database_url=env_url).db_busy_timeout_ms
    get_settings.cache_clear()
    return get_settings().db_busy_timeout_ms


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = _database_url()
    connectable = create_db_engine(
        url,
        busy_timeout_ms=_busy_timeout_ms(),
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite(url),
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
