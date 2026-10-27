"""Monthly budgets and alerts (owner: track MONEY).

A budget is a monthly limit for one category, or overall when category is None. Budgets
are in the base currency (settings.base_currency, TRY).

What counts as "my spending" in a month (calendar month of `expense_date`):
- my personal expenses: `owner_id == me` and no house;
- my share of house expenses: my `expense_shares.amount_minor`, whoever paid. What I paid
  for flatmates is not my spending (they owe it back), so the payer's full total never
  counts for house expenses.
Rows in another currency (a house in EUR, or old rows saved before FX conversion existed)
are converted with the TCMB rate of their expense date; a row with no rate is skipped and
logged rather than failing the whole status.

Levels: "warning" from alert_threshold_pct percent of the limit, "exceeded" when spent is
above the limit (exactly the limit is still "warning"). pct_used is floored.

`warnings_for_new_expense` is the budget half of the pipeline hook
(`expenses.finalize_expense`). It runs before the expense is saved and, for house
expenses, before shares exist, so it counts the payer's full amount unless shares are
already set. It warns only when this expense moves a budget up a level (ok -> warning,
or to exceeded), so a user is not nagged on every purchase. It never raises.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Budget, Expense, ExpenseShare
from app.services import clock, fx
from app.services.categories import CATEGORIES, fold_text, is_known_category, normalize_category
from app.services.errors import DomainError, InvalidInput, NotFound
from app.services.expenses import ensure_user
from app.services.money import MoneyError, to_minor

log = logging.getLogger(__name__)

Level = Literal["ok", "warning", "exceeded"]
_LEVEL_RANK = {"ok": 0, "warning": 1, "exceeded": 2}
OVERALL_WORDS = {"", "overall", "total", "all", "genel", "toplam", "tum", "tumu", "hepsi", "butun"}


@dataclass
class BudgetStatus:
    budget: Budget
    month: dt.date  # first day of the month
    spent_minor: int
    remaining_minor: int  # may be negative
    pct_used: int  # floor(spent * 100 / limit)
    level: Level  # warning at >= alert_threshold_pct


# --- months -------------------------------------------------------------------------------


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def add_months(first_of_month: dt.date, months: int) -> dt.date:
    index = first_of_month.year * 12 + first_of_month.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


def base_currency() -> str:
    return fx.currency_code(get_settings().base_currency)


# --- spending -----------------------------------------------------------------------------


@dataclass
class SpendingRow:
    """My spending at one merchant on one day in one category, in the target currency."""

    day: dt.date
    merchant: str
    category: str | None
    amount_minor: int
    count: int  # expenses in this group


def spending_rows(
    db: Session, user_id: str, start: dt.date, end: dt.date, *, currency: str | None = None
) -> list[SpendingRow]:
    """My spending for expense dates in [start, end), grouped by day, merchant and category,
    in `currency` (default: the base currency). See the module docstring for the rules."""
    target = fx.currency_code(currency) if currency else base_currency()
    in_range = (Expense.expense_date >= start, Expense.expense_date < end)
    group = (Expense.expense_date, Expense.merchant, Expense.category, Expense.currency)
    personal = (
        select(*group, func.sum(Expense.total_minor), func.count())
        .where(Expense.owner_id == user_id, Expense.house_id.is_(None), *in_range)
        .group_by(*group)
    )
    shares = (
        select(*group, func.sum(ExpenseShare.amount_minor), func.count())
        .join(ExpenseShare, ExpenseShare.expense_id == Expense.id)
        .where(ExpenseShare.user_id == user_id, Expense.house_id.is_not(None), *in_range)
        .group_by(*group)
    )
    rows: list[SpendingRow] = []
    for stmt in (personal, shares):
        for day, merchant, category, row_currency, amount, count in db.execute(stmt):
            amount = int(amount or 0)
            if row_currency != target:
                try:
                    amount, _rate = fx.convert(db, amount, row_currency, target, day)
                except DomainError as exc:
                    log.warning("skipping %s %s on %s for %s: %s", amount, row_currency, day, user_id, exc)
                    continue
            rows.append(SpendingRow(day, merchant, category, amount, int(count)))
    return rows


def spending_by_category(
    db: Session, user_id: str, start: dt.date, end: dt.date, *, currency: str | None = None
) -> dict[str | None, int]:
    """My spending per category (None = uncategorised) for expense dates in [start, end),
    in `currency` (default: the base currency). See the module docstring for the rules."""
    totals: dict[str | None, int] = defaultdict(int)
    for row in spending_rows(db, user_id, start, end, currency=currency):
        totals[row.category] += row.amount_minor
    return dict(totals)


def _level(budget: Budget, spent_minor: int) -> Level:
    if spent_minor > budget.limit_minor:
        return "exceeded"
    if spent_minor * 100 >= budget.limit_minor * budget.alert_threshold_pct:
        return "warning"
    return "ok"


def _status(budget: Budget, month: dt.date, spent: dict[str | None, int]) -> BudgetStatus:
    spent_minor = sum(spent.values()) if budget.category is None else spent.get(budget.category, 0)
    return BudgetStatus(
        budget=budget,
        month=month,
        spent_minor=spent_minor,
        remaining_minor=budget.limit_minor - spent_minor,
        pct_used=spent_minor * 100 // budget.limit_minor,
        level=_level(budget, spent_minor),
    )


# --- CRUD ---------------------------------------------------------------------------------


def budget_category(raw: str | None) -> str | None:
    """None / "" / "overall" / "genel" -> None; otherwise one of CATEGORIES.

    Unlike expenses (where unknown text becomes "other"), an unknown budget category is an
    error: a budget silently set on "other" would never warn about what the user meant."""
    if raw is None or fold_text(raw) in OVERALL_WORDS:
        return None
    if not is_known_category(raw):
        raise InvalidInput(f"unknown category {raw!r}; use one of: {', '.join(CATEGORIES)} (empty = overall)")
    return normalize_category(raw)


def _sorted(budgets: list[Budget]) -> list[Budget]:
    return sorted(budgets, key=lambda b: (b.category is not None, b.category or ""))


def list_budgets(db: Session, user_id: str) -> list[Budget]:
    """Overall budget first, then categories alphabetically."""
    return _sorted(list(db.scalars(select(Budget).where(Budget.user_id == user_id))))


def _find(db: Session, user_id: str, category: str | None) -> Budget | None:
    cond = Budget.category.is_(None) if category is None else Budget.category == category
    return db.scalars(select(Budget).where(Budget.user_id == user_id, cond)).first()


def set_budget(
    db: Session,
    user_id: str,
    *,
    category: str | None,
    limit: Decimal | str,
    currency: str = "TRY",
    alert_threshold_pct: int = 80,
) -> Budget:
    """Create or update (upsert on user + category) a budget. `category` goes through
    `budget_category`; None = overall. The currency must be the base currency."""
    cat = budget_category(category)
    try:
        limit_minor = to_minor(limit)
    except MoneyError as exc:
        raise InvalidInput(str(exc)) from exc
    if limit_minor <= 0:
        raise InvalidInput("budget limit must be positive")
    code = fx.currency_code(currency)
    if code != base_currency():
        raise InvalidInput(f"budgets are kept in {base_currency()}; convert {code} first")
    if not 1 <= int(alert_threshold_pct) <= 100:
        raise InvalidInput("alert_threshold_pct must be between 1 and 100")

    ensure_user(db, user_id)
    budget = _find(db, user_id, cat)
    if budget is None:
        budget = Budget(user_id=user_id, category=cat)
        db.add(budget)
    budget.limit_minor = limit_minor
    budget.currency = code
    budget.alert_threshold_pct = int(alert_threshold_pct)
    try:
        db.commit()
    except IntegrityError:  # a concurrent request created the same budget: update that one
        db.rollback()
        budget = _find(db, user_id, cat)
        if budget is None:
            raise
        budget.limit_minor, budget.currency = limit_minor, code
        budget.alert_threshold_pct = int(alert_threshold_pct)
        db.commit()
    return budget


def delete_budget(db: Session, user_id: str, budget_id: int) -> None:
    budget = db.get(Budget, budget_id)
    if budget is None or budget.user_id != user_id:
        raise NotFound(f"budget {budget_id} not found")
    db.delete(budget)
    db.commit()


def budget_status(db: Session, user_id: str, month: dt.date | None = None) -> list[BudgetStatus]:
    """Status of every budget for the month containing `month` (default: this month)."""
    start = month_start(month or clock.today())
    budgets = list_budgets(db, user_id)
    if not budgets:
        return []
    spent = spending_by_category(db, user_id, start, add_months(start, 1))
    return [_status(b, start, spent) for b in budgets]


# --- pipeline hook ------------------------------------------------------------------------


def _label(budget: Budget) -> str:
    return "Overall budget" if budget.category is None else f"{budget.category.capitalize()} budget"


def warning_text(status: BudgetStatus, *, today: dt.date | None = None) -> str:
    """'Groceries budget: 85% used (1,700.00 of 2,000.00 TRY).' or '... exceeded: ...'."""
    b = status.budget
    when = "this month" if status.month == month_start(today or clock.today()) else f"in {status.month:%Y-%m}"
    spent, limit = fx.format_amount(status.spent_minor), fx.format_amount(b.limit_minor)
    if status.level == "exceeded":
        over = fx.format_amount(-status.remaining_minor)
        return (
            f"{_label(b)} exceeded {when}: {spent} of {limit} {b.currency} "
            f"({status.pct_used}%, {over} {b.currency} over)."
        )
    return f"{_label(b)}: {status.pct_used}% used {when} ({spent} of {limit} {b.currency})."


def _own_amount(expense: Expense) -> int:
    if expense.house_id is not None and expense.shares:
        return sum(s.amount_minor for s in expense.shares if s.user_id == expense.owner_id)
    return expense.total_minor


def _warnings(db: Session, expense: Expense) -> list[str]:
    user_id = expense.owner_id
    budgets = list_budgets(db, user_id)
    if not budgets:
        return []
    base = base_currency()
    day = expense.expense_date or clock.today()
    amount = _own_amount(expense)
    if expense.currency != base:
        amount, _rate = fx.convert(db, amount, expense.currency, base, day)
    if amount <= 0:
        return []
    start = month_start(day)
    before = spending_by_category(db, user_id, start, add_months(start, 1))
    after = dict(before)
    after[expense.category] = after.get(expense.category, 0) + amount

    messages = []
    for budget in sorted(budgets, key=lambda b: b.category is None):  # category budget first
        if budget.category is not None and budget.category != expense.category:
            continue
        old, new = _status(budget, start, before), _status(budget, start, after)
        if _LEVEL_RANK[new.level] > _LEVEL_RANK[old.level]:
            messages.append(warning_text(new))
    return messages


def warnings_for_new_expense(db: Session, expense: Expense) -> list[str]:
    """Pipeline hook: alerts this (not yet saved) expense would trigger for its payer, e.g.
    "Groceries budget: 85% used this month (1,700.00 of 2,000.00 TRY)." Never raises: a
    budget problem must not stop an expense from being saved."""
    try:
        return _warnings(db, expense)
    except Exception:
        log.exception("budget check failed for a new expense of %s", expense.owner_id)
        return []
