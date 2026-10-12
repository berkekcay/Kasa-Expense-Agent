"""Chat and receipt schemas (shared by the agent endpoints)."""

from __future__ import annotations

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


class ChatOut(BaseModel):
    session_id: str
    text: str
    chart: ChartSpec | None = None
    agent: str | None = None  # specialist that produced the answer, e.g. "report_agent"
