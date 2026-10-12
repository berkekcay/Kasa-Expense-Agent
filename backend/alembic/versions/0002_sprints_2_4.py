"""Sprints 2-4 data model: splits, settlements, budgets, FX, inbox, Google, subscriptions, reminders.

Adds to expenses: split_type, original_currency, original_total_minor, fx_rate, fx_date,
external_ref (filtered unique per owner + source) and subscription_id.

On SQL Server the RLS policy is dropped first and recreated at the end so it covers every
user-owned table:
  expense_item_assignees : the parent item's expense is visible to me
  settlements, reminders : I'm a member of the house
  budgets, subscriptions,
  inbox_items            : my own rows
  google_accounts        : my own row, or a background job session (SESSION_CONTEXT
                           'kasa_system' = 1) that maps a Gmail push to its user
  fx_rates               : shared reference data, no policy

Revision ID: 0002_sprints_2_4
Revises: 0001_sprint1_baseline
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_sprints_2_4"
down_revision: str | Sequence[str] | None = "0001_sprint1_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ID = sa.Unicode(128)
_ME = "CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))"

DROP_POLICY = (
    "IF OBJECT_ID(N'security.kasa_policy', N'SP') IS NOT NULL DROP SECURITY POLICY security.kasa_policy"
)

NEW_FUNCTIONS = [
    f"""CREATE OR ALTER FUNCTION security.fn_owner_access(@user_id NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok WHERE @user_id = {_ME}""",
    f"""CREATE OR ALTER FUNCTION security.fn_owner_or_system(@user_id NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE @user_id = {_ME}
       OR CAST(SESSION_CONTEXT(N'kasa_system') AS INT) = 1""",
    f"""CREATE OR ALTER FUNCTION security.fn_item_child_access(@item_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    FROM dbo.expense_items AS i
    JOIN dbo.expenses AS e ON e.id = i.expense_id
    WHERE i.id = @item_id
      AND (e.owner_id = {_ME}
           OR (e.house_id IS NOT NULL AND EXISTS (
                  SELECT 1 FROM dbo.house_members AS m
                  WHERE m.house_id = e.house_id AND m.user_id = {_ME})))""",
]
NEW_FUNCTION_NAMES = ("fn_item_child_access", "fn_owner_or_system", "fn_owner_access")


def _predicates(fn: str, table: str, *, update: bool = True) -> str:
    lines = [
        f"ADD FILTER PREDICATE {fn} ON dbo.{table}",
        f"ADD BLOCK  PREDICATE {fn} ON dbo.{table} AFTER INSERT",
    ]
    if update:
        lines.append(f"ADD BLOCK  PREDICATE {fn} ON dbo.{table} AFTER UPDATE")
    return ",\n    ".join(lines)


SPRINT1_PREDICATES = [
    _predicates("security.fn_expense_access(owner_id, house_id)", "expenses"),
    _predicates("security.fn_expense_child_access(expense_id)", "expense_items"),
    _predicates("security.fn_expense_child_access(expense_id)", "expense_shares"),
    _predicates("security.fn_house_access(id, created_by)", "houses"),
    (
        "ADD FILTER PREDICATE security.fn_is_house_member(house_id) ON dbo.house_members,\n    "
        "ADD BLOCK  PREDICATE security.fn_member_write(house_id, user_id) ON dbo.house_members AFTER INSERT"
    ),
]
NEW_PREDICATES = [
    _predicates("security.fn_item_child_access(item_id)", "expense_item_assignees"),
    _predicates("security.fn_is_house_member(house_id)", "settlements"),
    _predicates("security.fn_is_house_member(house_id)", "reminders"),
    _predicates("security.fn_owner_access(user_id)", "budgets"),
    _predicates("security.fn_owner_access(user_id)", "subscriptions"),
    _predicates("security.fn_owner_access(user_id)", "inbox_items"),
    _predicates("security.fn_owner_or_system(user_id)", "google_accounts"),
]


def _policy(predicates: list[str]) -> str:
    body = ",\n\n    ".join(predicates)
    return f"CREATE SECURITY POLICY security.kasa_policy\n    {body}\nWITH (STATE = ON, SCHEMABINDING = ON)"


def _is_mssql() -> bool:
    return op.get_context().dialect.name == "mssql"


def _now(name: str = "created_at") -> sa.Column:
    return sa.Column(name, sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False)


def upgrade() -> None:
    if _is_mssql():
        op.execute(DROP_POLICY)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("merchant_key", sa.Unicode(200), nullable=False),
        sa.Column("display_name", sa.Unicode(200), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("last_charge_date", sa.Date(), nullable=False),
        sa.Column("next_expected_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        _now("detected_at"),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_subscriptions_amount_positive")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_subscriptions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
        sa.UniqueConstraint("user_id", "merchant_key", name="uq_subscriptions_user_merchant"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])

    with op.batch_alter_table("expenses") as batch:
        batch.add_column(sa.Column("split_type", sa.String(10), nullable=True))
        batch.add_column(sa.Column("original_currency", sa.String(3), nullable=True))
        batch.add_column(sa.Column("original_total_minor", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("fx_rate", sa.Numeric(18, 6), nullable=True))
        batch.add_column(sa.Column("fx_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("external_ref", sa.Unicode(200), nullable=True))
        batch.add_column(sa.Column("subscription_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_expenses_subscription_id_subscriptions",
            "subscriptions",
            ["subscription_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_expenses_subscription_id", "expenses", ["subscription_id"])
    op.create_index(
        "uq_expenses_owner_source_ref",
        "expenses",
        ["owner_id", "source", "external_ref"],
        unique=True,
        sqlite_where=sa.text("external_ref IS NOT NULL"),
        mssql_where=sa.text("external_ref IS NOT NULL"),
    )

    op.create_table(
        "expense_item_assignees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["expense_items.id"],
            name="fk_expense_item_assignees_item_id_expense_items",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_expense_item_assignees_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_expense_item_assignees"),
        sa.UniqueConstraint("item_id", "user_id", name="uq_expense_item_assignee"),
    )
    op.create_index("ix_expense_item_assignees_item_id", "expense_item_assignees", ["item_id"])
    op.create_index("ix_expense_item_assignees_user_id", "expense_item_assignees", ["user_id"])

    op.create_table(
        "settlements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("from_user", USER_ID, nullable=False),
        sa.Column("to_user", USER_ID, nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("note", sa.Unicode(500), nullable=True),
        sa.Column("created_by", USER_ID, nullable=False),
        _now(),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_settlements_amount_positive")),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"], name="fk_settlements_house_id_houses"),
        sa.ForeignKeyConstraint(["from_user"], ["users.id"], name="fk_settlements_from_user_users"),
        sa.ForeignKeyConstraint(["to_user"], ["users.id"], name="fk_settlements_to_user_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_settlements_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_settlements"),
    )
    op.create_index("ix_settlements_house_id", "settlements", ["house_id"])

    op.create_table(
        "budgets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("limit_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("alert_threshold_pct", sa.Integer(), server_default=sa.text("80"), nullable=False),
        _now(),
        sa.CheckConstraint("limit_minor > 0", name=op.f("ck_budgets_limit_positive")),
        sa.CheckConstraint("alert_threshold_pct BETWEEN 1 AND 100", name=op.f("ck_budgets_threshold_range")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_budgets_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_budgets"),
        sa.UniqueConstraint("user_id", "category", name="uq_budgets_user_category"),
    )
    op.create_index("ix_budgets_user_id", "budgets", ["user_id"])
    op.create_index(
        "uq_budgets_user_overall",
        "budgets",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("category IS NULL"),
        mssql_where=sa.text("category IS NULL"),
    )

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("try_per_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("source", sa.String(20), server_default="TCMB", nullable=False),
        _now("fetched_at"),
        sa.PrimaryKeyConstraint("id", name="pk_fx_rates"),
        sa.UniqueConstraint("rate_date", "currency", name="uq_fx_rates_date_currency"),
    )

    op.create_table(
        "inbox_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("external_ref", sa.Unicode(200), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("title", sa.Unicode(300), nullable=False),
        sa.Column("sender", sa.Unicode(320), nullable=True),
        sa.Column("excerpt", sa.Unicode(2000), nullable=True),
        sa.Column("parsed_json", sa.UnicodeText(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("expense_id", sa.Integer(), nullable=True),
        sa.Column("error", sa.Unicode(500), nullable=True),
        _now(),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_inbox_items_user_id_users"),
        sa.ForeignKeyConstraint(
            ["expense_id"], ["expenses.id"], name="fk_inbox_items_expense_id_expenses", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inbox_items"),
        sa.UniqueConstraint("user_id", "source", "external_ref", name="uq_inbox_items_ref"),
    )
    op.create_index("ix_inbox_items_user_id", "inbox_items", ["user_id"])

    op.create_table(
        "google_accounts",
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("google_email", sa.Unicode(320), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("scopes", sa.String(1000), nullable=False),
        sa.Column("gmail_history_id", sa.String(40), nullable=True),
        sa.Column("gmail_watch_expires_at", sa.DateTime(), nullable=True),
        _now(),
        _now("updated_at"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_google_accounts_user_id_users"),
        sa.PrimaryKeyConstraint("user_id", name="pk_google_accounts"),
    )
    op.create_index("ix_google_accounts_google_email", "google_accounts", ["google_email"])

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("from_user", USER_ID, nullable=False),
        sa.Column("to_user", USER_ID, nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="TRY", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("calendar_event_id", sa.String(200), nullable=True),
        sa.Column("created_by", USER_ID, nullable=False),
        sa.Column("status", sa.String(20), server_default="scheduled", nullable=False),
        _now(),
        sa.CheckConstraint("amount_minor > 0", name=op.f("ck_reminders_amount_positive")),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"], name="fk_reminders_house_id_houses"),
        sa.ForeignKeyConstraint(["from_user"], ["users.id"], name="fk_reminders_from_user_users"),
        sa.ForeignKeyConstraint(["to_user"], ["users.id"], name="fk_reminders_to_user_users"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_reminders_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_reminders"),
    )
    op.create_index("ix_reminders_house_id", "reminders", ["house_id"])

    if _is_mssql():
        for statement in NEW_FUNCTIONS:
            op.execute(statement)
        op.execute(_policy(SPRINT1_PREDICATES + NEW_PREDICATES))


def downgrade() -> None:
    if _is_mssql():
        op.execute(DROP_POLICY)
        for name in NEW_FUNCTION_NAMES:
            op.execute(f"DROP FUNCTION IF EXISTS security.{name}")

    op.drop_table("reminders")
    op.drop_table("google_accounts")
    op.drop_table("inbox_items")
    op.drop_table("fx_rates")
    op.drop_table("budgets")
    op.drop_table("settlements")
    op.drop_table("expense_item_assignees")
    op.drop_index("uq_expenses_owner_source_ref", table_name="expenses")
    op.drop_index("ix_expenses_subscription_id", table_name="expenses")
    with op.batch_alter_table("expenses") as batch:
        batch.drop_constraint("fk_expenses_subscription_id_subscriptions", type_="foreignkey")
        for column in (
            "subscription_id",
            "external_ref",
            "fx_date",
            "fx_rate",
            "original_total_minor",
            "original_currency",
            "split_type",
        ):
            batch.drop_column(column)
    op.drop_table("subscriptions")

    if _is_mssql():
        op.execute(_policy(SPRINT1_PREDICATES))
