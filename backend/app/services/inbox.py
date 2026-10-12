"""Review queue for imported expenses (owner: track INGEST).

Gmail sync and statement imports never save expenses directly. They create InboxItems
(status "pending") with the fields an agent or parser extracted; the user approves (maybe
after editing) or rejects each one. Approval goes through `expenses.add_expense` with
source = item.source and external_ref = item.external_ref, so the MONEY hook runs and an
item can never be saved twice.

`ParsedExpense` is the shape of `inbox_items.parsed_json`, shared by the parsers, the API
and the frontend. It is finished; the queue functions below are for track INGEST.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field

from sqlalchemy.orm import Session

from app.db.models import InboxItem
from app.services.expenses import ExpenseInput, ItemInput, SavedExpense


@dataclass
class ParsedItem:
    description: str
    amount: str  # major units as a decimal string, e.g. "17.50"
    quantity: str = "1"


@dataclass
class ParsedExpense:
    merchant: str
    total: str  # major units as a decimal string
    currency: str = "TRY"
    expense_date: dt.date | None = None
    category: str | None = None  # free text; normalised when the expense is created
    items: list[ParsedItem] = field(default_factory=list)

    def to_json(self) -> str:
        data = asdict(self)
        data["expense_date"] = self.expense_date.isoformat() if self.expense_date else None
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> ParsedExpense:
        data = json.loads(raw)
        day = data.get("expense_date")
        return cls(
            merchant=str(data["merchant"]),
            total=str(data["total"]),
            currency=str(data.get("currency") or "TRY"),
            expense_date=dt.date.fromisoformat(day) if day else None,
            category=data.get("category"),
            items=[ParsedItem(**i) for i in data.get("items") or []],
        )

    def to_input(self, note: str | None = None) -> ExpenseInput:
        return ExpenseInput(
            merchant=self.merchant,
            total=self.total,
            expense_date=self.expense_date,
            currency=self.currency,
            category=self.category,
            note=note,
            items=[ItemInput(i.description, i.amount, i.quantity) for i in self.items],
        )


def create_item(
    db: Session,
    user_id: str,
    *,
    source: str,
    external_ref: str,
    received_at: dt.datetime,
    title: str,
    sender: str | None = None,
    excerpt: str | None = None,
    parsed: ParsedExpense | None = None,
    status: str = "pending",
    error: str | None = None,
) -> InboxItem | None:
    """Insert one item; returns None (and changes nothing) if (user, source, external_ref)
    already exists. Trims title/excerpt to the column sizes."""
    raise NotImplementedError("create_item: track INGEST")


def list_items(db: Session, user_id: str, *, status: str | None = None, limit: int = 100) -> list[InboxItem]:
    raise NotImplementedError("list_items: track INGEST")


def get_item(db: Session, user_id: str, item_id: int) -> InboxItem:
    raise NotImplementedError("get_item: track INGEST")


def update_parsed(db: Session, user_id: str, item_id: int, parsed: ParsedExpense) -> InboxItem:
    """User edits before approving. Only pending/failed items can be edited."""
    raise NotImplementedError("update_parsed: track INGEST")


def approve(
    db: Session, user_id: str, item_id: int, *, parsed: ParsedExpense | None = None
) -> tuple[InboxItem, SavedExpense]:
    """Create the expense (add_expense with source/external_ref of the item), link it,
    set status "approved" and decided_at. Conflict if it was already approved."""
    raise NotImplementedError("approve: track INGEST")


def reject(db: Session, user_id: str, item_id: int) -> InboxItem:
    raise NotImplementedError("reject: track INGEST")
