"""Dashboard schema (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel

from app.schemas.budgets import BudgetStatusOut
from app.schemas.subscriptions import SubscriptionOut


class CategoryTotalOut(BaseModel):
    category: str
    total: str
    total_minor: int


class HouseBalanceOut(BaseModel):
    house_id: int
    house_name: str
    balance: str
    balance_minor: int


class DashboardOut(BaseModel):
    month: dt.date
    currency: str
    total: str
    total_minor: int
    previous_month_total: str
    previous_month_total_minor: int
    by_category: list[CategoryTotalOut]
    budgets: list[BudgetStatusOut]
    upcoming_subscriptions: list[SubscriptionOut]
    house_balances: list[HouseBalanceOut]
    pending_inbox: int
