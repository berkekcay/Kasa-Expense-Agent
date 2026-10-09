"""SQLAlchemy 2.x ORM models.

Money is always stored as integer minor units (kuruş / cents) in BIGINT columns,
never as floats. The MSSQL DDL in `sql/mssql/001_schema.sql` mirrors these tables.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# User ids are opaque strings so Firebase Auth UIDs drop in later without a migration.
UserId = String(128)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UserId, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())


class House(Base):
    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="TRY")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    members: Mapped[list[HouseMember]] = relationship(back_populates="house", order_by="HouseMember.id")


class HouseMember(Base):
    __tablename__ = "house_members"
    __table_args__ = (UniqueConstraint("house_id", "user_id", name="uq_house_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    house_id: Mapped[int] = mapped_column(ForeignKey("houses.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    joined_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

    house: Mapped[House] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class Expense(Base):
    """One purchase. `owner_id` is the user who paid; `house_id` set means it is shared."""

    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    house_id: Mapped[int | None] = mapped_column(ForeignKey("houses.id"), index=True)
    merchant: Mapped[str] = mapped_column(String(200))
    expense_date: Mapped[dt.date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="TRY")
    total_minor: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | receipt
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.current_timestamp())

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
    description: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), default=Decimal(1))
    amount_minor: Mapped[int] = mapped_column(BigInteger)

    expense: Mapped[Expense] = relationship(back_populates="items")


class ExpenseShare(Base):
    """How much of a house expense each member owes (shares always sum to the total)."""

    __tablename__ = "expense_shares"
    __table_args__ = (UniqueConstraint("expense_id", "user_id", name="uq_expense_share"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)

    expense: Mapped[Expense] = relationship(back_populates="shares")
