"""Google account connection for Gmail + Calendar (owner: track INGEST).

The callback is hit by the browser coming back from Google, so it carries no Kasa auth
header; the user is identified by the signed `state` value instead.
"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from app.auth import DB, CurrentUser
from app.schemas.integrations import GoogleConnectOut, GoogleStatusOut, SyncResultOut

router = APIRouter(prefix="/integrations/google", tags=["integrations"])


@router.get("/connect", response_model=GoogleConnectOut)
def connect(user_id: CurrentUser) -> GoogleConnectOut:
    """URL of Google's consent screen for the current user."""
    raise NotImplementedError("GET /integrations/google/connect: track INGEST")


@router.get("/callback", include_in_schema=False)
def callback(code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    """Exchange the code, store the encrypted refresh token, start the Gmail watch, then
    redirect to {frontend_url}/settings?google=connected (or ?google=error)."""
    raise NotImplementedError("GET /integrations/google/callback: track INGEST")


@router.get("/status", response_model=GoogleStatusOut)
def status(db: DB, user_id: CurrentUser) -> GoogleStatusOut:
    raise NotImplementedError("GET /integrations/google/status: track INGEST")


@router.post("/sync", response_model=SyncResultOut)
async def sync_now(user_id: CurrentUser) -> SyncResultOut:
    """Manual "check my email now" button."""
    raise NotImplementedError("POST /integrations/google/sync: track INGEST")


@router.delete("", status_code=204)
def disconnect(db: DB, user_id: CurrentUser) -> None:
    raise NotImplementedError("DELETE /integrations/google: track INGEST")
