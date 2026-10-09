"""Who is calling? Sprint 1 uses a dev header; swap this one module for Firebase later.

Everything else depends only on `CurrentUser` / `get_db`, so replacing
`current_user_id` with Firebase ID-token verification touches nothing else.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import session_for
from app.services.expenses import ensure_user

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")


def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> str:
    """DEV ONLY: trusts the X-User-Id header. TODO(sprint 2): verify a Firebase ID token
    from `Authorization: Bearer ...` with firebase_admin.auth.verify_id_token instead."""
    user_id = (x_user_id or get_settings().dev_default_user_id).strip()
    if not _USER_ID_RE.match(user_id):
        raise HTTPException(status_code=400, detail="invalid X-User-Id")
    return user_id


CurrentUser = Annotated[str, Depends(current_user_id)]


def get_db(user_id: CurrentUser) -> Iterator[Session]:
    """A DB session acting as the current user (sets SESSION_CONTEXT on SQL Server)."""
    with session_for(user_id) as db:
        ensure_user(db, user_id)
        db.commit()
        yield db


DB = Annotated[Session, Depends(get_db)]
