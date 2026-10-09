"""Engine + session factory.

Every session carries the acting user's id in `session.info["user_id"]`. On SQL Server,
each new transaction pushes that id into SESSION_CONTEXT so the row-level security
policy in `sql/mssql/002_row_level_security.sql` filters rows server-side as a second
line of defence (the services also filter by user explicitly).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_fk_on(dbapi_conn, _record):  # SQLite ignores FKs unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    # pool_pre_ping recovers connections dropped while a Cloud Run instance sat idle.
    return create_engine(url, pool_pre_ping=True)


def get_engine() -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = _make_engine(get_settings().database_url)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db() -> None:
    """Create tables for local SQLite dev. SQL Server is provisioned from sql/mssql/*.sql."""
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)


@event.listens_for(Session, "after_begin")
def _set_mssql_session_context(session: Session, _transaction, connection) -> None:
    if connection.dialect.name != "mssql":
        return
    # Not read-only: pooled connections are reused by other users, so every
    # transaction re-sets (or clears) the value.
    connection.execute(
        text("EXEC sp_set_session_context @key = N'user_id', @value = :uid"),
        {"uid": session.info.get("user_id")},
    )


@contextmanager
def session_for(user_id: str | None) -> Iterator[Session]:
    """Open a session acting as `user_id` (None = system, e.g. migrations/seed)."""
    get_engine()
    assert _session_factory is not None
    session = _session_factory(info={"user_id": user_id})
    try:
        yield session
    finally:
        session.close()
