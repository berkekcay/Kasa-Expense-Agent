"""Monthly budgets and alerts (owner: track MONEY).

A budget is a monthly limit for one category, or overall when category is None. Spending
for a month = the user's personal expenses + their *shares* of house expenses, in the
base currency. `warnings_for_new_expense` is the budget half of the expense pipeline hook
(`services.expenses.finalize_expense`).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from sqlalchemy.orm import Session

from app.db.models import Budget, Expense


@dataclass
class BudgetStatus:
    budget: Budget
    month: dt.date  # first day of the month
    spent_minor: int
    remaining_minor: int  # may be negative
    pct_used: int  # floor(spent * 100 / limit)
    level: Literal["ok", "warning", "exceeded"]  # warning at >= alert_threshold_pct


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
    `categories.normalize_category`; None = overall."""
    raise NotImplementedError("set_budget: track MONEY")


def list_budgets(db: Session, user_id: str) -> list[Budget]:
    raise NotImplementedError("list_budgets: track MONEY")


def delete_budget(db: Session, user_id: str, budget_id: int) -> None:
    raise NotImplementedError("delete_budget: track MONEY")


def budget_status(db: Session, user_id: str, month: dt.date | None = None) -> list[BudgetStatus]:
    """Status of every budget for the month containing `month` (default: this month)."""
    raise NotImplementedError("budget_status: track MONEY")


def warnings_for_new_expense(db: Session, expense: Expense) -> list[str]:
    """Pipeline hook: alerts this (not yet saved) expense would trigger for its payer, e.g.
    "groceries budget: 85% used (1700.00 of 2000.00 TRY)". Must not raise for users
    without budgets."""
    # Placeholder until track MONEY lands: budgets are not checked yet.
    return []
