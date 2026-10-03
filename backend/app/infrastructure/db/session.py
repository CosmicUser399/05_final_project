"""Engine factory, SQLite PRAGMAs and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.config import Settings


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite:")


def _apply_sqlite_pragmas(
    dbapi_connection: object,
    connection_record: object,
    *,
    busy_timeout_ms: int,
) -> None:
    """Enable WAL, foreign keys and busy timeout on each SQLite connect."""
    del connection_record
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
    finally:
        cursor.close()


def create_db_engine(
    database_url: str,
    *,
    busy_timeout_ms: int = 5000,
) -> Engine:
    """Create an engine; apply SQLite PRAGMAs when needed.

    PostgreSQL connections are left unchanged (no SQLite-specific
    settings).
    """
    connect_args: dict[str, object] = {}
    if _is_sqlite(database_url):
        # Required so WAL and busy_timeout apply across threads/tests.
        connect_args["check_same_thread"] = False

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    if _is_sqlite(database_url):

        @event.listens_for(engine, "connect")
        def _on_connect(
            dbapi_connection: object,
            connection_record: object,
        ) -> None:
            _apply_sqlite_pragmas(
                dbapi_connection,
                connection_record,
                busy_timeout_ms=busy_timeout_ms,
            )

    return engine


def create_engine_from_settings(settings: Settings) -> Engine:
    """Build an engine from application settings."""
    return create_db_engine(
        settings.resolved_database_url,
        busy_timeout_ms=settings.db_busy_timeout_ms,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


@contextmanager
def session_scope(
    factory: sessionmaker[Session],
) -> Iterator[Session]:
    """Provide a short-lived session with commit/rollback."""
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def read_sqlite_pragma(connection: Connection, name: str) -> str:
    """Return a SQLite PRAGMA value as a string (tests / diagnostics)."""
    row = connection.exec_driver_sql(f"PRAGMA {name}").fetchone()
    if row is None:
        return ""
    return str(row[0])
