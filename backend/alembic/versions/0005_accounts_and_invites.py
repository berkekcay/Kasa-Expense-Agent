"""Accounts with mandatory 2FA, sign-in sessions, recovery codes and house invite links.

- users gets the login fields (email, scrypt password hash, Google subject, encrypted TOTP
  secret, lockout counters) with filtered unique indexes on login_email and google_sub.
- auth_sessions and recovery_codes are owner-only; the sign-in lookup runs before the user
  is known, so on SQL Server they use the owner-or-system predicate.
- house_invites are visible to the house's members and to the system session that checks
  a code for someone who is not a member yet.
- fn_member_write also lets the system session add a member: accepting an invite runs as
  system after the code was checked, because the person joining is not a member yet.
  A function that a schema-bound policy uses cannot be altered, so its predicate is dropped
  from the policy first and added back after.

Revision ID: 0005_accounts_and_invites
Revises: 0004_chat_history
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_accounts_and_invites"
down_revision: str | Sequence[str] | None = "0004_chat_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_ID = sa.Unicode(128)
_ME = "CAST(SESSION_CONTEXT(N'user_id') AS NVARCHAR(128))"
_SYSTEM = "CAST(SESSION_CONTEXT(N'kasa_system') AS INT) = 1"

MEMBER_WRITE = f"""CREATE OR ALTER FUNCTION security.fn_member_write(@house_id INT, @user_id NVARCHAR(128))
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE (@user_id <> {_ME}
           AND EXISTS (
              SELECT 1 FROM dbo.house_members AS m
              WHERE m.house_id = @house_id
                AND m.user_id = {_ME}))
       OR (@user_id = {_ME}
           AND EXISTS (SELECT 1 FROM dbo.houses AS h
                       WHERE h.id = @house_id AND h.created_by = @user_id))
       {{system}}"""

HOUSE_MEMBER_OR_SYSTEM = f"""CREATE OR ALTER FUNCTION security.fn_house_member_or_system(@house_id INT)
RETURNS TABLE
WITH SCHEMABINDING
AS RETURN
    SELECT 1 AS ok
    WHERE {_SYSTEM}
       OR EXISTS (SELECT 1 FROM dbo.house_members AS m
                  WHERE m.house_id = @house_id AND m.user_id = {_ME})"""

NEW_PREDICATES = [
    ("security.fn_owner_or_system(user_id)", "auth_sessions"),
    ("security.fn_owner_or_system(user_id)", "recovery_codes"),
    ("security.fn_house_member_or_system(house_id)", "house_invites"),
]
MEMBER_BLOCK = "BLOCK PREDICATE security.fn_member_write(house_id, user_id) ON dbo.house_members AFTER INSERT"


def _is_mssql() -> bool:
    return op.get_context().dialect.name == "mssql"


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False)


def _alter_policy(lines: list[str]) -> None:
    op.execute("ALTER SECURITY POLICY security.kasa_policy\n    " + ",\n    ".join(lines))


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("login_email", sa.Unicode(length=320), nullable=True))
        batch.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("google_sub", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("totp_secret_enc", sa.String(length=500), nullable=True))
        batch.add_column(sa.Column("totp_enabled_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("totp_last_step", sa.BigInteger(), nullable=True))
        batch.add_column(
            sa.Column("failed_logins", sa.Integer(), server_default=sa.text("0"), nullable=False)
        )
        batch.add_column(sa.Column("locked_until", sa.DateTime(), nullable=True))
    for column in ("login_email", "google_sub"):
        op.create_index(
            f"uq_users_{column}",
            "users",
            [column],
            unique=True,
            sqlite_where=sa.text(f"{column} IS NOT NULL"),
            mssql_where=sa.text(f"{column} IS NOT NULL"),
        )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.Unicode(length=300), nullable=True),
        _now("created_at"),
        _now("last_seen_at"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])

    op.create_table(
        "recovery_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", USER_ID, nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        _now("created_at"),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_recovery_codes_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_recovery_codes"),
    )
    op.create_index("ix_recovery_codes_user_id", "recovery_codes", ["user_id"])

    op.create_table(
        "house_invites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("house_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("house_name", sa.Unicode(length=100), nullable=False),
        sa.Column("created_by", USER_ID, nullable=False),
        _now("created_at"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("uses", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("max_uses > 0", name="ck_house_invites_max_uses_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_house_invites_created_by_users"),
        sa.ForeignKeyConstraint(["house_id"], ["houses.id"], name="fk_house_invites_house_id_houses"),
        sa.PrimaryKeyConstraint("id", name="pk_house_invites"),
        sa.UniqueConstraint("code", name="uq_house_invites_code"),
    )
    op.create_index("ix_house_invites_house_id", "house_invites", ["house_id"])

    if _is_mssql():
        op.execute(HOUSE_MEMBER_OR_SYSTEM)
        _alter_policy([f"DROP {MEMBER_BLOCK}"])
        op.execute(MEMBER_WRITE.format(system=f"OR {_SYSTEM}"))
        lines = [f"ADD {MEMBER_BLOCK}"]
        for fn, table in NEW_PREDICATES:
            lines += [
                f"ADD FILTER PREDICATE {fn} ON dbo.{table}",
                f"ADD BLOCK PREDICATE {fn} ON dbo.{table} AFTER INSERT",
                f"ADD BLOCK PREDICATE {fn} ON dbo.{table} AFTER UPDATE",
            ]
        _alter_policy(lines)


def downgrade() -> None:
    if _is_mssql():
        lines = [f"DROP {MEMBER_BLOCK}"]
        for _fn, table in NEW_PREDICATES:
            lines += [
                f"DROP FILTER PREDICATE ON dbo.{table}",
                f"DROP BLOCK PREDICATE ON dbo.{table} AFTER INSERT",
                f"DROP BLOCK PREDICATE ON dbo.{table} AFTER UPDATE",
            ]
        _alter_policy(lines)
        op.execute(MEMBER_WRITE.format(system=""))
        _alter_policy([f"ADD {MEMBER_BLOCK}"])
        op.execute("DROP FUNCTION IF EXISTS security.fn_house_member_or_system")

    op.drop_index("ix_house_invites_house_id", table_name="house_invites")
    op.drop_table("house_invites")
    op.drop_index("ix_recovery_codes_user_id", table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    for column in ("google_sub", "login_email"):
        op.drop_index(f"uq_users_{column}", table_name="users")
    with op.batch_alter_table("users") as batch:
        for column in (
            "locked_until",
            "failed_logins",
            "totp_last_step",
            "totp_enabled_at",
            "totp_secret_enc",
            "google_sub",
            "password_hash",
            "login_email",
        ):
            batch.drop_column(column)
