"""SQLAlchemy unit-of-work wrapper."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.infrastructure.db.repositories import AuditRepository
from app.infrastructure.db.repositories import SystemRepository
from app.infrastructure.db.repositories import SystemVersionRepository
from app.infrastructure.db.repositories import VersionContentRepository


class SqlAlchemyUnitOfWork:
    """Coordinate repositories in one database transaction."""

    systems: SystemRepository
    versions: SystemVersionRepository
    content: VersionContentRepository
    audit: AuditRepository

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """Store the session factory used to open transactions."""
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        """Open a session and wire repositories."""
        self._session = self._session_factory()
        self.systems = SystemRepository(self._session)
        self.versions = SystemVersionRepository(self._session)
        self.content = VersionContentRepository(
            self._session,
            self.versions,
        )
        self.audit = AuditRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Commit on success, rollback on error, always close."""
        if self._session is None:
            return
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None

    @property
    def session(self) -> Session:
        """Return the active SQLAlchemy session."""
        if self._session is None:
            msg = "Unit of work is not active"
            raise RuntimeError(msg)
        return self._session
