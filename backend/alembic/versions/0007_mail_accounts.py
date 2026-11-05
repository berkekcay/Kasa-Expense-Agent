"""Mail accounts: a mailbox read over IMAP with an app password, owner-only.

Revision ID: 0007_mail_accounts
Revises: 0006_saved_reports
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_mail_accounts"
down_revision: str | Sequence[str] | None = "0006_saved_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FN = "security.fn_owner_access(user_id)"


def _is_mssql() -> bool:
    return op.get_context().dialect.name == "mssql"


def upgrade() -> None:
    op.create_table(
        "mail_accounts",
        sa.Column("user_id", sa.Unicode(length=128), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.Unicode(length=320), nullable=False),
        sa.Column("password_enc", sa.Text(), nullable=False),
        sa.Column("folder", sa.Unicode(length=200), nullable=False),
        sa.Column("uid_validity", sa.String(length=40), nullable=True),
        sa.Column("last_uid", sa.BigInteger(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Unicode(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_mail_accounts_user_id_users"),
        sa.PrimaryKeyConstraint("user_id", name="pk_mail_accounts"),
    )
    if _is_mssql():
        op.execute(
            "ALTER SECURITY POLICY security.kasa_policy\n    "
            f"ADD FILTER PREDICATE {FN} ON dbo.mail_accounts,\n    "
            f"ADD BLOCK PREDICATE {FN} ON dbo.mail_accounts AFTER INSERT,\n    "
            f"ADD BLOCK PREDICATE {FN} ON dbo.mail_accounts AFTER UPDATE"
        )


def downgrade() -> None:
    if _is_mssql():
        op.execute(
            "ALTER SECURITY POLICY security.kasa_policy\n    "
            "DROP FILTER PREDICATE ON dbo.mail_accounts,\n    "
            "DROP BLOCK PREDICATE ON dbo.mail_accounts AFTER INSERT,\n    "
            "DROP BLOCK PREDICATE ON dbo.mail_accounts AFTER UPDATE"
        )
    op.drop_table("mail_accounts")
