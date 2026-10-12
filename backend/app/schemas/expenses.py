"""Expense schemas (shared; changes need a heads-up to every track)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import Expense
from app.schemas.common import Amount, money_str
from app.services.money import format_minor


class ItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Amount = Field(gt=0, decimal_places=2)
    quantity: Decimal = Field(default=Decimal(1), gt=0, decimal_places=3)


class ExpenseIn(BaseModel):
    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    expense_date: dt.date | None = None
    currency: str = Field(default="TRY", min_length=2, max_length=3)
    category: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)
    items: list[ItemIn] = []


AMOUNT_FIELDS = ("total", "currency", "items", "amount", "total_minor", "shares")


class ExpenseUpdateIn(BaseModel):
    """Fields of an expense that can change. Send only the ones to change; `note` or
    `category` set to null clears it. Amounts, currency and items cannot change: to fix an
    amount, delete the expense and add it again."""

    model_config = ConfigDict(extra="forbid")

    merchant: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=50, description="null clears it")
    expense_date: dt.date | None = None
    note: str | None = Field(default=None, max_length=500, description="null or empty clears it")

    @model_validator(mode="before")
    @classmethod
    def _no_amounts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            amounts = sorted(k for k in data if k in AMOUNT_FIELDS)
            if amounts:
                raise ValueError(
                    f"{', '.join(amounts)} cannot be changed; delete the expense and add it again"
                )
        return data


class ItemOut(BaseModel):
    description: str
    quantity: str
    amount: str
    amount_minor: int
    assignees: list[str] = []  # user ids, for split_type "items"


class ShareOut(BaseModel):
    user_id: str
    amount: str
    amount_minor: int


class ExpenseOut(BaseModel):
    id: int
    owner_id: str
    house_id: int | None
    merchant: str
    expense_date: dt.date
    currency: str
    total: str
    total_minor: int
    category: str | None
    source: str
    note: str | None
    items: list[ItemOut]
    shares: list[ShareOut]
    split_type: str | None = None
    # Set when the purchase was in another currency and was converted to `currency`.
    original_currency: str | None = None
    original_total: str | None = None
    original_total_minor: int | None = None
    fx_rate: str | None = None
    fx_date: dt.date | None = None
    subscription_id: int | None = None
    # Only on create responses: FX notes, budget alerts, receipt sanity checks.
    warnings: list[str] = []

    @classmethod
    def from_model(cls, e: Expense, warnings: list[str] | None = None) -> ExpenseOut:
        return cls(
            id=e.id,
            owner_id=e.owner_id,
            house_id=e.house_id,
            merchant=e.merchant,
            expense_date=e.expense_date,
            currency=e.currency,
            total=format_minor(e.total_minor),
            total_minor=e.total_minor,
            category=e.category,
            source=e.source,
            note=e.note,
            items=[
                ItemOut(
                    description=i.description,
                    quantity=str(i.quantity.normalize() if isinstance(i.quantity, Decimal) else i.quantity),
                    amount=format_minor(i.amount_minor),
                    amount_minor=i.amount_minor,
                    assignees=[a.user_id for a in i.assignees],
                )
                for i in e.items
            ],
            shares=[
                ShareOut(user_id=s.user_id, amount=format_minor(s.amount_minor), amount_minor=s.amount_minor)
                for s in e.shares
            ],
            split_type=e.split_type,
            original_currency=e.original_currency,
            original_total=money_str(e.original_total_minor),
            original_total_minor=e.original_total_minor,
            fx_rate=None if e.fx_rate is None else str(e.fx_rate),
            fx_date=e.fx_date,
            subscription_id=e.subscription_id,
            warnings=warnings or [],
        )


class CategoriesOut(BaseModel):
    categories: list[str]
