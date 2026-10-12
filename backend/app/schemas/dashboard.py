"""Dashboard schema (owner: track MONEY). Amounts are decimal strings plus integer minor
units, ready for charts (`total_minor / 100` on an axis, `total` in labels)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.schemas.budgets import BudgetStatusOut
from app.schemas.subscriptions import SubscriptionOut
from app.services.dashboard import DashboardSummary
from app.services.money import format_minor


class CategoryTotalOut(BaseModel):
    category: str = Field(description="'uncategorised' for expenses without a category")
    total: str
    total_minor: int


class MonthTotalOut(BaseModel):
    month: dt.date = Field(description="First day of the month")
    total: str
    total_minor: int


class HouseBalanceOut(BaseModel):
    house_id: int
    house_name: str
    balance: str = Field(description="Positive: the house owes me. Negative: I owe.")
    balance_minor: int
    currency: str


class RecentExpenseOut(BaseModel):
    id: int
    merchant: str
    expense_date: dt.date
    category: str | None
    house_id: int | None
    currency: str
    total: str
    total_minor: int
    my_amount: str = Field(description="The total for personal expenses, my share for house expenses")
    my_amount_minor: int


class DashboardOut(BaseModel):
    month: dt.date = Field(description="First day of the month")
    currency: str = Field(description="Base currency of every total below")
    total: str = Field(description="My personal spending plus my shares of house expenses")
    total_minor: int
    previous_month_total: str
    previous_month_total_minor: int
    by_category: list[CategoryTotalOut] = Field(description="This month, largest first")
    budgets: list[BudgetStatusOut]
    upcoming_subscriptions: list[SubscriptionOut] = Field(description="Next 30 days, soonest first")
    house_balances: list[HouseBalanceOut]
    pending_inbox: int
    trend: list[MonthTotalOut] = Field(description="Last 6 months, oldest first, ending with `month`")
    recent_expenses: list[RecentExpenseOut] = Field(description="Newest 5 personal or shared expenses")

    @classmethod
    def from_summary(cls, s: DashboardSummary) -> DashboardOut:
        return cls(
            month=s.month,
            currency=s.currency,
            total=format_minor(s.total_minor),
            total_minor=s.total_minor,
            previous_month_total=format_minor(s.previous_month_total_minor),
            previous_month_total_minor=s.previous_month_total_minor,
            by_category=[
                CategoryTotalOut(
                    category=c.category, total=format_minor(c.total_minor), total_minor=c.total_minor
                )
                for c in s.by_category
            ],
            budgets=[BudgetStatusOut.from_status(b) for b in s.budgets],
            upcoming_subscriptions=[SubscriptionOut.from_model(x) for x in s.upcoming_subscriptions],
            house_balances=[
                HouseBalanceOut(
                    house_id=h.house_id,
                    house_name=h.house_name,
                    balance=format_minor(h.balance_minor),
                    balance_minor=h.balance_minor,
                    currency=h.currency,
                )
                for h in s.house_balances
            ],
            pending_inbox=s.pending_inbox,
            trend=[
                MonthTotalOut(month=m.month, total=format_minor(m.total_minor), total_minor=m.total_minor)
                for m in s.trend
            ],
            recent_expenses=[
                RecentExpenseOut(
                    id=r.expense.id,
                    merchant=r.expense.merchant,
                    expense_date=r.expense.expense_date,
                    category=r.expense.category,
                    house_id=r.expense.house_id,
                    currency=r.expense.currency,
                    total=format_minor(r.expense.total_minor),
                    total_minor=r.expense.total_minor,
                    my_amount=format_minor(r.my_amount_minor),
                    my_amount_minor=r.my_amount_minor,
                )
                for r in s.recent_expenses
            ],
        )
