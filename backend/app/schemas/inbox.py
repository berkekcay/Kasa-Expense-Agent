"""Inbox (email / statement review queue) schemas (owner: track INGEST)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.db.models import InboxItem
from app.schemas.common import Amount
from app.schemas.expenses import ExpenseOut
from app.services import inbox as inbox_service


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

    def to_parsed(self) -> inbox_service.ParsedExpense:
        return inbox_service.ParsedExpense(
            merchant=self.merchant.strip(),
            total=str(self.total),
            currency=self.currency,
            expense_date=self.expense_date,
            category=self.category,
            items=[
                inbox_service.ParsedItem(i.description.strip(), str(i.amount), i.quantity or "1")
                for i in self.items
            ],
        )

    @classmethod
    def from_parsed(cls, parsed: inbox_service.ParsedExpense | None) -> ParsedExpenseIO | None:
        if parsed is None:
            return None
        try:
            return cls(
                merchant=parsed.merchant,
                total=parsed.total,
                currency=parsed.currency,
                expense_date=parsed.expense_date,
                category=parsed.category,
                items=[
                    ParsedItemIO(description=i.description, amount=i.amount, quantity=i.quantity)
                    for i in parsed.items
                ],
            )
        except ValueError:  # stored data that no longer validates: show it as unparsed
            return None


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

    @classmethod
    def from_model(cls, item: InboxItem) -> InboxItemOut:
        return cls(
            id=item.id,
            source=item.source,
            external_ref=item.external_ref,
            received_at=item.received_at,
            title=item.title,
            sender=item.sender,
            excerpt=item.excerpt,
            parsed=ParsedExpenseIO.from_parsed(inbox_service.parsed_of(item)),
            status=item.status,
            expense_id=item.expense_id,
            error=item.error,
            created_at=item.created_at,
            decided_at=item.decided_at,
        )


class InboxApproveIn(BaseModel):
    parsed: ParsedExpenseIO | None = Field(default=None, description="edited fields; empty = as parsed")


class InboxApproveOut(BaseModel):
    item: InboxItemOut
    expense: ExpenseOut  # expense.warnings has FX notes and budget alerts


class InboxBulkIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=200)


class InboxBulkResult(BaseModel):
    item_id: int
    status: str  # approved | rejected | error
    expense_id: int | None = None
    warnings: list[str] = []
    error: str | None = None


class InboxBulkOut(BaseModel):
    results: list[InboxBulkResult]
    succeeded: int
    failed: int
