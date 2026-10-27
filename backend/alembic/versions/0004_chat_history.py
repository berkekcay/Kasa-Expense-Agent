"""Chat history: conversations and their messages, owner-only.

Two new user-owned tables. On SQL Server both join the existing security policy with the
owner predicate (`security.fn_owner_access`), added and dropped with ALTER SECURITY POLICY so
the other predicates are not touched.

Revision ID: 0004_chat_history
Revises: 0003_reminder_cancel_reason
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_chat_history"
down_revision: str | Sequence[str] | None = "0003_reminder_cancel_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ID = sa.Unicode(128)
TABLES = ("chat_conversations", "chat_messages")


def _is_mssql() -> bool:
    return op.get_context().dialect.name == "mssql"


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("title", sa.Unicode(length=200), nullable=False),
        sa.Column("adk_session_id", sa.String(length=64), nullable=True),
        _now("created_at"),
        _now("updated_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_conversations_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_chat_conversations"),
    )
    op.create_index("ix_chat_conversations_user_id", "chat_conversations", ["user_id"])
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=32), nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("text", sa.UnicodeText(), nullable=False),
        sa.Column("payload_json", sa.UnicodeText(), nullable=True),
        _now("created_at"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_conversations.id"],
            name="fk_chat_messages_conversation_id_chat_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_chat_messages_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])

    if _is_mssql():
        adds = []
        for table in TABLES:
            fn = "security.fn_owner_access(user_id)"
            adds += [
                f"ADD FILTER PREDICATE {fn} ON dbo.{table}",
                f"ADD BLOCK PREDICATE {fn} ON dbo.{table} AFTER INSERT",
                f"ADD BLOCK PREDICATE {fn} ON dbo.{table} AFTER UPDATE",
            ]
        op.execute("ALTER SECURITY POLICY security.kasa_policy\n    " + ",\n    ".join(adds))


def downgrade() -> None:
    if _is_mssql():
        drops = []
        for table in TABLES:
            drops += [
                f"DROP FILTER PREDICATE ON dbo.{table}",
                f"DROP BLOCK PREDICATE ON dbo.{table} AFTER INSERT",
                f"DROP BLOCK PREDICATE ON dbo.{table} AFTER UPDATE",
            ]
        op.execute("ALTER SECURITY POLICY security.kasa_policy\n    " + ",\n    ".join(drops))
    op.drop_index("ix_chat_messages_conversation_id", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_conversations_user_id", table_name="chat_conversations")
    op.drop_table("chat_conversations")
