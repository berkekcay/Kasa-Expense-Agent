"""Review queue for imported expenses (owner: track INGEST)."""

from __future__ import annotations

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.expenses import ExpenseOut
from app.schemas.inbox import (
    InboxApproveIn,
    InboxApproveOut,
    InboxBulkIn,
    InboxBulkOut,
    InboxBulkResult,
    InboxItemOut,
    ParsedExpenseIO,
)
from app.services import inbox as inbox_service

router = APIRouter(prefix="/inbox", tags=["inbox"])


def _bulk(outcomes: list[inbox_service.BulkOutcome]) -> InboxBulkOut:
    results = [
        InboxBulkResult(
            item_id=o.item_id, status=o.status, expense_id=o.expense_id, warnings=o.warnings, error=o.error
        )
        for o in outcomes
    ]
    failed = sum(1 for r in results if r.status == "error")
    return InboxBulkOut(results=results, succeeded=len(results) - failed, failed=failed)


@router.get("", response_model=list[InboxItemOut])
def list_items(
    db: DB, user_id: CurrentUser, status: str | None = "pending", limit: int = 100
) -> list[InboxItemOut]:
    """Items for review, newest first. `status`: pending (default), approved, rejected,
    failed, ignored, or all."""
    items = inbox_service.list_items(db, user_id, status=status, limit=limit)
    return [InboxItemOut.from_model(i) for i in items]


@router.post("/approve", response_model=InboxBulkOut)
def approve_many(body: InboxBulkIn, db: DB, user_id: CurrentUser) -> InboxBulkOut:
    """Approve several items as parsed. Each result says approved or why not."""
    return _bulk(inbox_service.approve_many(db, user_id, body.ids))


@router.post("/reject", response_model=InboxBulkOut)
def reject_many(body: InboxBulkIn, db: DB, user_id: CurrentUser) -> InboxBulkOut:
    return _bulk(inbox_service.reject_many(db, user_id, body.ids))


@router.get("/{item_id}", response_model=InboxItemOut)
def get_item(item_id: int, db: DB, user_id: CurrentUser) -> InboxItemOut:
    return InboxItemOut.from_model(inbox_service.get_item(db, user_id, item_id))


@router.patch("/{item_id}", response_model=InboxItemOut)
def edit_item(item_id: int, body: ParsedExpenseIO, db: DB, user_id: CurrentUser) -> InboxItemOut:
    """Correct the parsed fields before approving (the item becomes pending)."""
    return InboxItemOut.from_model(inbox_service.update_parsed(db, user_id, item_id, body.to_parsed()))


@router.post("/{item_id}/approve", response_model=InboxApproveOut)
def approve(item_id: int, body: InboxApproveIn, db: DB, user_id: CurrentUser) -> InboxApproveOut:
    """Save the item as an expense (FX conversion and budget warnings apply). 409 if it was
    already saved."""
    parsed = body.parsed.to_parsed() if body.parsed else None
    item, saved = inbox_service.approve(db, user_id, item_id, parsed=parsed)
    return InboxApproveOut(
        item=InboxItemOut.from_model(item), expense=ExpenseOut.from_model(saved.expense, saved.warnings)
    )


@router.post("/{item_id}/reject", response_model=InboxItemOut)
def reject(item_id: int, db: DB, user_id: CurrentUser) -> InboxItemOut:
    return InboxItemOut.from_model(inbox_service.reject(db, user_id, item_id))
