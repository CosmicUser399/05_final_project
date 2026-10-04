"""Unit tests for OREDA / ISO reference repositories."""

from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.infrastructure.reference_data.iso14224_repository import (
    ISO14224Repository,
)
from app.infrastructure.reference_data.oreda_repository import OREDARepository


def test_ingest_and_search_demo_seeds(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        oreda = OREDARepository(session)
        iso = ISO14224Repository(session)
        assert oreda.ingest_csv() >= 1
        assert iso.ingest_json() >= 1
        # Second ingest without replace is a no-op.
        assert oreda.ingest_csv() == 0
        assert iso.ingest_json() == 0
        session.commit()

        hits = oreda.search(query="compressor", limit=10)
        assert hits
        assert all(hit.source_type.value == "OREDA" for hit in hits)
        node = iso.find_by_code("PUMP.CENT")
        assert node is not None
        assert node.name.lower().find("pump") >= 0
