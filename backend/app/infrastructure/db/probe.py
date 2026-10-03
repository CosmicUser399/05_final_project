"""SQLAlchemy implementation of the database probe port."""

from __future__ import annotations

import logging

from sqlalchemy import Engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.infrastructure.db.session import create_db_engine
from app.infrastructure.db.session import create_engine_from_settings

__all__ = [
    "SqlAlchemyDatabaseProbe",
    "create_db_engine",
    "create_engine_from_settings",
]

logger = logging.getLogger(__name__)


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
