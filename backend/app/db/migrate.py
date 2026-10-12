"""Run Alembic from inside the app (startup, tests) instead of the CLI.

The CLI still works the same way: `cd backend && alembic upgrade head`.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect

BACKEND_DIR = Path(__file__).resolve().parents[2]
# First revision = the Sprint 1 schema. Databases created by the old `create_all()` code
# have these tables but no alembic_version row; they are stamped here before upgrading.
BASELINE_REVISION = "0001_sprint1_baseline"


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def upgrade_to_head(engine: Engine) -> None:
    cfg = alembic_config()
    with engine.connect() as conn:
        if conn.dialect.name == "sqlite":
            # Batch migrations copy tables; with FKs on, dropping the old copy would
            # cascade-delete child rows. The pragma only works outside a transaction.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        try:
            tables = set(inspect(conn).get_table_names())
            cfg.attributes["connection"] = conn
            if "users" in tables and "alembic_version" not in tables:
                command.stamp(cfg, BASELINE_REVISION)
            command.upgrade(cfg, "head")
            conn.commit()
        finally:
            if conn.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
