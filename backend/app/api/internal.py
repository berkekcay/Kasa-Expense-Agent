"""Machine-to-machine endpoints for Cloud Scheduler and Pub/Sub (finished; tracks only
implement the services these call).

- Cloud Scheduler jobs send `X-Kasa-Task-Token: <INTERNAL_TASK_TOKEN>`.
- The Gmail Pub/Sub push subscription sends a Google-signed OIDC token
  (`Authorization: Bearer ...`) with audience PUBSUB_PUSH_AUDIENCE, issued to the service
  account PUBSUB_PUSH_SERVICE_ACCOUNT.
Both return 503 while their settings are empty, so nothing is open by default.
"""

from __future__ import annotations

import base64
import hmac
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from app.config import get_settings
from app.db.session import session_for
from app.services import fx, gmail_sync

log = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


def require_task_token(x_kasa_task_token: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().internal_task_token
    if not expected:
        raise HTTPException(status_code=503, detail="internal endpoints are disabled (INTERNAL_TASK_TOKEN)")
    if not x_kasa_task_token or not hmac.compare_digest(x_kasa_task_token, expected):
        raise HTTPException(status_code=401, detail="bad task token")


def verify_pubsub_token(token: str, audience: str) -> dict[str, Any]:
    """Verify a Google-signed OIDC token; tests monkeypatch this function."""
    from google.oauth2 import id_token

    from app.auth import _google_request

    return id_token.verify_oauth2_token(token, _google_request(), audience=audience, clock_skew_in_seconds=10)


def require_pubsub_push(authorization: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    if not (settings.pubsub_push_audience and settings.pubsub_push_service_account):
        raise HTTPException(status_code=503, detail="Pub/Sub push is not configured")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="missing push token")
    try:
        claims = verify_pubsub_token(token, settings.pubsub_push_audience)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid push token") from exc
    if claims.get("email") != settings.pubsub_push_service_account or not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="push token from an unexpected service account")


TaskAuth = Depends(require_task_token)


@router.post("/gmail/sync-all", dependencies=[TaskAuth])
async def gmail_sync_all() -> dict:
    results = await gmail_sync.sync_all()
    return {"accounts": len(results), "created": sum(r.created for r in results)}


@router.post("/gmail/renew-watches", dependencies=[TaskAuth])
def gmail_renew_watches() -> dict:
    return {"renewed": gmail_sync.renew_watches()}


@router.post("/fx/refresh", dependencies=[TaskAuth])
def fx_refresh() -> dict:
    with session_for(None, system=True) as db:
        return {"rates": fx.refresh_rates(db)}


@router.post("/gmail/push", status_code=204, dependencies=[Depends(require_pubsub_push)])
async def gmail_push(request: Request) -> Response:
    """Gmail -> Pub/Sub -> here. Body: {"message": {"data": base64(json{emailAddress,
    historyId})}}. Malformed messages are acknowledged (204) so Pub/Sub does not retry them
    forever; a failing sync returns 500 so Pub/Sub retries later."""
    try:
        envelope = await request.json()
        payload = json.loads(base64.b64decode(envelope["message"]["data"]))
        email, history_id = str(payload["emailAddress"]), str(payload["historyId"])
    except (ValueError, KeyError, TypeError):
        log.warning("ignoring malformed Gmail push message")
        return Response(status_code=204)
    await gmail_sync.handle_push(email, history_id)
    return Response(status_code=204)
