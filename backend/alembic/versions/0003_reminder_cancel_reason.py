"""Reminders remember why they were cancelled.

Adds reminders.cancel_reason (NULL, "user" or "outdated"). "outdated" means the balances
changed and creating reminders again replaced this one. A nullable column on an existing
table: no data change, and the SQL Server RLS policy (reminders: house members) already
covers it, so the policy is not touched. Adding or dropping a column that no predicate uses
is allowed under a schema-bound policy.

Revision ID: 0003_reminder_cancel_reason
Revises: 0002_sprints_2_4
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_reminder_cancel_reason"
down_revision: str | Sequence[str] | None = "0002_sprints_2_4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reminders", sa.Column("cancel_reason", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("cancel_reason")
