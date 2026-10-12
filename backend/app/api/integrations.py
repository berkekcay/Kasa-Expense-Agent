"""Google account connection for Gmail + Calendar (owner: track INGEST).

The callback is hit by the browser coming back from Google, so it carries no Kasa auth
header; the user is identified by the signed `state` value instead. A frontend-hosted
redirect page can use POST /integrations/google/exchange instead, which also checks that
the signed-in user is the one who started the flow.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import RedirectResponse

from app.auth import DB, CurrentUser
from app.config import get_settings
from app.db.session import session_for
from app.integrations import google_oauth
from app.schemas.integrations import GoogleConnectOut, GoogleExchangeIn, GoogleStatusOut, SyncResultOut
from app.services import gmail_sync
from app.services.errors import DomainError, Forbidden, InvalidInput, NotConfigured
from app.services.expenses import ensure_user

log = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google", tags=["integrations"])


def _status(db, user_id: str) -> GoogleStatusOut:
    account = google_oauth.get_account(db, user_id)
    scopes = (account.scopes or "").split() if account else []
    return GoogleStatusOut(
        configured=get_settings().google_oauth_enabled,
        connected=account is not None,
        google_email=account.google_email if account else None,
        scopes=scopes,
        gmail_access=google_oauth.GMAIL_SCOPE in scopes,
        calendar_access=google_oauth.CALENDAR_SCOPE in scopes,
        gmail_watch_expires_at=account.gmail_watch_expires_at if account else None,
    )


async def _first_sync(user_id: str) -> None:
    try:
        await gmail_sync.sync_user(user_id)
    except Exception:
        log.exception("first Gmail sync failed for %s", user_id)


def _connect(user_id: str, code: str, background: BackgroundTasks) -> None:
    tokens = google_oauth.exchange_code(code)
    with session_for(user_id) as db:
        ensure_user(db, user_id)
        google_oauth.save_account(db, user_id, tokens)
    if google_oauth.GMAIL_SCOPE in tokens.scopes:
        try:  # push notifications; without them the hourly sync still runs
            gmail_sync.start_watch(user_id)
        except DomainError as exc:
            log.info("Gmail watch not started for %s: %s", user_id, type(exc).__name__)
        background.add_task(_first_sync, user_id)


@router.get("/connect", response_model=GoogleConnectOut)
def connect(user_id: CurrentUser) -> GoogleConnectOut:
    """URL of Google's consent screen for the current user."""
    return GoogleConnectOut(url=google_oauth.authorization_url(user_id))


@router.get("/callback", include_in_schema=False)
def callback(
    background: BackgroundTasks, code: str = "", state: str = "", error: str = ""
) -> RedirectResponse:
    """Exchange the code, store the encrypted refresh token, start the Gmail watch, then
    redirect to {frontend_url}/settings?google=connected (or ?google=error&reason=...)."""
    base = get_settings().frontend_url.rstrip("/") + "/settings?"

    def back(**params: str) -> RedirectResponse:
        return RedirectResponse(base + urlencode(params), status_code=303)

    if error:  # the user pressed Cancel, or Google refused
        return back(google="error", reason="denied" if error == "access_denied" else "google")
    try:
        user_id = google_oauth.read_state(state)
        _connect(user_id, code, background)
    except InvalidInput as exc:
        log.info("Google connect refused: %s", exc)
        return back(google="error", reason="scopes" if "access" in str(exc) else "invalid")
    except NotConfigured:
        return back(google="error", reason="not_configured")
    except DomainError as exc:
        log.warning("Google connect failed: %s", exc)
        return back(google="error", reason="google")
    return back(google="connected")


@router.post("/exchange", response_model=GoogleStatusOut)
def exchange(
    body: GoogleExchangeIn, background: BackgroundTasks, db: DB, user_id: CurrentUser
) -> GoogleStatusOut:
    """Finish the flow from a frontend redirect page (signed-in user must match the state)."""
    if google_oauth.read_state(body.state) != user_id:
        raise Forbidden("this Google sign-in was started by another user")
    _connect(user_id, body.code, background)
    db.expire_all()
    return _status(db, user_id)


@router.get("/status", response_model=GoogleStatusOut)
def status(db: DB, user_id: CurrentUser) -> GoogleStatusOut:
    return _status(db, user_id)


@router.post("/sync", response_model=SyncResultOut)
async def sync_now(user_id: CurrentUser) -> SyncResultOut:
    """Manual "check my email now" button."""
    result = await gmail_sync.sync_user(user_id)
    return SyncResultOut(
        fetched=result.fetched,
        created=result.created,
        ignored=result.ignored,
        duplicates=result.duplicates,
        failed=result.failed,
        error=result.error,
    )


@router.delete("", status_code=204)
def disconnect(db: DB, user_id: CurrentUser) -> None:
    google_oauth.disconnect(db, user_id)
