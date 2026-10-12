"""Review queue for imported expenses (owner: track INGEST)."""

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.inbox import InboxApproveIn, InboxApproveOut, InboxItemOut, ParsedExpenseIO
from app.services import inbox as inbox_service

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("", response_model=list[InboxItemOut])
def list_items(db: DB, user_id: CurrentUser, status: str | None = "pending") -> list[InboxItemOut]:
    inbox_service.list_items(db, user_id, status=status)
    raise NotImplementedError("GET /inbox: track INGEST")


@router.get("/{item_id}", response_model=InboxItemOut)
def get_item(item_id: int, db: DB, user_id: CurrentUser) -> InboxItemOut:
    inbox_service.get_item(db, user_id, item_id)
    raise NotImplementedError("GET /inbox/{id}: track INGEST")


@router.patch("/{item_id}", response_model=InboxItemOut)
def edit_item(item_id: int, body: ParsedExpenseIO, db: DB, user_id: CurrentUser) -> InboxItemOut:
    raise NotImplementedError("PATCH /inbox/{id}: track INGEST")


@router.post("/{item_id}/approve", response_model=InboxApproveOut)
def approve(item_id: int, body: InboxApproveIn, db: DB, user_id: CurrentUser) -> InboxApproveOut:
    raise NotImplementedError("POST /inbox/{id}/approve: track INGEST")


@router.post("/{item_id}/reject", response_model=InboxItemOut)
def reject(item_id: int, db: DB, user_id: CurrentUser) -> InboxItemOut:
    inbox_service.reject(db, user_id, item_id)
    raise NotImplementedError("POST /inbox/{id}/reject: track INGEST")
