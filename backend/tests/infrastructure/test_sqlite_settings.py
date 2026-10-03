"""SQLite connection PRAGMA and foreign-key tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models import EquipmentRow
from app.infrastructure.db.models import SystemRow
from app.infrastructure.db.models import SystemVersionRow
from app.infrastructure.db.session import read_sqlite_pragma


def test_sqlite_pragmas_enabled(engine: Engine) -> None:
    with engine.connect() as connection:
        assert read_sqlite_pragma(connection, "foreign_keys") in {
            "1",
            "ON",
            "on",
        }
        journal = read_sqlite_pragma(connection, "journal_mode").lower()
        assert journal == "wal"
        assert int(read_sqlite_pragma(connection, "busy_timeout")) >= 5000
        sync = read_sqlite_pragma(connection, "synchronous").lower()
        assert sync in {"1", "normal"}


def test_foreign_keys_reject_orphan_equipment(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            EquipmentRow(
                id=uuid4(),
                version_id=uuid4(),
                lineage_id=uuid4(),
                tag="X-1",
                name="Orphan",
                quantity=1,
                criticality="MEDIUM",
                operating_mode="CONTINUOUS",
                standby_mode="NONE",
                is_repairable=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_two_connections_read_and_write_without_lock(
    engine: Engine,
) -> None:
    system_id = uuid4()
    version_id = uuid4()
    with Session(engine) as writer:
        writer.add(
            SystemRow(
                id=system_id,
                name="Plant",
                description=None,
                created_by=None,
            )
        )
        writer.add(
            SystemVersionRow(
                id=version_id,
                system_id=system_id,
                lineage_id=uuid4(),
                version_number=1,
                status="DRAFT",
            )
        )
        writer.commit()

    with Session(engine) as writer, Session(engine) as reader:
        writer.add(
            EquipmentRow(
                id=uuid4(),
                version_id=version_id,
                lineage_id=uuid4(),
                tag="P-101",
                name="Pump",
                quantity=1,
                criticality="HIGH",
                operating_mode="CONTINUOUS",
                standby_mode="NONE",
                is_repairable=True,
            )
        )
        writer.commit()
        count = reader.execute(
            text("SELECT COUNT(*) FROM equipment")
        ).scalar_one()
        assert count == 1
