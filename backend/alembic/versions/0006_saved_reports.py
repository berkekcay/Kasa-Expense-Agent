"""Saved reports: charts from the chat that can be run again on fresh data, owner-only.

Revision ID: 0006_saved_reports
Revises: 0005_accounts_and_invites
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_saved_reports"
down_revision: str | Sequence[str] | None = "0005_accounts_and_invites"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FN = "security.fn_owner_access(user_id)"


def _is_mssql() -> bool:
    return op.get_context().dialect.name == "mssql"


def upgrade() -> None:
    op.create_table(
        "saved_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Unicode(length=128), nullable=False),
        sa.Column("title", sa.Unicode(length=200), nullable=False),
        sa.Column("question", sa.Unicode(length=1000), nullable=True),
        sa.Column("sql", sa.UnicodeText(), nullable=False),
        sa.Column("chart_type", sa.String(length=10), nullable=False),
        sa.Column("x", sa.Unicode(length=100), nullable=True),
        sa.Column("y", sa.Unicode(length=100), nullable=True),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_saved_reports_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_saved_reports"),
    )
    op.create_index("ix_saved_reports_user_id", "saved_reports", ["user_id"])
    if _is_mssql():
        op.execute(
            "ALTER SECURITY POLICY security.kasa_policy\n    "
            f"ADD FILTER PREDICATE {FN} ON dbo.saved_reports,\n    "
            f"ADD BLOCK PREDICATE {FN} ON dbo.saved_reports AFTER INSERT,\n    "
            f"ADD BLOCK PREDICATE {FN} ON dbo.saved_reports AFTER UPDATE"
        )


def downgrade() -> None:
    if _is_mssql():
        op.execute(
            "ALTER SECURITY POLICY security.kasa_policy\n    "
            "DROP FILTER PREDICATE ON dbo.saved_reports,\n    "
            "DROP BLOCK PREDICATE ON dbo.saved_reports AFTER INSERT,\n    "
            "DROP BLOCK PREDICATE ON dbo.saved_reports AFTER UPDATE"
        )
    op.drop_index("ix_saved_reports_user_id", table_name="saved_reports")
    op.drop_table("saved_reports")
