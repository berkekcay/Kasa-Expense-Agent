"""Alembic environment for Kasa.

URL lookup order: `-x url=...`, MIGRATION_DATABASE_URL, then the app setting DATABASE_URL.
When the app runs migrations itself (`app.db.migrate`), it passes an open connection in
`config.attributes["connection"]` and none of that applies.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    if x_args.get("url"):
        return x_args["url"]
    if os.environ.get("MIGRATION_DATABASE_URL"):
        return os.environ["MIGRATION_DATABASE_URL"]
    from app.config import get_settings

    return get_settings().database_url


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        # SQLite can't ALTER constraints; batch mode rebuilds the table instead.
        render_as_batch=True,
        compare_type=True,
        **kwargs,
    )


def run_offline() -> None:
    """`alembic upgrade head --sql`: print the DDL instead of running it."""
    _configure(url=_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    dialect = context.get_context().dialect
    if dialect.name == "mssql":
        # Offline there is no server to ask for its version, and SQLAlchemy then renders
        # for SQL Server 2005 (DATE -> DATETIME, NVARCHAR(max) -> NTEXT). Target 2022 instead.
        dialect.server_version_info = (16,)
        dialect.deprecate_large_types = None
        dialect._setup_version_attributes()
        dialect._supports_nvarchar_max = True
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    if config.config_file_name is not None:
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    engine = create_engine(_url(), poolclass=pool.NullPool)
    if engine.dialect.name == "mssql":
        from app.db.session import install_connect_retry

        install_connect_retry(engine)  # wait for a paused Azure SQL database to resume
    with engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")  # see app.db.migrate
            conn.commit()  # the pragma autobegan a transaction; let Alembic own the next one
        _configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()
        conn.commit()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
