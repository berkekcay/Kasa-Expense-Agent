"""Expense data layer shared by the REST API and the agents' tools.

Every function takes the acting `user_id` and only touches that user's rows.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Expense, ExpenseItem, User
from app.services.errors import InvalidInput, NotFound
from app.services.money import MoneyError, normalize_currency, to_minor


@dataclass
class ItemInput:
    description: str
    amount: Decimal | str
    quantity: Decimal | str = "1"


@dataclass
class ExpenseInput:
    merchant: str
    total: Decimal | str
    expense_date: dt.date | None = None
    currency: str | None = "TRY"
    category: str | None = None
    note: str | None = None
    items: list[ItemInput] = field(default_factory=list)


def ensure_user(db: Session, user_id: str, display_name: str | None = None) -> User:
    """Return the user row, creating it on first sight (dev auth / Firebase first login)."""
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, display_name=display_name or user_id)
        db.add(user)
        db.flush()
    return user


def build_expense(user_id: str, data: ExpenseInput, *, source: str = "manual") -> Expense:
    """Validate input and build (but do not add) an Expense with exact minor-unit amounts."""
    merchant = data.merchant.strip()
    if not merchant:
        raise InvalidInput("merchant is required")
    try:
        total_minor = to_minor(data.total)
        currency = normalize_currency(data.currency)
        items = [
            ExpenseItem(
                description=(i.description or "item").strip()[:200],
                quantity=Decimal(str(i.quantity or "1")),
                amount_minor=to_minor(i.amount),
            )
            for i in data.items
        ]
    except (MoneyError, ArithmeticError) as exc:
        raise InvalidInput(str(exc)) from exc
    if total_minor <= 0:
        raise InvalidInput("total must be positive")
    return Expense(
        owner_id=user_id,
        merchant=merchant[:200],
        expense_date=data.expense_date or dt.date.today(),
        currency=currency,
        total_minor=total_minor,
        category=data.category,
        note=data.note,
        source=source,
        items=items,
    )


def create_expense(db: Session, user_id: str, data: ExpenseInput, *, source: str = "manual") -> Expense:
    ensure_user(db, user_id)
    expense = build_expense(user_id, data, source=source)
    db.add(expense)
    db.commit()
    return get_expense(db, user_id, expense.id)


def list_expenses(db: Session, user_id: str, *, limit: int = 100) -> list[Expense]:
    stmt = (
        select(Expense)
        .where(Expense.owner_id == user_id)
        .options(selectinload(Expense.items), selectinload(Expense.shares))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_expense(db: Session, user_id: str, expense_id: int) -> Expense:
    stmt = (
        select(Expense)
        .where(Expense.id == expense_id, Expense.owner_id == user_id)
        .options(selectinload(Expense.items), selectinload(Expense.shares))
    )
    expense = db.scalars(stmt).first()
    if expense is None:
        raise NotFound(f"expense {expense_id} not found")
    return expense


def items_sum_minor(expense: Expense) -> int:
    return sum(i.amount_minor for i in expense.items)
