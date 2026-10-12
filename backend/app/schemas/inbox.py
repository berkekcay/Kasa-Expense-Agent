"""Inbox (email / statement review queue) schemas (owner: track INGEST)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.schemas.common import Amount
from app.schemas.expenses import ExpenseOut


class ParsedItemIO(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Amount = Field(gt=0, decimal_places=2)
    quantity: str = "1"


class ParsedExpenseIO(BaseModel):
    """Same fields as services.inbox.ParsedExpense."""

    merchant: str = Field(min_length=1, max_length=200)
    total: Amount = Field(gt=0, decimal_places=2)
    currency: str = Field(default="TRY", min_length=2, max_length=3)
    expense_date: dt.date | None = None
    category: str | None = Field(default=None, max_length=50)
    items: list[ParsedItemIO] = []


class InboxItemOut(BaseModel):
    id: int
    source: str
    external_ref: str
    received_at: dt.datetime
    title: str
    sender: str | None
    excerpt: str | None
    parsed: ParsedExpenseIO | None
    status: str
    expense_id: int | None
    error: str | None
    created_at: dt.datetime
    decided_at: dt.datetime | None


class InboxApproveIn(BaseModel):
    parsed: ParsedExpenseIO | None = Field(default=None, description="edited fields; empty = as parsed")


class InboxApproveOut(BaseModel):
    item: InboxItemOut
    expense: ExpenseOut
