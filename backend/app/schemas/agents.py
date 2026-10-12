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
    type: Literal["bar", "line", "pie"]
    title: str = ""
    x: str
    y: str
    data: list[dict[str, Any]]


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatOut(BaseModel):
    session_id: str
    text: str
    chart: ChartSpec | None = None
    agent: str | None = None  # specialist that produced the answer, e.g. "report_agent"
