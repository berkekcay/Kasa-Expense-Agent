"""Sprint 1 baseline: users, houses, house_members, expenses, expense_items, expense_shares.

On SQL Server it also creates the row-level security policy that used to live in
sql/mssql/002_row_level_security.sql. The app sets the acting user on every transaction
(app/db/session.py):
    EXEC sp_set_session_context @key = N'user_id', @value = <uid>;
and the policy filters/blocks rows server-side, so a bug in a query (or a report-agent
SELECT) still cannot read another user's data. With no session context, every row is hidden.

Visibility rules
  expenses              : I paid it, or it belongs to a house I'm a member of
  expense_items/_shares : the parent expense is visible to me
  houses                : I created it or I'm a member
  house_members         : rows of houses I'm a member of (incl. my own row)
  users                 : no policy (display names only, needed to add flatmates)

The app must connect as a low-privilege login (db_datareader + db_datawriter, not db_owner);
run migrations with an admin login (MIGRATION_DATABASE_URL).

Revision ID: 0001_sprint1_baseline
Revises:
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_sprint1_baseline"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ID = sa.Unicode(128)

# One statement per op.execute: CREATE FUNCTION / SECURITY POLICY must start a batch.
RLS_FUNCTIONS = [
    "IF SCHEMA_ID(N'security') IS NULL EXEC (N'CREATE SCHEMA security')",
    """CREATE OR ALTER FUNCTION security.fn_is_house_member(@house_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    FROM dbo.house_members AS m
    WHERE m.house_id = @house_id
      AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))""",
    """CREATE OR ALTER FUNCTION security.fn_expense_access(@owner_id NVARCHAR(128), @house_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE @owner_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
       OR (@house_id IS NOT NULL AND EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))))""",
    """CREATE OR ALTER FUNCTION security.fn_expense_child_access(@expense_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    FROM dbo.expenses AS e
    WHERE e.id = @expense_id
      AND (e.owner_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           OR (e.house_id IS NOT NULL AND EXISTS (
                  SELECT 1 FROM dbo.house_members AS m
                  WHERE m.house_id = e.house_id
                    AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128)))))""",
    """CREATE OR ALTER FUNCTION security.fn_house_access(@house_id INT, @created_by NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE @created_by = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
       OR EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128)))""",
    # A membership row may be written by an existing member adding someone else, or by the
    # house creator adding themselves right after creating it. (AFTER INSERT predicates see
    # the new row, so a self-insert must not count as "already a member".)
    """CREATE OR ALTER FUNCTION security.fn_member_write(@house_id INT, @user_id NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE (@user_id <> CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           AND EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))))
       OR (@user_id = CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))
           AND EXISTS (SELECT 1 FROM dbo.houses AS h
                       WHERE h.id = @house_id AND h.created_by = @user_id))""",
]

RLS_POLICY = """CREATE SECURITY POLICY security.kasa_policy
    ADD FILTER PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses,
    ADD BLOCK  PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_access(owner_id, house_id) ON dbo.expenses AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_items AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_expense_child_access(expense_id) ON dbo.expense_shares AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_house_access(id, created_by) ON dbo.houses,
    ADD BLOCK  PREDICATE security.fn_house_access(id, created_by) ON dbo.houses AFTER INSERT,
    ADD BLOCK  PREDICATE security.fn_house_access(id, created_by) ON dbo.houses AFTER UPDATE,

    ADD FILTER PREDICATE security.fn_is_house_member(house_id) ON dbo.house_members,
    ADD BLOCK  PREDICATE security.fn_member_write(house_id, user_id) ON dbo.house_members AFTER INSERT
WITH (STATE = ON, SCHEMABINDING = ON)"""

DROP_POLICY = (
    "IF OBJECT_ID(N'security.kasa_policy', N'SP') IS NOT NULL DROP SECURITY POLICY security.kasa_policy"
)
DROP_FUNCTIONS = [
    f"DROP FUNCTION IF EXISTS security.{name}"
    for name in (
        "fn_member_write",
        "fn_house_access",
        "fn_expense_child_access",
        "fn_expense_access",
        "fn_is_house_member",
    )
]


def _is_mssql() -> bool:
    # get_context() works online and in offline (--sql) mode, unlike get_bind().
    return op.get_context().dialect.name == "mssql"


def _now() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", USER_ID, nullable=False),
        sa.Column("display_name", sa.Unicode(100), nullable=False),
        sa.Column("email", sa.Unicode(320), nullable=True),
        _now(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_table(
        "houses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Unicode(100), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("created_by", USER_ID, nullable=False),
        _now(),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_houses_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_houses"),
    )
    op.create_table(
        "house_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"], name="fk_house_members_house_id_houses"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_house_members_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_house_members"),
        sa.UniqueConstraint("house_id", "user_id", name="uq_house_member"),
    )
    op.create_index("ix_house_members_house_id", "house_members", ["house_id"])
    op.create_index("ix_house_members_user_id", "house_members", ["user_id"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", USER_ID, nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=True),
        sa.Column("merchant", sa.Unicode(200), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
        sa.Column("note", sa.Unicode(500), nullable=True),
        _now(),
        sa.CheckConstraint("total_minor > 0", name=op.f("ck_expenses_total_positive")),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_expenses_owner_id_users"),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"], name="fk_expenses_house_id_houses"),
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
    )
    op.create_index("ix_expenses_owner_id", "expenses", ["owner_id"])
    op.create_index("ix_expenses_house_id", "expenses", ["house_id"])

    op.create_table(
        "expense_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Unicode(200), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), server_default=sa.text("1"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name="fk_expense_items_expense_id_expenses", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_expense_items"),
    )
    op.create_index("ix_expense_items_expense_id", "expense_items", ["expense_id"])

    op.create_table(
        "expense_shares",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("amount_minor >= 0", name=op.f("ck_expense_shares_nonneg")),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name="fk_expense_shares_expense_id_expenses", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_expense_shares_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_expense_shares"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_share"),
    )
    op.create_index("ix_expense_shares_expense_id", "expense_shares", ["expense_id"])
    op.create_index("ix_expense_shares_user_id", "expense_shares", ["user_id"])

    if _is_mssql():
        for statement in RLS_FUNCTIONS:
            op.execute(statement)
        op.execute(RLS_POLICY)


def downgrade() -> None:
    if _is_mssql():
        op.execute(DROP_POLICY)
        for statement in DROP_FUNCTIONS:
            op.execute(statement)
    op.drop_table("expense_shares")
    op.drop_table("expense_items")
    op.drop_table("expenses")
    op.drop_table("house_members")
    op.drop_table("houses")
    op.drop_table("users")
