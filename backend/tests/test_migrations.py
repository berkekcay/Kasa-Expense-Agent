"""Alembic is the only source of the schema: the migrations must build exactly the models."""

import io

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import BASELINE_REVISION, alembic_config, upgrade_to_head
from app.db.models import Base


@pytest.fixture
def fresh_engine(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    yield engine
    engine.dispose()


def _diff(engine):
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)


def _head(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_upgrade_builds_exactly_the_models(fresh_engine):
    upgrade_to_head(fresh_engine)
    assert _diff(fresh_engine) == []
    assert _head(fresh_engine) == "0002_sprints_2_4"


def test_downgrade_to_base_and_back(fresh_engine):
    upgrade_to_head(fresh_engine)
    cfg = alembic_config()
    with fresh_engine.connect() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")
        conn.commit()
        assert set(inspect(conn).get_table_names()) == {"alembic_version"}
    upgrade_to_head(fresh_engine)
    assert _diff(fresh_engine) == []


def test_legacy_create_all_database_is_stamped_then_upgraded(fresh_engine):
    # Sprint 1 dev databases were made by create_all(): the baseline tables, no alembic_version.
    cfg = alembic_config()
    with fresh_engine.connect() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, BASELINE_REVISION)
        conn.execute(text("DROP TABLE alembic_version"))
        conn.execute(text("INSERT INTO users (id, display_name) VALUES ('old', 'Old user')"))
        conn.commit()
    upgrade_to_head(fresh_engine)
    assert _head(fresh_engine) == "0002_sprints_2_4"
    assert _diff(fresh_engine) == []
    with fresh_engine.connect() as conn:
        assert (
            conn.execute(text("SELECT display_name FROM users WHERE id = 'old'")).scalar_one() == "Old user"
        )


def test_sql_server_ddl_renders_offline(monkeypatch):
    """`alembic upgrade head --sql` for SQL Server, without a server (no driver needed)."""
    monkeypatch.setenv(
        "MIGRATION_DATABASE_URL", "mssql+pyodbc://u:p@offline/kasa?driver=ODBC+Driver+18+for+SQL+Server"
    )
    buffer = io.StringIO()
    cfg = alembic_config()
    cfg.output_buffer = buffer
    command.upgrade(cfg, "head", sql=True)
    sql = buffer.getvalue()
    assert "CREATE SECURITY POLICY security.kasa_policy" in sql
    for table in (
        "budgets",
        "subscriptions",
        "inbox_items",
        "settlements",
        "reminders",
        "google_accounts",
        "expense_item_assignees",
    ):
        assert f"ON dbo.{table}" in sql, table
    assert "ON dbo.fx_rates" not in sql  # shared reference data, no RLS
    assert "WHERE external_ref IS NOT NULL" in sql  # filtered unique index for import dedupe
    assert "expense_date DATE NOT NULL" in sql and "parsed_json NVARCHAR(max)" in sql
    assert BASELINE_REVISION in sql
