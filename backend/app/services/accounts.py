"""Kasa accounts: register, sign in, mandatory 2FA, sessions (owner: shared).

Every account has Google Authenticator (TOTP) 2FA; there is no way to finish signing in
without it. The flow is a small state machine carried in a signed, ten-minute "pending"
token (`security.sign`), so nothing half-finished is stored:

    register / password ok / Google ok
        -> pending(step="totp_setup") when the account has no 2FA yet
           -> setup_totp (secret + QR) -> confirm_totp -> session + recovery codes
        -> pending(step="totp") when it has
           -> verify_login (TOTP code or a one-time recovery code) -> session

Five wrong passwords or codes in a row lock the account for fifteen minutes. Sessions are
random bearer tokens; only their SHA-256 is stored, and they can be listed and revoked.
The TOTP secret is stored Fernet-encrypted (`services.crypto`), passwords as scrypt hashes.

Lookups that happen before we know who the user is (email at sign-in, a session token on
every request) read `users` (no RLS) or run in a system session for `auth_sessions`.
"""

from __future__ import annotations

import datetime as dt
import re
import secrets
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AuthSession, RecoveryCode, User
from app.services import crypto, security
from app.services.errors import BadRequest, Conflict, InvalidInput, Locked, NotFound, Unauthenticated

PENDING_TTL_SECONDS = 600
PENDING_PURPOSE = "kasa-login"
MAX_FAILURES = 5
LOCK_MINUTES = 15
LAST_SEEN_EVERY = dt.timedelta(minutes=5)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if not _EMAIL.match(value) or len(value) > 320:
        raise BadRequest("enter a valid email address")
    return value


def find_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.login_email == email))


@dataclass
class Pending:
    user_id: str
    step: str  # "totp" or "totp_setup"
    token: str


def pending_for(user: User) -> Pending:
    step = "totp" if user.totp_enabled_at else "totp_setup"
    token = security.sign(PENDING_PURPOSE, {"uid": user.id, "step": step}, PENDING_TTL_SECONDS)
    return Pending(user_id=user.id, step=step, token=token)


def read_pending(db: Session, token: str, step: str) -> User:
    body = security.unsign(PENDING_PURPOSE, token or "")
    if not body or body.get("step") != step:
        raise Unauthenticated("this sign-in step has expired; start again")
    user = db.get(User, str(body.get("uid", "")))
    if user is None:
        raise Unauthenticated("this sign-in step has expired; start again")
    # A setup token made before 2FA was turned on must not be able to replace the secret.
    if step == "totp_setup" and user.totp_enabled_at is not None:
        raise Unauthenticated("this sign-in step has expired; start again")
    _check_lock(user)
    return user


def _check_lock(user: User) -> None:
    if user.locked_until and user.locked_until > _now():
        until = user.locked_until.strftime("%H:%M")
        raise Locked(f"too many failed attempts; try again after {until} UTC")


def _failed(db: Session, user: User) -> None:
    user.failed_logins = (user.failed_logins or 0) + 1
    if user.failed_logins >= MAX_FAILURES:
        user.locked_until = _now() + dt.timedelta(minutes=LOCK_MINUTES)
        user.failed_logins = 0
    db.commit()


def _succeeded(user: User) -> None:
    user.failed_logins = 0
    user.locked_until = None


# --- register and password sign-in ----------------------------------------------------------


def register(db: Session, email: str, password: str, display_name: str) -> Pending:
    email = normalize_email(email)
    problem = security.password_problem(password)
    if problem:
        raise BadRequest(problem)
    name = " ".join(display_name.split())[:100]
    if not name:
        raise InvalidInput("enter your name")
    if find_by_email(db, email):
        raise Conflict("an account with this email already exists; sign in instead")
    user = User(
        id="u_" + secrets.token_hex(8),
        display_name=name,
        email=email,
        login_email=email,
        password_hash=security.hash_password(password),
    )
    db.add(user)
    db.flush()
    return pending_for(user)


def start_login(db: Session, email: str, password: str) -> Pending:
    try:
        email = normalize_email(email)
    except BadRequest as exc:
        raise Unauthenticated("wrong email or password") from exc
    user = find_by_email(db, email)
    if user is not None:
        _check_lock(user)
    # Always hash, so a missing account takes as long as a wrong password.
    ok = security.verify_password(password, user.password_hash if user else None)
    if user is None or not ok:
        if user is not None:
            _failed(db, user)
        raise Unauthenticated("wrong email or password")
    return pending_for(user)


# --- 2FA ------------------------------------------------------------------------------------


@dataclass
class TotpSetup:
    secret: str
    otpauth_uri: str
    qr_svg: str


def setup_totp(db: Session, pending_token: str) -> TotpSetup:
    """A new secret for an account that has no 2FA yet. Calling it again replaces the secret
    (the user scanned the old QR into a lost phone, or closed the tab)."""
    user = read_pending(db, pending_token, "totp_setup")
    secret = security.new_totp_secret()
    user.totp_secret_enc = crypto.encrypt(secret)
    db.flush()
    uri = security.otpauth_uri(secret, user.login_email or user.display_name)
    return TotpSetup(secret=secret, otpauth_uri=uri, qr_svg=security.qr_svg(uri))


def _secret(user: User) -> str:
    if not user.totp_secret_enc:
        raise BadRequest("set up the authenticator app first")
    return crypto.decrypt(user.totp_secret_enc)


def _check_code(db: Session, user: User, code: str) -> None:
    step = security.verify_totp(_secret(user), code, last_step=user.totp_last_step)
    if step is None:
        _failed(db, user)
        raise BadRequest("that code is not right; check the time on your phone and try again")
    user.totp_last_step = step


@dataclass
class SignedIn:
    user: User
    token: str
    expires_at: dt.datetime
    recovery_codes: list[str] | None = None


def confirm_totp(db: Session, pending_token: str, code: str, user_agent: str | None) -> SignedIn:
    user = read_pending(db, pending_token, "totp_setup")
    _check_code(db, user, code)
    user.totp_enabled_at = _now()
    _succeeded(user)
    codes = replace_recovery_codes(db, user.id)
    signed = create_session(db, user, user_agent)
    signed.recovery_codes = codes
    return signed


def verify_login(
    db: Session, pending_token: str, user_agent: str | None, code: str = "", recovery_code: str = ""
) -> SignedIn:
    user = read_pending(db, pending_token, "totp")
    if recovery_code:
        _use_recovery_code(db, user, recovery_code)
    else:
        _check_code(db, user, code)
    _succeeded(user)
    return create_session(db, user, user_agent)


def replace_recovery_codes(db: Session, user_id: str) -> list[str]:
    db.query(RecoveryCode).filter(RecoveryCode.user_id == user_id).delete()
    codes = security.new_recovery_codes()
    db.add_all(RecoveryCode(user_id=user_id, code_hash=security.sha256(c)) for c in codes)
    db.flush()
    return codes


def _use_recovery_code(db: Session, user: User, code: str) -> None:
    digest = security.sha256(security.normalize_recovery_code(code))
    row = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id, RecoveryCode.code_hash == digest, RecoveryCode.used_at.is_(None)
        )
    )
    if row is None:
        _failed(db, user)
        raise BadRequest("that recovery code is not right or was already used")
    row.used_at = _now()


def regenerate_recovery_codes(db: Session, user_id: str, code: str) -> list[str]:
    user = db.get(User, user_id)
    if user is None or not user.totp_enabled_at:
        raise BadRequest("this account has no two-step verification")
    _check_lock(user)
    _check_code(db, user, code)
    return replace_recovery_codes(db, user_id)


def change_password(
    db: Session, user_id: str, current_session_id: int | None, current: str, new: str, code: str
) -> None:
    user = db.get(User, user_id)
    if user is None:
        raise NotFound("account not found")
    _check_lock(user)
    if user.password_hash and not security.verify_password(current, user.password_hash):
        _failed(db, user)
        raise BadRequest("the current password is not right")
    problem = security.password_problem(new)
    if problem:
        raise BadRequest(problem)
    _check_code(db, user, code)
    user.password_hash = security.hash_password(new)
    revoke_others(db, user_id, current_session_id)


# --- sessions -------------------------------------------------------------------------------


def create_session(db: Session, user: User, user_agent: str | None) -> SignedIn:
    token = security.new_session_token()
    expires = _now() + dt.timedelta(days=get_settings().session_days)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=security.sha256(token),
            user_agent=(user_agent or "")[:300] or None,
            expires_at=expires,
        )
    )
    db.flush()
    return SignedIn(user=user, token=token, expires_at=expires)


def session_for_token(db: Session, token: str) -> AuthSession | None:
    """The live session for a bearer token, or None. `db` must be a system session: we do not
    know the user yet. Touches last_seen_at at most every few minutes."""
    if not token.startswith(security.SESSION_PREFIX):
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == security.sha256(token)))
    now = _now()
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        return None
    if now - row.last_seen_at > LAST_SEEN_EVERY:
        db.execute(update(AuthSession).where(AuthSession.id == row.id).values(last_seen_at=now))
        db.commit()
    return row


def list_sessions(db: Session, user_id: str) -> list[AuthSession]:
    stmt = (
        select(AuthSession)
        .where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None), AuthSession.expires_at > _now()
        )
        .order_by(AuthSession.last_seen_at.desc())
    )
    return list(db.scalars(stmt))


def revoke(db: Session, user_id: str, session_id: int) -> None:
    row = db.scalar(select(AuthSession).where(AuthSession.id == session_id, AuthSession.user_id == user_id))
    if row is None:
        raise NotFound("session not found")
    row.revoked_at = _now()


def revoke_others(db: Session, user_id: str, keep_session_id: int | None) -> None:
    stmt = update(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    if keep_session_id is not None:
        stmt = stmt.where(AuthSession.id != keep_session_id)
    db.execute(stmt.values(revoked_at=_now()))


# --- Google sign-in -------------------------------------------------------------------------


def google_user(db: Session, sub: str, email: str, name: str | None) -> User:
    """The account for a verified Google identity: by Google subject, else a new account
    without a password. 2FA still follows.

    An existing password account with the same email is NOT linked automatically. Kasa does
    not verify email addresses at registration, so anyone could have registered someone
    else's address first and would then receive that person's Google sign-ins
    (pre-account takeover). That person signs in with the password instead."""
    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None and find_by_email(db, normalize_email(email)) is not None:
        raise Conflict("an account with this email already exists; sign in with your email and password")
    if user is None:
        email = normalize_email(email)
        user = User(
            id="u_" + secrets.token_hex(8),
            display_name=(name or email.split("@")[0])[:100],
            email=email,
            login_email=email,
            google_sub=sub,
        )
        db.add(user)
    db.flush()
    _check_lock(user)
    return user
