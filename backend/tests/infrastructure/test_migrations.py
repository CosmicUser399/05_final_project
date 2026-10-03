"""Alembic migration upgrade/downgrade smoke tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy import text

from tests.conftest import apply_migrations
from tests.conftest import downgrade_migrations


def test_migrations_upgrade_and_downgrade(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    apply_migrations(url)

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert "systems" in tables
    assert "system_versions" in tables
    assert "equipment" in tables
    assert "failure_modes" in tables
    assert "maintenance_tasks" in tables
    assert "alembic_version" in tables
    engine.dispose()

    downgrade_migrations(url)
    engine = create_engine(url)
    remaining = set(inspect(engine).get_table_names())
    assert "systems" not in remaining
    assert remaining == {"alembic_version"} or remaining <= {"alembic_version"}
    with engine.connect() as connection:
        version = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).fetchone()
        assert version is None or version[0] is None
    engine.dispose()
