"""Home dashboard (owner: track MONEY)."""

import datetime as dt

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.dashboard import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut, summary="Home page numbers")
def get_dashboard(db: DB, user_id: CurrentUser, month: dt.date | None = None) -> DashboardOut:
    """Totals, categories, 6-month trend, budgets, house balances, upcoming subscription
    charges, recent expenses and the pending inbox count for the month containing `month`
    (default: this month). Plain SQL, no LLM."""
    summary = dashboard_service.dashboard_summary(db, user_id, month)
    db.commit()  # keeps any exchange rate fetched while converting
    return DashboardOut.from_summary(summary)
