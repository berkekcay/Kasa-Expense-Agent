"""Saved reports (owner: track REPORT): charts kept from the chat, run again on fresh data
without the LLM. See `services.saved_reports`."""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.auth import DB, CurrentUser
from app.schemas.agents import ChartSpec
from app.services import saved_reports

router = APIRouter(prefix="/reports", tags=["reports"])


class SaveReportIn(BaseModel):
    message_id: int = Field(description="A chat answer with report_saveable=true")
    title: str | None = Field(default=None, max_length=200)


class ReportUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    pinned: bool | None = None


class ReportOut(BaseModel):
    id: int
    title: str
    question: str | None
    chart_type: str
    pinned: bool
    created_at: dt.datetime
    last_run_at: dt.datetime | None


class ReportRunOut(BaseModel):
    report: ReportOut
    chart: ChartSpec | None
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool
    run_at: dt.datetime


def _out(r) -> ReportOut:
    return ReportOut(
        id=r.id,
        title=r.title,
        question=r.question,
        chart_type=r.chart_type,
        pinned=r.pinned,
        created_at=r.created_at,
        last_run_at=r.last_run_at,
    )


@router.post("", response_model=ReportOut, status_code=201)
def save_report(body: SaveReportIn, db: DB, user_id: CurrentUser) -> ReportOut:
    """Keep the chart of a chat answer. The SQL comes from the server's copy of the answer."""
    report = saved_reports.save_from_message(db, user_id, body.message_id, body.title)
    db.commit()
    return _out(report)


@router.get("", response_model=list[ReportOut])
def list_reports(db: DB, user_id: CurrentUser, pinned: bool = False) -> list[ReportOut]:
    """Pinned first, then newest. `pinned=true` for the dashboard."""
    return [_out(r) for r in saved_reports.list_reports(db, user_id, pinned_only=pinned)]


@router.get("/{report_id}/run", response_model=ReportRunOut)
def run_report(report_id: int, db: DB, user_id: CurrentUser) -> ReportRunOut:
    """Run the report on today's data (no LLM; same guard as the chat)."""
    report, result, chart = saved_reports.run(db, user_id, report_id)
    db.commit()
    return ReportRunOut(
        report=_out(report),
        chart=ChartSpec(**chart) if chart else None,
        columns=result["columns"],
        rows=result["rows"],
        truncated=result["truncated"],
        run_at=report.last_run_at or dt.datetime.now(dt.UTC).replace(tzinfo=None),
    )


@router.get(
    "/{report_id}/export.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}, "description": "UTF-8 CSV with a BOM"}},
)
def export_report(report_id: int, db: DB, user_id: CurrentUser) -> Response:
    report, result, _chart = saved_reports.run(db, user_id, report_id)
    db.commit()
    return Response(
        content=saved_reports.to_csv(result),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="kasa-report-{report.id}.csv"'},
    )


@router.patch("/{report_id}", response_model=ReportOut)
def update_report(report_id: int, body: ReportUpdateIn, db: DB, user_id: CurrentUser) -> ReportOut:
    """Rename, or pin to / unpin from the dashboard (at most four pinned)."""
    report = saved_reports.update(db, user_id, report_id, title=body.title, pinned=body.pinned)
    db.commit()
    return _out(report)


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: int, db: DB, user_id: CurrentUser) -> None:
    saved_reports.delete(db, user_id, report_id)
    db.commit()
