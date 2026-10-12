"""Home dashboard numbers in one call (owner: track MONEY).

Plain SQL aggregates over the user's own rows; everything in the base currency.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.db.models import Subscription
from app.services.budgets import BudgetStatus


@dataclass
class CategoryTotal:
    category: str  # "uncategorised" for NULL
    total_minor: int


@dataclass
class HouseBalance:
    house_id: int
    house_name: str
    balance_minor: int  # + = the house owes me


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


def dashboard_summary(db: Session, user_id: str, month: dt.date | None = None) -> DashboardSummary:
    raise NotImplementedError("dashboard_summary: track MONEY")
