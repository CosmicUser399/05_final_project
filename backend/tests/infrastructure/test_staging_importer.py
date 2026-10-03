"""StagingImporter rejects broken Fabricate artifacts."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.domain.errors import ValidationError
from app.infrastructure.files.staging_importer import StagingImporter
from app.infrastructure.mcp.mock_fabricate import _build_staging_sqlite


def test_import_valid_mock_artifact() -> None:
    importer = StagingImporter()
    payload = importer.import_bytes(
        _build_staging_sqlite(),
        conversation_id="conv_test",
    )
    assert len(payload.equipment) == 3
    assert payload.metadata["generated_by"] == "fabricate"
    assert payload.metadata["conversation_id"] == "conv_test"


def test_duplicate_tag_rejected() -> None:
    blob = _sqlite_with(
        """
        CREATE TABLE equipment (
            tag TEXT, name TEXT, parent_tag TEXT, category TEXT
        );
        INSERT INTO equipment VALUES ('P-1', 'A', NULL, 'ROTATING');
        INSERT INTO equipment VALUES ('P-1', 'B', NULL, 'ROTATING');
        """
    )
    with pytest.raises(ValidationError) as exc:
        StagingImporter().import_bytes(blob, conversation_id="c1")
    assert exc.value.code == "STAGING_DUPLICATE_TAG"


def test_broken_parent_rejected() -> None:
    blob = _sqlite_with(
        """
        CREATE TABLE equipment (
            tag TEXT, name TEXT, parent_tag TEXT, category TEXT
        );
        INSERT INTO equipment VALUES ('P-1', 'A', 'MISSING', 'ROTATING');
        """
    )
    with pytest.raises(ValidationError) as exc:
        StagingImporter().import_bytes(blob, conversation_id="c1")
    assert exc.value.code == "STAGING_BROKEN_PARENT"


def test_parent_cycle_rejected() -> None:
    blob = _sqlite_with(
        """
        CREATE TABLE equipment (
            tag TEXT, name TEXT, parent_tag TEXT, category TEXT
        );
        INSERT INTO equipment VALUES ('A', 'A', 'B', 'PROCESS');
        INSERT INTO equipment VALUES ('B', 'B', 'A', 'PROCESS');
        """
    )
    with pytest.raises(ValidationError) as exc:
        StagingImporter().import_bytes(blob, conversation_id="c1")
    assert exc.value.code == "STAGING_PARENT_CYCLE"


def test_non_sqlite_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        StagingImporter().import_bytes(b"not-sqlite", conversation_id="c1")
    assert exc.value.code == "STAGING_INVALID_FORMAT"


def _sqlite_with(script: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.sqlite"
        conn = sqlite3.connect(path)
        try:
            conn.executescript(script)
            conn.commit()
        finally:
            conn.close()
        return path.read_bytes()
