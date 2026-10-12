"""Expense data layer shared by the REST API and the agents' tools.

Every function takes the acting `user_id` and only touches that user's rows.

How every expense gets created (receipt, manual, house, email, statement):

    expense = build_expense(user_id, data, source=...)        # validate, exact minor units
    warnings = finalize_expense(db, expense)                  # MONEY hook: FX + budgets
    ... set house_id / shares here for house expenses (after finalize, on the base amount)
    db.add(expense); db.commit()

`add_expense()` does all of that for personal expenses and returns the warnings too.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import EXPENSE_SOURCES, Expense, ExpenseItem, User
from app.services import clock
from app.services.categories import CATEGORIES, normalize_category
from app.services.errors import Conflict, InvalidInput, NotFound
from app.services.money import MoneyError, normalize_currency, to_minor

# Items (with their per-item assignees) and shares are always loaded with an expense.
_LOAD_CHILDREN = (
    selectinload(Expense.items).selectinload(ExpenseItem.assignees),
    selectinload(Expense.shares),
)


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


@dataclass
class SavedExpense:
    expense: Expense
    warnings: list[str] = field(default_factory=list)


def ensure_user(db: Session, user_id: str, display_name: str | None = None, email: str | None = None) -> User:
    """Return the user row, creating it on first sight (dev auth / Firebase first login).

    With Firebase, the token's name and email are passed in and kept up to date.
    """
    user = db.get(User, user_id)
    if user is None:
        user = User(id=user_id, display_name=(display_name or user_id)[:100], email=email)
        db.add(user)
        db.flush()
        return user
    if email and user.email != email:
        user.email = email
    if display_name and user.display_name == user.id:  # never overwrite a name set by a person
        user.display_name = display_name[:100]
    return user


def build_expense(
    user_id: str, data: ExpenseInput, *, source: str = "manual", external_ref: str | None = None
) -> Expense:
    """Validate input and build (but do not add) an Expense with exact minor-unit amounts.

    The category is normalised to the fixed list in `services.categories`.
    """
    merchant = data.merchant.strip()
    if not merchant:
        raise InvalidInput("merchant is required")
    if source not in EXPENSE_SOURCES:
        raise InvalidInput(f"unknown source {source!r}")
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
        expense_date=data.expense_date or clock.today(),
        currency=currency,
        total_minor=total_minor,
        category=normalize_category(data.category),
        note=data.note,
        source=source,
        external_ref=external_ref,
        items=items,
    )


def finalize_expense(
    db: Session, expense: Expense, *, base_currency: str | None = None, check_budgets: bool = True
) -> list[str]:
    """MONEY hook. Call on every new Expense after `build_expense()` and before shares are
    computed or anything is committed. Returns human-readable warnings for the user.

    1. `fx.apply_base_currency`: if `expense.currency` is not the base currency (the house's
       currency for house expenses, else settings.base_currency), converts `total_minor` and
       item amounts with the TCMB rate for `expense_date` and keeps the original amount in
       `original_currency` / `original_total_minor` / `fx_rate` / `fx_date`.
    2. `budgets.warnings_for_new_expense`: budget alerts that this expense would trigger (the
       expense is not in the DB yet; the budget check counts it itself).

    House expenses pass `check_budgets=False` and call `budgets.warnings_for_new_expense`
    themselves once the shares are set, so the payer's alert counts only their own share.
    """
    from app.config import get_settings
    from app.services import budgets, fx  # imported late: both import this module

    base = normalize_currency(base_currency or get_settings().base_currency)
    warnings = fx.apply_base_currency(db, expense, base)
    if check_budgets:
        warnings += budgets.warnings_for_new_expense(db, expense)
    return warnings


def find_by_external_ref(db: Session, user_id: str, source: str, external_ref: str) -> Expense | None:
    return db.scalars(
        select(Expense).where(
            Expense.owner_id == user_id, Expense.source == source, Expense.external_ref == external_ref
        )
    ).first()


def add_expense(
    db: Session,
    user_id: str,
    data: ExpenseInput,
    *,
    source: str = "manual",
    external_ref: str | None = None,
) -> SavedExpense:
    """Create a personal expense through the full pipeline (validate, FX, budgets, save).

    Raises Conflict if `external_ref` was already imported for this user and source.
    """
    ensure_user(db, user_id)
    if external_ref and find_by_external_ref(db, user_id, source, external_ref):
        raise Conflict(f"already imported ({source} {external_ref})")
    expense = build_expense(user_id, data, source=source, external_ref=external_ref)
    warnings = finalize_expense(db, expense)
    db.add(expense)
    db.commit()
    return SavedExpense(get_expense(db, user_id, expense.id), warnings)


def create_expense(db: Session, user_id: str, data: ExpenseInput, *, source: str = "manual") -> Expense:
    """Sprint 1 helper kept for callers that do not need the warnings."""
    return add_expense(db, user_id, data, source=source).expense


EXPENSE_SCOPES = ("all", "personal", "house")
MAX_PAGE = 500
UNCATEGORISED = "none"  # `category` filter value for expenses without a category


@dataclass
class ExpenseFilters:
    """Filters for `list_expenses`. Every field is optional; the default is all of the
    user's own expenses (personal ones and house bills they paid), newest first."""

    month: str | None = None  # "YYYY-MM"
    category: str | None = None  # one of CATEGORIES, or "none" for uncategorised
    source: str | None = None  # one of EXPENSE_SOURCES
    scope: str = "all"  # all | personal (house_id IS NULL) | house (house bills I paid)


def _month_range(month: str) -> tuple[dt.date, dt.date]:
    """ "YYYY-MM" -> [first day, first day of the next month)."""
    try:
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            raise ValueError
        year, mon = int(month[:4]), int(month[5:])
        start = dt.date(year, mon, 1)
    except ValueError:
        raise InvalidInput("month must look like YYYY-MM") from None
    end = dt.date(year + 1, 1, 1) if mon == 12 else dt.date(year, mon + 1, 1)
    return start, end


def _filtered(user_id: str, filters: ExpenseFilters):
    if filters.scope not in EXPENSE_SCOPES:
        raise InvalidInput(f"scope must be one of {', '.join(EXPENSE_SCOPES)}")
    conditions = [Expense.owner_id == user_id]
    if filters.scope == "personal":
        conditions.append(Expense.house_id.is_(None))
    elif filters.scope == "house":
        conditions.append(Expense.house_id.is_not(None))
    if filters.month:
        start, end = _month_range(filters.month)
        conditions += [Expense.expense_date >= start, Expense.expense_date < end]
    if filters.category:
        if filters.category == UNCATEGORISED:
            conditions.append(Expense.category.is_(None))
        elif filters.category in CATEGORIES:
            conditions.append(Expense.category == filters.category)
        else:
            raise InvalidInput(f"unknown category {filters.category!r}")
    if filters.source:
        if filters.source not in EXPENSE_SOURCES:
            raise InvalidInput(f"source must be one of {', '.join(EXPENSE_SOURCES)}")
        conditions.append(Expense.source == filters.source)
    return conditions


def list_expenses(
    db: Session,
    user_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
    filters: ExpenseFilters | None = None,
) -> list[Expense]:
    """The user's own expenses, newest first, filtered and paged."""
    stmt = (
        select(Expense)
        .where(*_filtered(user_id, filters or ExpenseFilters()))
        .options(*_LOAD_CHILDREN)
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, MAX_PAGE)))
    )
    return list(db.scalars(stmt))


def count_expenses(db: Session, user_id: str, filters: ExpenseFilters | None = None) -> int:
    """How many expenses match the filters (for paging, ignores limit/offset)."""
    stmt = select(func.count()).select_from(Expense).where(*_filtered(user_id, filters or ExpenseFilters()))
    return int(db.scalar(stmt) or 0)


def get_expense(db: Session, user_id: str, expense_id: int) -> Expense:
    stmt = (
        select(Expense).where(Expense.id == expense_id, Expense.owner_id == user_id).options(*_LOAD_CHILDREN)
    )
    expense = db.scalars(stmt).first()
    if expense is None:
        raise NotFound(f"expense {expense_id} not found")
    return expense


def items_sum_minor(expense: Expense) -> int:
    return sum(i.amount_minor for i in expense.items)


@dataclass
class ExpenseChanges:
    """Fields `update_expense` may change. Only the names in `fields` are applied, so a
    field can be cleared (note=None) without touching the others. Amounts never change:
    to fix an amount, delete the expense and add it again."""

    fields: set[str]
    merchant: str | None = None
    category: str | None = None
    expense_date: dt.date | None = None
    note: str | None = None


EDITABLE_FIELDS = ("merchant", "category", "expense_date", "note")


def update_expense(db: Session, user_id: str, expense_id: int, changes: ExpenseChanges) -> Expense:
    """Change merchant, category, date or note of one of the user's own expenses (the payer's,
    for a house bill). Others' expenses are NotFound."""
    unknown = changes.fields - set(EDITABLE_FIELDS)
    if unknown:
        raise InvalidInput(f"cannot change {', '.join(sorted(unknown))}; only {', '.join(EDITABLE_FIELDS)}")
    expense = get_expense(db, user_id, expense_id)
    if "merchant" in changes.fields:
        merchant = (changes.merchant or "").strip()
        if not merchant:
            raise InvalidInput("merchant is required")
        expense.merchant = merchant[:200]
    if "category" in changes.fields:
        expense.category = normalize_category(changes.category)
    if "expense_date" in changes.fields:
        if changes.expense_date is None:
            raise InvalidInput("expense_date cannot be empty")
        expense.expense_date = changes.expense_date
    if "note" in changes.fields:
        note = (changes.note or "").strip()
        expense.note = note[:500] or None
    db.commit()
    return get_expense(db, user_id, expense_id)


def delete_expense(db: Session, user_id: str, expense_id: int) -> None:
    """Delete one of the user's own personal expenses with its receipt lines.

    House bills are refused (Conflict): they change everyone's balance, so they are deleted
    through `houses.delete_house_expense` (DELETE /houses/{house_id}/expenses/{id}).
    """
    expense = get_expense(db, user_id, expense_id)
    if expense.house_id is not None:
        raise Conflict(
            f"expense {expense_id} is a house expense; delete it with "
            f"DELETE /houses/{expense.house_id}/expenses/{expense_id}"
        )
    db.delete(expense)
    db.commit()
