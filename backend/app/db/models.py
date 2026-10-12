"""SQLAlchemy 2.x ORM models.

Money is always stored as integer minor units (kuruş / cents) in BIGINT columns,
never as floats. Alembic (`backend/alembic/`) is the only way the schema changes: every
edit here needs a new revision (`alembic revision --autogenerate -m "..."`), and
`tests/test_migrations.py` fails if the models and the migrations drift apart.

Text columns use `Unicode` so SQL Server stores them as NVARCHAR (Turkish letters survive
any collation); on SQLite it is plain VARCHAR.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    Unicode,
    UnicodeText,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# User ids are opaque strings so Firebase Auth UIDs drop in without a migration.
UserId = Unicode(128)

# Deterministic constraint names: Alembic needs them to drop/alter constraints later,
# and SQL Server would otherwise invent random ones.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Allowed values for the string "enum" columns (kept as plain strings in the DB).
EXPENSE_SOURCES = ("manual", "receipt", "statement", "email")
SPLIT_TYPES = ("equal", "percent", "exact", "items")
INBOX_SOURCES = ("email", "statement")
INBOX_STATUSES = ("pending", "approved", "rejected", "failed", "ignored")
SUBSCRIPTION_PERIODS = ("weekly", "monthly", "yearly")
SUBSCRIPTION_STATUSES = ("active", "dismissed")
REMINDER_STATUSES = ("scheduled", "done", "cancelled")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _now() -> Mapped[dt.datetime]:
    return mapped_column(DateTime, server_default=func.current_timestamp())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UserId, primary_key=True)
    display_name: Mapped[str] = mapped_column(Unicode(100))
    email: Mapped[str | None] = mapped_column(Unicode(320))
    created_at: Mapped[dt.datetime] = _now()


class House(Base):
    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Unicode(100))
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = _now()

    members: Mapped[list[HouseMember]] = relationship(back_populates="house", order_by="HouseMember.id")


class HouseMember(Base):
    __tablename__ = "house_members"
    __table_args__ = (UniqueConstraint("house_id", "user_id", name="uq_house_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    joined_at: Mapped[dt.datetime] = _now()

    house: Mapped[House] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Expense(Base):
    """One purchase. `owner_id` is the user who paid; `house_id` set means it is shared.

    `currency` / `total_minor` are always in the user's (or house's) base currency, TRY by
    default. When the purchase was in another currency, `fx.apply_base_currency` converts it
    and keeps the original in `original_currency` / `original_total_minor`, with the TCMB
    rate used (`fx_rate` = TRY per 1 unit of the original currency) and its date.
    """

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("total_minor > 0", name="total_positive"),
        # Dedupe for imports (email / statement): the same source line is saved once per
        # owner. Filtered so the many rows without an external_ref never collide (SQL Server
        # treats NULLs as equal in plain unique constraints).
        Index(
            "uq_expenses_owner_source_ref",
            "owner_id",
            "source",
            "external_ref",
            unique=True,
            sqlite_where=text("external_ref IS NOT NULL"),
            mssql_where=text("external_ref IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    merchant: Mapped[str] = mapped_column(Unicode(200))
    expense_date: Mapped[dt.date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    total_minor: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str | None] = mapped_column(String(50))  # always from services.categories
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    note: Mapped[str | None] = mapped_column(Unicode(500))
    created_at: Mapped[dt.datetime] = _now()

    # Sprint 2-4 columns (all nullable so Sprint 1 rows stay valid).
    split_type: Mapped[str | None] = mapped_column(String(10))  # SPLIT_TYPES; None = personal
    original_currency: Mapped[str | None] = mapped_column(String(3))
    original_total_minor: Mapped[int | None] = mapped_column(BigInteger)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # TRY per 1 original unit
    fx_date: Mapped[dt.date | None] = mapped_column(Date)
    external_ref: Mapped[str | None] = mapped_column(Unicode(200))  # Gmail id / statement line hash
    subscription_id: Mapped[int | None] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True
    )

    items: Mapped[list[ExpenseItem]] = relationship(
        back_populates="expense", cascade="all, delete-orphan", order_by="ExpenseItem.id"
    )
    shares: Mapped[list[ExpenseShare]] = relationship(
        back_populates="expense", cascade="all, delete-orphan", order_by="ExpenseShare.id"
    )


class ExpenseItem(Base):
    __tablename__ = "expense_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(Unicode(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal(1), server_default=text("1"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)

    expense: Mapped[Expense] = relationship(back_populates="items")
    assignees: Mapped[list[ExpenseItemAssignee]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ExpenseItemAssignee.id"
    )


class ExpenseItemAssignee(Base):
    """Who shares one line item, for `split_type == "items"` house expenses."""

    __tablename__ = "expense_item_assignees"
    __table_args__ = (UniqueConstraint("item_id", "user_id", name="uq_expense_item_assignee"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("expense_items.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)

    item: Mapped[ExpenseItem] = relationship(back_populates="assignees")


class ExpenseShare(Base):
    """How much of a house expense each member owes (shares always sum to the total)."""

    __tablename__ = "expense_shares"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_share"),
        CheckConstraint("amount_minor >= 0", name="nonneg"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)

    expense: Mapped[Expense] = relationship(back_populates="shares")


class Settlement(Base):
    """A recorded payment between flatmates (`from_user` paid `to_user`). Reduces debts."""

    __tablename__ = "settlements"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), index=True)
    from_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    to_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    note: Mapped[str | None] = mapped_column(Unicode(500))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = _now()


class Budget(Base):
    """Monthly spending limit. `category` None means the overall limit."""

    __tablename__ = "budgets"
    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_budgets_user_category"),
        # SQLite treats NULLs as distinct, so "one overall budget per user" needs its own index.
        Index(
            "uq_budgets_user_overall",
            "user_id",
            unique=True,
            sqlite_where=text("category IS NULL"),
            mssql_where=text("category IS NULL"),
        ),
        CheckConstraint("limit_minor > 0", name="limit_positive"),
        CheckConstraint("alert_threshold_pct BETWEEN 1 AND 100", name="threshold_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str | None] = mapped_column(String(50))
    limit_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, default=80, server_default=text("80"))
    created_at: Mapped[dt.datetime] = _now()


class FxRate(Base):
    """Daily TCMB rate: TRY per 1 unit of `currency`. Shared reference data (no owner)."""

    __tablename__ = "fx_rates"
    __table_args__ = (UniqueConstraint("rate_date", "currency", name="uq_fx_rates_date_currency"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rate_date: Mapped[dt.date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    try_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    source: Mapped[str] = mapped_column(String(20), default="TCMB", server_default="TCMB")
    fetched_at: Mapped[dt.datetime] = _now()


class InboxItem(Base):
    """A candidate expense found in Gmail or a bank statement, waiting for the user's decision.

    `parsed_json` holds the extracted fields as JSON: merchant, date, currency, total,
    category, items (see `services.inbox.ParsedExpense`).
    """

    __tablename__ = "inbox_items"
    __table_args__ = (UniqueConstraint("user_id", "source", "external_ref", name="uq_inbox_items_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(20))  # INBOX_SOURCES
    external_ref: Mapped[str] = mapped_column(Unicode(200))
    received_at: Mapped[dt.datetime] = mapped_column(DateTime)
    title: Mapped[str] = mapped_column(Unicode(300))  # email subject or statement line
    sender: Mapped[str | None] = mapped_column(Unicode(320))
    excerpt: Mapped[str | None] = mapped_column(Unicode(2000))
    parsed_json: Mapped[str | None] = mapped_column(UnicodeText)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    expense_id: Mapped[int | None] = mapped_column(ForeignKey("expenses.id", ondelete="SET NULL"))
    error: Mapped[str | None] = mapped_column(Unicode(500))
    created_at: Mapped[dt.datetime] = _now()
    decided_at: Mapped[dt.datetime | None] = mapped_column(DateTime)


class GoogleAccount(Base):
    """The user's connected Google account (Gmail read + Calendar events).

    The refresh token is stored encrypted with Fernet (`services.crypto`), never in plain text.
    """

    __tablename__ = "google_accounts"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    google_email: Mapped[str] = mapped_column(Unicode(320), index=True)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    scopes: Mapped[str] = mapped_column(String(1000))  # space-separated, as Google returns them
    gmail_history_id: Mapped[str | None] = mapped_column(String(40))
    gmail_watch_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = _now()
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )


class Subscription(Base):
    """A recurring charge detected from the user's expenses (Netflix, Spotify, gym...)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", name="uq_subscriptions_user_merchant"),
        CheckConstraint("amount_minor > 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    merchant_key: Mapped[str] = mapped_column(Unicode(200))  # normalised merchant name
    display_name: Mapped[str] = mapped_column(Unicode(200))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    period: Mapped[str] = mapped_column(String(10))  # SUBSCRIPTION_PERIODS
    last_charge_date: Mapped[dt.date] = mapped_column(Date)
    next_expected_date: Mapped[dt.date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    detected_at: Mapped[dt.datetime] = _now()


class Reminder(Base):
    """A settle-up reminder (optionally mirrored as a Google Calendar event)."""

    __tablename__ = "reminders"
    __table_args__ = (CheckConstraint("amount_minor > 0", name="amount_positive"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), index=True)
    from_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    to_user: Mapped[str] = mapped_column(ForeignKey("users.id"))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="TRY", server_default="TRY")
    due_date: Mapped[dt.date] = mapped_column(Date)
    calendar_event_id: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="scheduled", server_default="scheduled")
    created_at: Mapped[dt.datetime] = _now()
