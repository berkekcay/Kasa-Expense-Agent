"""Review queue for imported expenses (owner: track INGEST).

Gmail sync and statement imports never save expenses directly. They create InboxItems
(status "pending") with the fields an agent or parser extracted; the user approves (maybe
after editing) or rejects each one. Approval goes through `expenses.add_expense` with
source = item.source and external_ref = item.external_ref, so the MONEY hook runs and an
item can never be saved twice. The parser agents cannot reach anything in this module
except through their caller creating items: only the user (REST API, or the chat inbox
agent acting on the user's explicit request) approves.

`ParsedExpense` is the shape of `inbox_items.parsed_json`, shared by the parsers, the API
and the frontend.
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, field

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import INBOX_SOURCES, INBOX_STATUSES, InboxItem
from app.services import expenses as expense_service
from app.services.errors import Conflict, DomainError, InvalidInput, NotFound
from app.services.expenses import ExpenseInput, ItemInput, SavedExpense
from app.services.money import format_minor


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


EXCERPT_CHARS = 500


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _naive_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is not None:
        value = value.astimezone(dt.UTC).replace(tzinfo=None)
    return value


def short_excerpt(text: str | None, limit: int = EXCERPT_CHARS) -> str | None:
    """Whitespace-collapsed start of a text, for display only (never the full email)."""
    if not text:
        return None
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3].rstrip() + "..."


def find_item(db: Session, user_id: str, source: str, external_ref: str) -> InboxItem | None:
    return db.scalars(
        select(InboxItem).where(
            InboxItem.user_id == user_id, InboxItem.source == source, InboxItem.external_ref == external_ref
        )
    ).first()


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
    """Insert one item and commit; returns None (and changes nothing) if (user, source,
    external_ref) already exists. Trims title/excerpt to the column sizes."""
    if source not in INBOX_SOURCES:
        raise InvalidInput(f"unknown inbox source {source!r}")
    if status not in INBOX_STATUSES or status == "approved":
        raise InvalidInput(f"items cannot be created as {status!r}")
    if find_item(db, user_id, source, external_ref) is not None:
        return None
    expense_service.ensure_user(db, user_id)
    item = InboxItem(
        user_id=user_id,
        source=source,
        external_ref=external_ref[:200],
        received_at=_naive_utc(received_at),
        title=(" ".join((title or "").split()) or "(no subject)")[:300],
        sender=sender[:320] if sender else None,
        excerpt=short_excerpt(excerpt, 2000),
        parsed_json=parsed.to_json() if parsed else None,
        status=status,
        error=error[:500] if error else None,
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:  # a concurrent sync inserted the same ref first
        db.rollback()
        return None
    return item


def list_items(db: Session, user_id: str, *, status: str | None = None, limit: int = 100) -> list[InboxItem]:
    """Newest first. `status` None or "all" lists every status."""
    stmt = select(InboxItem).where(InboxItem.user_id == user_id)
    if status and status != "all":
        if status not in INBOX_STATUSES:
            raise InvalidInput(f"status must be one of {', '.join(INBOX_STATUSES)} or all")
        stmt = stmt.where(InboxItem.status == status)
    stmt = stmt.order_by(InboxItem.received_at.desc(), InboxItem.id.desc()).limit(max(1, min(limit, 500)))
    return list(db.scalars(stmt))


def count_pending(db: Session, user_id: str) -> int:
    stmt = select(func.count()).where(InboxItem.user_id == user_id, InboxItem.status == "pending")
    return int(db.scalar(stmt) or 0)


def get_item(db: Session, user_id: str, item_id: int) -> InboxItem:
    item = db.scalars(select(InboxItem).where(InboxItem.id == item_id, InboxItem.user_id == user_id)).first()
    if item is None:
        raise NotFound(f"inbox item {item_id} not found")
    return item


def parsed_of(item: InboxItem) -> ParsedExpense | None:
    if not item.parsed_json:
        return None
    try:
        return ParsedExpense.from_json(item.parsed_json)
    except (ValueError, KeyError, TypeError):
        return None


def _validate(parsed: ParsedExpense) -> None:
    """Same checks the expense pipeline runs, so a bad edit fails before approval."""
    expense_service.build_expense("validation", parsed.to_input())


def update_parsed(db: Session, user_id: str, item_id: int, parsed: ParsedExpense) -> InboxItem:
    """User edits before approving. Approved items cannot change; any other item becomes
    "pending" again with the edited fields (so a wrongly ignored email can be fixed)."""
    item = get_item(db, user_id, item_id)
    if item.status == "approved":
        raise Conflict(f"inbox item {item_id} is already approved")
    _validate(parsed)
    item.parsed_json = parsed.to_json()
    item.status = "pending"
    item.error = None
    item.decided_at = None
    db.commit()
    return item


def approve(
    db: Session, user_id: str, item_id: int, *, parsed: ParsedExpense | None = None
) -> tuple[InboxItem, SavedExpense]:
    """Create the expense (add_expense with source/external_ref of the item), link it,
    set status "approved" and decided_at. Conflict if it was already approved.

    If an expense with the same source and ref already exists (a concurrent click, or an
    earlier run that saved the expense but not the item), the item is linked to that
    expense and Conflict is raised."""
    item = get_item(db, user_id, item_id)
    if item.status == "approved":
        raise Conflict(f"inbox item {item_id} is already approved (expense {item.expense_id})")
    if parsed is not None:
        _validate(parsed)
        item.parsed_json = parsed.to_json()
    data = parsed or parsed_of(item)
    if data is None:
        raise InvalidInput(f"inbox item {item_id} has no expense details yet; edit it first")
    label = "Email" if item.source == "email" else "Statement"
    note = f"{label}: {item.title}"[:500]
    try:
        saved = expense_service.add_expense(
            db, user_id, data.to_input(note=note), source=item.source, external_ref=item.external_ref
        )
    except (Conflict, IntegrityError):  # IntegrityError: a concurrent approval won the race
        db.rollback()
        existing = expense_service.find_by_external_ref(db, user_id, item.source, item.external_ref)
        item = get_item(db, user_id, item_id)
        if existing is not None:
            item.expense_id = existing.id
            item.status = "approved"
            item.decided_at = item.decided_at or _utcnow()
            db.commit()
        ref = existing.id if existing else "?"
        raise Conflict(f"inbox item {item_id} was already saved as expense {ref}") from None
    item = get_item(db, user_id, item_id)
    item.expense_id = saved.expense.id
    item.status = "approved"
    item.error = None
    item.decided_at = _utcnow()
    db.commit()
    warnings = list(saved.warnings)
    expense = saved.expense
    if expense.items:
        items_total = expense_service.items_sum_minor(expense)
        if items_total != expense.total_minor:
            warnings.append(
                f"line items add up to {format_minor(items_total)} but the total is "
                f"{format_minor(expense.total_minor)}"
            )
    return item, SavedExpense(expense, warnings)


def reject(db: Session, user_id: str, item_id: int) -> InboxItem:
    item = get_item(db, user_id, item_id)
    if item.status == "approved":
        raise Conflict(f"inbox item {item_id} is already approved; delete the expense instead")
    item.status = "rejected"
    item.decided_at = _utcnow()
    db.commit()
    return item


@dataclass
class BulkOutcome:
    item_id: int
    status: str  # approved | rejected | error
    expense_id: int | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def approve_many(db: Session, user_id: str, item_ids: list[int]) -> list[BulkOutcome]:
    """Approve each item as parsed; one failure does not stop the others."""
    outcomes: list[BulkOutcome] = []
    for item_id in dict.fromkeys(item_ids):
        try:
            item, saved = approve(db, user_id, item_id)
        except DomainError as exc:
            db.rollback()
            outcomes.append(BulkOutcome(item_id, "error", error=str(exc)))
            continue
        outcomes.append(BulkOutcome(item_id, "approved", item.expense_id, saved.warnings))
    return outcomes


def reject_many(db: Session, user_id: str, item_ids: list[int]) -> list[BulkOutcome]:
    outcomes: list[BulkOutcome] = []
    for item_id in dict.fromkeys(item_ids):
        try:
            reject(db, user_id, item_id)
        except DomainError as exc:
            db.rollback()
            outcomes.append(BulkOutcome(item_id, "error", error=str(exc)))
            continue
        outcomes.append(BulkOutcome(item_id, "rejected"))
    return outcomes
