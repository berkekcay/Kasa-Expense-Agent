"""Chat and receipt schemas (shared by the agent endpoints)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.expenses import ExpenseOut


class ReceiptOut(BaseModel):
    expense: ExpenseOut
    agent_message: str
    warnings: list[str] = []


class ChartSpec(BaseModel):
    """What the chat shows under an answer. bar/line/pie: `x` and `y` name the columns of
    `data` to draw (y is a number). table: `columns` in order and `data` is every result row
    as it came back (money as exact decimal strings); `x` and `y` are empty."""

    type: Literal["bar", "line", "pie", "table"]
    title: str = ""
    x: str = ""
    y: str = ""
    columns: list[str] = []
    data: list[dict[str, Any]]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    conversation_id: str | None = Field(
        default=None, description="Saved conversation; empty starts a new one"
    )
    file_ids: list[str] = Field(default=[], max_length=5, description="Files from POST /chat/files")
    locale: Literal["tr", "en"] | None = Field(
        default=None, description="UI language; decides the reply language when the message does not"
    )


class ChatCard(BaseModel):
    """Something the turn did, shown under the answer.
    expense: an expense was saved (`data` has expense_id, merchant, total, currency, date,
      house); the UI offers undo. payment: a payment between flatmates was recorded.
    import: rows of an attached file are ready to add (`data` is the preview with draft_id);
      nothing is saved until the user confirms with POST /chat/imports/{draft_id}."""

    kind: Literal["expense", "payment", "import"]
    data: dict[str, Any]


class ChatOut(BaseModel):
    session_id: str
    text: str
    chart: ChartSpec | None = None
    agent: str | None = None  # specialist that produced the answer, e.g. "report_agent"
    cards: list[ChatCard] = []
    conversation_id: str | None = None
    message_id: int | None = None  # the saved answer, for PUT /chat/messages/{id}/cards/{i}


class SheetOut(BaseModel):
    name: str
    rows: int
    columns: list[str]


class ChatFileOut(BaseModel):
    file_id: str
    filename: str
    sheets: list[SheetOut]


class ImportConfirmOut(BaseModel):
    created: int
    duplicates: int


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: dt.datetime
    updated_at: dt.datetime
    message_count: int = 0


class ChatMessageOut(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    text: str
    created_at: dt.datetime
    chart: ChartSpec | None = None
    agent: str | None = None
    cards: list[ChatCard] = []
    card_state: dict[str, dict[str, Any]] = {}
    files: list[dict[str, str]] = []


class ConversationDetailOut(ConversationOut):
    messages: list[ChatMessageOut]


class ConversationRenameIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class CardStateIn(BaseModel):
    state: dict[str, Any]
