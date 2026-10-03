"""SQLAlchemy implementation of the database probe port."""

from __future__ import annotations

import logging

from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine (connections are opened lazily)."""
    return create_engine(database_url, pool_pre_ping=True)


class SqlAlchemyDatabaseProbe:
    """Runs ``SELECT 1`` to verify database availability."""

    def __init__(self, engine: Engine) -> None:
        """Store the engine used for probing."""
        self._engine = engine

    def is_available(self) -> bool:
        """Return True when a trivial query succeeds."""
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError:
            logger.warning("database probe failed", exc_info=False)
            return False
        return True
