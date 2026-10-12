"""Who is calling?

- FIREBASE_PROJECT_ID set: every request needs `Authorization: Bearer <Firebase ID token>`.
  The token is verified with Google's public certs (cached), the user id is the Firebase
  `uid`, and the user's email / name from the token are saved on `users`.
- Not set (local dev, tests): the X-User-Id header says who is calling, falling back to
  DEV_DEFAULT_USER_ID. Never run like this in production.

Everything else depends only on `CurrentUser` / `DB`, so the rest of the app does not care.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import session_for
from app.services.expenses import ensure_user

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None = None
    name: str | None = None


@lru_cache
def _google_request():
    """A google-auth transport whose HTTP session caches Google's public certs according to
    their Cache-Control headers, so most requests verify tokens without a network call."""
    import cachecontrol
    import google.auth.transport.requests
    import requests

    session = cachecontrol.CacheControl(requests.session())
    return google.auth.transport.requests.Request(session=session)


def verify_firebase_token(token: str, project_id: str) -> dict[str, Any]:
    """Verify signature, expiry, issuer and audience; return the token claims.
    Tests monkeypatch this function."""
    from google.oauth2 import id_token

    return id_token.verify_firebase_token(
        token, _google_request(), audience=project_id, clock_skew_in_seconds=10
    )


def authenticate(
    authorization: Annotated[str | None, Header()] = None,
    x_user_id: Annotated[str | None, Header()] = None,
) -> Principal:
    settings = get_settings()
    if settings.firebase_project_id:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(
                status_code=401, detail="sign in required", headers={"WWW-Authenticate": "Bearer"}
            )
        try:
            claims = verify_firebase_token(token.strip(), settings.firebase_project_id)
        except Exception as exc:  # expired, wrong project, bad signature, cert fetch failed
            raise HTTPException(
                status_code=401, detail="invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
            ) from exc
        uid = str(claims.get("user_id") or claims.get("sub") or "")
        if not _USER_ID_RE.match(uid):
            raise HTTPException(status_code=401, detail="token has no usable user id")
        email = claims.get("email") if claims.get("email_verified", False) else None
        return Principal(user_id=uid, email=email, name=claims.get("name"))

    # DEV ONLY: trusts the X-User-Id header.
    user_id = (x_user_id or settings.dev_default_user_id).strip()
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(status_code=400, detail="invalid X-User-Id")
    return Principal(user_id=user_id)


CurrentPrincipal = Annotated[Principal, Depends(authenticate)]


def current_user_id(principal: CurrentPrincipal) -> str:
    return principal.user_id


CurrentUser = Annotated[str, Depends(current_user_id)]


def get_db(principal: CurrentPrincipal) -> Iterator[Session]:
    """A DB session acting as the current user (sets SESSION_CONTEXT on SQL Server).
    Creates the user row on first sight and keeps email/name from Firebase up to date."""
    with session_for(principal.user_id) as db:
        ensure_user(db, principal.user_id, principal.name, principal.email)
        db.commit()
        yield db


DB = Annotated[Session, Depends(get_db)]
