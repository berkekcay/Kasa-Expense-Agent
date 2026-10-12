"""Home dashboard (owner: track MONEY)."""

import datetime as dt

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.dashboard import DashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(db: DB, user_id: CurrentUser, month: dt.date | None = None) -> DashboardOut:
    dashboard_service.dashboard_summary(db, user_id, month)
    raise NotImplementedError("GET /dashboard: track MONEY")
