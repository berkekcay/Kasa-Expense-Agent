"""Home dashboard numbers in one call (owner: track MONEY).

Deterministic SQL/ORM over the user's own rows, no LLM. Spending means the same thing as
for budgets (`budgets.spending_by_category`): my personal expenses plus my shares of house
expenses, in the base currency. House balances come from `services.houses` and are in each
house's currency.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Expense, ExpenseShare, InboxItem, Subscription
from app.services import budgets, clock, houses, subscriptions
from app.services.budgets import BudgetStatus

TREND_MONTHS = 6
RECENT_EXPENSES = 5
UPCOMING_DAYS = 30


@dataclass
class CategoryTotal:
    category: str  # "uncategorised" for NULL
    total_minor: int


@dataclass
class MonthTotal:
    month: dt.date  # first day of the month
    total_minor: int


@dataclass
class HouseBalance:
    house_id: int
    house_name: str
    balance_minor: int  # + = the house owes me
    currency: str = "TRY"


@dataclass
class RecentExpense:
    expense: Expense
    my_amount_minor: int  # the total for personal expenses, my share for house expenses


@dataclass
class DashboardSummary:
    month: dt.date  # first day of the month
    currency: str
    total_minor: int  # my personal spending + my shares of house expenses
    previous_month_total_minor: int
    by_category: list[CategoryTotal] = field(default_factory=list)
    budgets: list[BudgetStatus] = field(default_factory=list)
    upcoming_subscriptions: list[Subscription] = field(default_factory=list)
    house_balances: list[HouseBalance] = field(default_factory=list)
    pending_inbox: int = 0
    trend: list[MonthTotal] = field(default_factory=list)  # oldest first, ends with `month`
    recent_expenses: list[RecentExpense] = field(default_factory=list)


def _house_balances(db: Session, user_id: str) -> list[HouseBalance]:
    result = []
    for house in houses.list_houses(db, user_id):
        state = houses.house_balances(db, user_id, house.id)
        result.append(
            HouseBalance(
                house_id=house.id,
                house_name=house.name,
                balance_minor=state.balances.get(user_id, 0),
                currency=house.currency,
            )
        )
    return result


def _recent_expenses(db: Session, user_id: str, limit: int) -> list[RecentExpense]:
    mine = exists().where(ExpenseShare.expense_id == Expense.id, ExpenseShare.user_id == user_id)
    stmt = (
        select(Expense)
        .where(
            or_(
                (Expense.owner_id == user_id) & Expense.house_id.is_(None),
                Expense.house_id.is_not(None) & mine,
            )
        )
        .options(selectinload(Expense.shares))
        .order_by(Expense.expense_date.desc(), Expense.id.desc())
        .limit(limit)
    )
    result = []
    for e in db.scalars(stmt):
        if e.house_id is None:
            amount = e.total_minor
        else:
            amount = sum(s.amount_minor for s in e.shares if s.user_id == user_id)
        result.append(RecentExpense(expense=e, my_amount_minor=amount))
    return result


def _pending_inbox(db: Session, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(InboxItem)
        .where(InboxItem.user_id == user_id, InboxItem.status == "pending")
    )
    return int(db.scalar(stmt) or 0)


def dashboard_summary(db: Session, user_id: str, month: dt.date | None = None) -> DashboardSummary:
    """Everything the home page shows for the month containing `month` (default: now)."""
    start = budgets.month_start(month or clock.today())
    oldest = budgets.add_months(start, -(TREND_MONTHS - 1))

    trend: list[MonthTotal] = []
    current: dict[str | None, int] = {}
    for offset in range(TREND_MONTHS):
        first = budgets.add_months(oldest, offset)
        spent = budgets.spending_by_category(db, user_id, first, budgets.add_months(first, 1))
        trend.append(MonthTotal(first, sum(spent.values())))
        if first == start:
            current = spent

    by_category = sorted(
        (CategoryTotal(category or "uncategorised", total) for category, total in current.items() if total),
        key=lambda c: (-c.total_minor, c.category),
    )
    return DashboardSummary(
        month=start,
        currency=budgets.base_currency(),
        total_minor=trend[-1].total_minor,
        previous_month_total_minor=trend[-2].total_minor,
        by_category=by_category,
        budgets=budgets.budget_status(db, user_id, start),
        upcoming_subscriptions=subscriptions.upcoming_charges(db, user_id, within_days=UPCOMING_DAYS),
        house_balances=_house_balances(db, user_id),
        pending_inbox=_pending_inbox(db, user_id),
        trend=trend,
        recent_expenses=_recent_expenses(db, user_id, RECENT_EXPENSES),
    )
