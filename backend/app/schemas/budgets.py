"""Budget schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import Budget
from app.schemas.common import Amount
from app.services.budgets import BudgetStatus
from app.services.money import format_minor


class BudgetIn(BaseModel):
    category: str | None = Field(
        default=None,
        max_length=50,
        description="A category or a synonym ('market' means groceries); empty or null = overall budget",
        examples=["groceries"],
    )
    limit: Amount = Field(gt=0, decimal_places=2, description="Monthly limit", examples=["3000.00"])
    currency: str = Field(default="TRY", min_length=2, max_length=3, description="Must be the base currency")
    alert_threshold_pct: int = Field(
        default=80, ge=1, le=100, description="Warn from this percent of the limit"
    )


class BudgetOut(BaseModel):
    id: int
    category: str | None = Field(description="null = overall budget")
    limit: str
    limit_minor: int
    currency: str
    alert_threshold_pct: int

    @classmethod
    def from_model(cls, b: Budget) -> BudgetOut:
        return cls(
            id=b.id,
            category=b.category,
            limit=format_minor(b.limit_minor),
            limit_minor=b.limit_minor,
            currency=b.currency,
            alert_threshold_pct=b.alert_threshold_pct,
        )


class BudgetStatusOut(BaseModel):
    budget: BudgetOut
    month: dt.date = Field(description="First day of the month")
    spent: str
    spent_minor: int
    remaining: str = Field(description="Negative when over the limit")
    remaining_minor: int
    pct_used: int = Field(description="floor(spent * 100 / limit); can be above 100")
    level: Literal["ok", "warning", "exceeded"]

    @classmethod
    def from_status(cls, s: BudgetStatus) -> BudgetStatusOut:
        return cls(
            budget=BudgetOut.from_model(s.budget),
            month=s.month,
            spent=format_minor(s.spent_minor),
            spent_minor=s.spent_minor,
            remaining=format_minor(s.remaining_minor),
            remaining_minor=s.remaining_minor,
            pct_used=s.pct_used,
            level=s.level,
        )
