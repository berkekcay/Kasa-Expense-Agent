"""Saved reports (owner: track REPORT): keep a chart the report agent made and run it again
later on fresh data, without the LLM.

A report is saved from a chat answer by its message id: the SQL and chart settings were
stored on the server with that answer (`api.agents._finish`), so the browser never sends SQL.
Every run goes through `reports.run_report_query`, the same static guard and user-scoped
relations as the chat, so a saved report can never read more than the agent could.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ChatMessage, SavedReport
from app.services import chat_history, reports
from app.services.errors import InvalidInput, NotFound

MAX_REPORTS = 50
MAX_PINNED = 4


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def save_from_message(db: Session, user_id: str, message_id: int, title: str | None = None) -> SavedReport:
    message = db.scalar(
        select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.user_id == user_id)
    )
    if message is None:
        raise NotFound("message not found")
    spec = chat_history.payload_of(message).get("report")
    if not spec or not spec.get("sql"):
        raise InvalidInput("this answer has no report to save")
    count = len(list(db.scalars(select(SavedReport.id).where(SavedReport.user_id == user_id))))
    if count >= MAX_REPORTS:
        raise InvalidInput(f"you can keep at most {MAX_REPORTS} reports; delete one first")
    report = SavedReport(
        user_id=user_id,
        title=(title or spec.get("title") or spec.get("question") or "Report").strip()[:200],
        question=(spec.get("question") or "")[:1000] or None,
        sql=spec["sql"],
        chart_type=spec.get("chart_type") or "table",
        x=spec.get("x") or None,
        y=spec.get("y") or None,
    )
    db.add(report)
    db.flush()
    return report


def list_reports(db: Session, user_id: str, *, pinned_only: bool = False) -> list[SavedReport]:
    stmt = select(SavedReport).where(SavedReport.user_id == user_id)
    if pinned_only:
        stmt = stmt.where(SavedReport.pinned.is_(True))
    return list(db.scalars(stmt.order_by(SavedReport.pinned.desc(), SavedReport.created_at.desc())))


def get(db: Session, user_id: str, report_id: int) -> SavedReport:
    report = db.scalar(select(SavedReport).where(SavedReport.id == report_id, SavedReport.user_id == user_id))
    if report is None:
        raise NotFound("report not found")
    return report


def run(
    db: Session, user_id: str, report_id: int
) -> tuple[SavedReport, dict[str, Any], dict[str, Any] | None]:
    """(report, result rows, chart spec) on today's data."""
    report = get(db, user_id, report_id)
    sql, chart_type, x, y, title = report.sql, report.chart_type, report.x, report.y, report.title
    try:
        result = reports.run_report_query(db, user_id, sql, get_settings().report_row_limit)
    except reports.UnsafeQuery as exc:  # e.g. the guard got stricter since it was saved
        raise InvalidInput(f"this report can no longer run: {exc}") from exc
    try:
        chart = reports.build_chart(result, chart_type, x or "", y or "", title)
    except ValueError:
        chart = reports.build_table(result, title)
    report = get(db, user_id, report_id)  # run_report_query rolled the session back
    report.last_run_at = _now()
    db.flush()
    return report, result, chart


def update(
    db: Session, user_id: str, report_id: int, *, title: str | None = None, pinned: bool | None = None
) -> SavedReport:
    report = get(db, user_id, report_id)
    if title is not None:
        if not title.strip():
            raise InvalidInput("the title cannot be empty")
        report.title = title.strip()[:200]
    if pinned is not None:
        if pinned and not report.pinned and len(list_reports(db, user_id, pinned_only=True)) >= MAX_PINNED:
            raise InvalidInput(f"you can pin at most {MAX_PINNED} reports to the dashboard")
        report.pinned = pinned
    db.flush()
    return report


def delete(db: Session, user_id: str, report_id: int) -> None:
    db.delete(get(db, user_id, report_id))
    db.flush()


def to_csv(result: dict[str, Any]) -> str:
    """UTF-8 CSV with a BOM so Excel opens Turkish letters correctly."""
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out)
    writer.writerow(result["columns"])
    for row in result["rows"]:
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in result["columns"]])
    return out.getvalue()
