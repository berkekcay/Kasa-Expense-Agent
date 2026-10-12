"""Engine + session factory.

Every session carries the acting user's id in `session.info["user_id"]`. On SQL Server,
each new transaction pushes that id into SESSION_CONTEXT so the row-level security policy
(created by the Alembic migrations) filters rows server-side as a second line of defence
(the services also filter by user explicitly).
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_migrated = False
_migrate_lock = threading.Lock()


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
    """Bring the schema to the latest Alembic revision (once per process).

    With AUTO_MIGRATE=false (prod) this does nothing; migrations run as a deploy step.
    """
    global _migrated
    if _migrated or not get_settings().auto_migrate:
        return
    with _migrate_lock:
        if _migrated:
            return
        from app.db.migrate import upgrade_to_head  # alembic is only imported when needed

        upgrade_to_head(get_engine())
        _migrated = True


@event.listens_for(Session, "after_begin")
def _set_mssql_session_context(session: Session, _transaction, connection) -> None:
    if connection.dialect.name != "mssql":
        return
    # Not read-only: pooled connections are reused by other users, so every
    # transaction re-sets (or clears) both values.
    connection.execute(
        text(
            "EXEC sp_set_session_context @key = N'user_id', @value = :uid; "
            "EXEC sp_set_session_context @key = N'kasa_system', @value = :system;"
        ),
        {"uid": session.info.get("user_id"), "system": 1 if session.info.get("system") else None},
    )


@contextmanager
def session_for(user_id: str | None, *, system: bool = False) -> Iterator[Session]:
    """Open a session acting as `user_id`.

    `system=True` is for background jobs only (Cloud Scheduler sync, Pub/Sub push) that
    must find rows across users, e.g. the Google account for an incoming Gmail address.
    Only the RLS predicates that explicitly allow it (google_accounts) honour the flag.
    Do the per-user work in a normal `session_for(user_id)` afterwards.
    """
    get_engine()
    assert _session_factory is not None
    session = _session_factory(info={"user_id": user_id, "system": system})
    try:
        yield session
    finally:
        session.close()
