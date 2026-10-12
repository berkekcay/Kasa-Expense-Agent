"""Budget schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Amount


class BudgetIn(BaseModel):
    category: str | None = Field(default=None, max_length=50, description="empty = overall budget")
    limit: Amount = Field(gt=0, decimal_places=2)
    currency: str = Field(default="TRY", min_length=2, max_length=3)
    alert_threshold_pct: int = Field(default=80, ge=1, le=100)


class BudgetOut(BaseModel):
    id: int
    category: str | None
    limit: str
    limit_minor: int
    currency: str
    alert_threshold_pct: int


class BudgetStatusOut(BaseModel):
    budget: BudgetOut
    month: dt.date
    spent: str
    spent_minor: int
    remaining: str
    remaining_minor: int
    pct_used: int
    level: Literal["ok", "warning", "exceeded"]
