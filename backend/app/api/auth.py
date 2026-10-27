"""Kasa accounts: register, sign in with password or Google, mandatory 2FA, sessions
(owner: shared). The rules live in `services.accounts`; this file is the HTTP shape.

The steps before a session exists run in a system DB session: the user is not known yet,
and on SQL Server the sessions and recovery-code tables allow the system to write them.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import DB, CurrentPrincipal
from app.config import get_settings
from app.db.session import session_for
from app.integrations import google_signin
from app.schemas.users import MeOut
from app.services import accounts
from app.services.errors import DomainError

router = APIRouter(prefix="/auth", tags=["auth"])


def get_system_db() -> Iterator[Session]:
    with session_for(None, system=True) as db:
        yield db


SystemDB = Annotated[Session, Depends(get_system_db)]
UserAgent = Annotated[str | None, Header()]


class RegisterIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)
    display_name: str = Field(min_length=1, max_length=100)
    accept_terms: bool


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(max_length=256)


class PendingOut(BaseModel):
    pending_token: str
    step: str = Field(description="totp: enter the code; totp_setup: set up the authenticator first")


class PendingIn(BaseModel):
    pending_token: str


class TotpSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class CodeIn(BaseModel):
    pending_token: str
    code: str = Field(default="", max_length=16)


class VerifyIn(BaseModel):
    pending_token: str
    code: str = Field(default="", max_length=16)
    recovery_code: str = Field(default="", max_length=32)


class SessionOut(BaseModel):
    token: str
    expires_at: str
    user: MeOut
    recovery_codes: list[str] | None = None


class SessionInfo(BaseModel):
    id: int
    user_agent: str | None
    created_at: str
    last_seen_at: str
    expires_at: str
    current: bool


class RecoveryIn(BaseModel):
    code: str = Field(max_length=16)


class RecoveryOut(BaseModel):
    recovery_codes: list[str]


class PasswordIn(BaseModel):
    current_password: str = Field(default="", max_length=256)
    new_password: str = Field(max_length=256)
    code: str = Field(max_length=16)


def _pending(p: accounts.Pending) -> PendingOut:
    return PendingOut(pending_token=p.token, step=p.step)


def _signed_in(s: accounts.SignedIn) -> SessionOut:
    return SessionOut(
        token=s.token,
        expires_at=s.expires_at.isoformat() + "Z",
        user=MeOut.from_model(s.user),
        recovery_codes=s.recovery_codes,
    )


@router.post("/register", response_model=PendingOut, status_code=201)
def register(body: RegisterIn, db: SystemDB) -> PendingOut:
    """New account with email and password. Next: set up the authenticator (mandatory)."""
    if not body.accept_terms:
        raise HTTPException(status_code=400, detail="accept the privacy notice and the terms to continue")
    pending = accounts.register(db, body.email, body.password, body.display_name)
    db.commit()
    return _pending(pending)


@router.post("/login", response_model=PendingOut)
def login(body: LoginIn, db: SystemDB) -> PendingOut:
    """Email and password. 401 if wrong, 423 while locked after five failures."""
    pending = accounts.start_login(db, body.email, body.password)
    db.commit()
    return _pending(pending)


@router.post("/totp/setup", response_model=TotpSetupOut)
def totp_setup(body: PendingIn, db: SystemDB) -> TotpSetupOut:
    """A new authenticator secret with its QR code, for an account without 2FA yet."""
    setup = accounts.setup_totp(db, body.pending_token)
    db.commit()
    return TotpSetupOut(secret=setup.secret, otpauth_uri=setup.otpauth_uri, qr_svg=setup.qr_svg)


@router.post("/totp/confirm", response_model=SessionOut)
def totp_confirm(body: CodeIn, db: SystemDB, user_agent: UserAgent = None) -> SessionOut:
    """The first code from the app turns 2FA on and signs in. The ten recovery codes are
    returned once, here only."""
    signed = accounts.confirm_totp(db, body.pending_token, body.code, user_agent)
    db.commit()
    return _signed_in(signed)


@router.post("/login/verify", response_model=SessionOut)
def login_verify(body: VerifyIn, db: SystemDB, user_agent: UserAgent = None) -> SessionOut:
    """The 2FA step: a code from the app, or one of the recovery codes (each works once)."""
    signed = accounts.verify_login(
        db, body.pending_token, user_agent, code=body.code, recovery_code=body.recovery_code
    )
    db.commit()
    return _signed_in(signed)


@router.get("/google/start", include_in_schema=True)
def google_start(next: str = "/") -> RedirectResponse:
    """Redirect to Google's account chooser."""
    return RedirectResponse(google_signin.authorization_url(next), status_code=307)


@router.get("/google/callback")
def google_callback(db: SystemDB, code: str = "", state: str = "", error: str = "") -> RedirectResponse:
    """Google sends the browser back here; we send it on to the web app's 2FA step with a
    pending token in the URL fragment (fragments never reach server logs)."""
    base = get_settings().frontend_url.rstrip("/") + "/login/continue"
    try:
        if error:
            raise DomainError("Google sign-in was cancelled")
        next_path = google_signin.read_state(state)
        identity = google_signin.exchange(code)
        user = accounts.google_user(db, identity.sub, identity.email, identity.name)
        pending = accounts.pending_for(user)
        db.commit()
    except DomainError as exc:
        return RedirectResponse(f"{base}#error={quote(str(exc))}", status_code=303)
    fragment = f"pending={quote(pending.token)}&step={pending.step}&next={quote(next_path)}"
    return RedirectResponse(f"{base}#{fragment}", status_code=303)


@router.post("/logout", status_code=204)
def logout(principal: CurrentPrincipal, db: DB) -> None:
    """End this session (the token stops working right away)."""
    if principal.session_id is not None:
        accounts.revoke(db, principal.user_id, principal.session_id)
        db.commit()


@router.get("/sessions", response_model=list[SessionInfo])
def sessions(principal: CurrentPrincipal, db: DB) -> list[SessionInfo]:
    """Signed-in devices, most recently used first."""
    return [
        SessionInfo(
            id=s.id,
            user_agent=s.user_agent,
            created_at=s.created_at.isoformat() + "Z",
            last_seen_at=s.last_seen_at.isoformat() + "Z",
            expires_at=s.expires_at.isoformat() + "Z",
            current=s.id == principal.session_id,
        )
        for s in accounts.list_sessions(db, principal.user_id)
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, principal: CurrentPrincipal, db: DB) -> None:
    accounts.revoke(db, principal.user_id, session_id)
    db.commit()


@router.post("/recovery-codes", response_model=RecoveryOut)
def recovery_codes(body: RecoveryIn, principal: CurrentPrincipal, db: DB) -> RecoveryOut:
    """New recovery codes (the old ones stop working). Needs a current 2FA code."""
    codes = accounts.regenerate_recovery_codes(db, principal.user_id, body.code)
    db.commit()
    return RecoveryOut(recovery_codes=codes)


@router.post("/password", status_code=204)
def change_password(body: PasswordIn, principal: CurrentPrincipal, db: DB) -> None:
    """Set a new password (needs the current one, if any, and a 2FA code). Every other
    session is signed out."""
    accounts.change_password(
        db, principal.user_id, principal.session_id, body.current_password, body.new_password, body.code
    )
    db.commit()
