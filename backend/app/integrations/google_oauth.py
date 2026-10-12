"""Google OAuth 2.0 (web server flow) for Gmail read + Calendar events (owner: track INGEST).

Flow: GET /integrations/google/connect -> `authorization_url(user_id)` (access_type=offline,
prompt=consent, include_granted_scopes=true, signed `state`) -> Google -> GET
/integrations/google/callback?code&state -> `read_state` + `exchange_code` + `save_account`
-> redirect to {frontend_url}/settings?google=connected.

`state` is a Fernet token (AES + HMAC-SHA256 with a timestamp, key TOKEN_ENCRYPTION_KEY), so
it is signed, opaque and expires after STATE_MAX_AGE_SECONDS. It carries the Kasa user id.

The refresh token is stored encrypted (`services.crypto`). `credentials_for_user` is the one
function other tracks use (HOUSE for Calendar, INGEST for Gmail): it returns google-auth
Credentials whose `token` is a fresh access token (refreshed here with plain httpx and
cached in memory until shortly before it expires). If Google says the refresh token is dead
(`invalid_grant`: revoked, expired, password change), the account row is deleted and the
function returns None, exactly as if the user had never connected.

All HTTP goes through `http_client()`, which tests replace with an httpx.MockTransport.
Tokens are never logged.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import secrets
import threading
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import GoogleAccount
from app.db.session import session_for
from app.services import crypto
from app.services.errors import DomainError, InvalidInput, NotConfigured, UpstreamError

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
STATE_MAX_AGE_SECONDS = 600

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
_ID_TOKEN_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
_STATE_PURPOSE = "kasa-google-oauth"
# Refresh a cached access token this long before Google's expiry.
_EXPIRY_MARGIN = dt.timedelta(seconds=120)


def http_client() -> httpx.Client:
    """HTTP client for every Google OAuth call. Tests monkeypatch this."""
    return httpx.Client(timeout=httpx.Timeout(15.0))


@dataclass
class GoogleTokens:
    refresh_token: str
    access_token: str
    google_email: str  # from the id_token (openid email scope)
    scopes: list[str]
    expires_in: int = 3600


def _require_config():
    settings = get_settings()
    if not settings.google_oauth_enabled:
        raise NotConfigured(
            "Google connection is not configured on the server "
            "(GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, TOKEN_ENCRYPTION_KEY)"
        )
    return settings


def has_scope(account: GoogleAccount | None, scope: str) -> bool:
    return account is not None and scope in (account.scopes or "").split()


# --- state ---------------------------------------------------------------------------------


def make_state(user_id: str) -> str:
    _require_config()
    payload = {"p": _STATE_PURPOSE, "uid": user_id, "n": secrets.token_urlsafe(12)}
    return crypto.encrypt(json.dumps(payload, separators=(",", ":")))


def authorization_url(user_id: str) -> str:
    """Consent-screen URL. `state` = crypto.encrypt(json {uid, nonce}); checked with
    max_age_seconds=STATE_MAX_AGE_SECONDS in `read_state`. Raises NotConfigured when
    settings.google_oauth_enabled is false."""
    settings = _require_config()
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(settings.google_oauth_scopes),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": make_state(user_id),
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def read_state(state: str) -> str:
    """Return the user id inside a state value; InvalidInput if forged or expired."""
    _require_config()
    try:
        payload = json.loads(crypto.decrypt(state, max_age_seconds=STATE_MAX_AGE_SECONDS))
    except (crypto.CryptoError, ValueError) as exc:
        raise InvalidInput("the Google sign-in link is invalid or expired; start again") from exc
    uid = payload.get("uid") if isinstance(payload, dict) else None
    if payload.get("p") != _STATE_PURPOSE or not isinstance(uid, str) or not uid:
        raise InvalidInput("the Google sign-in link is invalid or expired; start again")
    return uid


# --- token endpoint ------------------------------------------------------------------------


def _post_token(data: dict[str, str]) -> dict:
    """POST to the token endpoint. Returns the JSON body for 200, raises otherwise.
    `_TokenRejected` carries Google's error code (e.g. invalid_grant) for 400/401."""
    try:
        with http_client() as client:
            r = client.post(TOKEN_URL, data=data, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise UpstreamError(f"could not reach Google ({type(exc).__name__})") from exc
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code == 200 and isinstance(body, dict):
        return body
    code = str(body.get("error") or "") if isinstance(body, dict) else ""
    if r.status_code in (400, 401) and code:
        raise _TokenRejected(code)
    raise UpstreamError(f"Google token endpoint answered HTTP {r.status_code}")


class _TokenRejected(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _jwt_claims(token: str) -> dict:
    try:
        payload = token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as exc:
        raise UpstreamError("Google returned an unreadable id_token") from exc


def _email_from_id_token(id_token: str, client_id: str) -> str | None:
    """The id_token came straight from Google's token endpoint over TLS, so per OpenID
    Connect Core 3.1.3.7 the TLS check stands in for the signature check. We still check
    issuer, audience, expiry and that the email is verified."""
    claims = _jwt_claims(id_token)
    if claims.get("iss") not in _ID_TOKEN_ISSUERS or claims.get("aud") != client_id:
        raise UpstreamError("Google returned an id_token for another client")
    if int(claims.get("exp") or 0) < dt.datetime.now(dt.UTC).timestamp() - 60:
        raise UpstreamError("Google returned an expired id_token")
    if claims.get("email") and claims.get("email_verified") in (True, "true"):
        return str(claims["email"])
    return None


def _email_from_userinfo(access_token: str) -> str | None:
    try:
        with http_client() as client:
            r = client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    except httpx.HTTPError as exc:
        raise UpstreamError(f"could not reach Google ({type(exc).__name__})") from exc
    if r.status_code != 200:
        raise UpstreamError(f"Google userinfo answered HTTP {r.status_code}")
    data = r.json()
    if data.get("email") and data.get("email_verified") in (True, "true"):
        return str(data["email"])
    return None


def exchange_code(code: str) -> GoogleTokens:
    """POST the code to TOKEN_URL; read the email from the id_token (or userinfo);
    UpstreamError on failure. InvalidInput if Google returned no refresh token or neither
    Gmail nor Calendar access was granted (Google lets users untick scopes)."""
    settings = _require_config()
    if not code:
        raise InvalidInput("missing authorization code")
    try:
        body = _post_token(
            {
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "grant_type": "authorization_code",
            }
        )
    except _TokenRejected as exc:
        if exc.code == "invalid_grant":
            raise InvalidInput("the Google authorization code is invalid or expired; connect again") from exc
        raise UpstreamError(f"Google refused the code exchange ({exc.code})") from exc

    access_token = str(body.get("access_token") or "")
    refresh_token = str(body.get("refresh_token") or "")
    scopes = str(body.get("scope") or "").split()
    if not access_token:
        raise UpstreamError("Google returned no access token")
    if not refresh_token:
        raise InvalidInput("Google returned no refresh token; remove Kasa at myaccount.google.com and retry")
    if GMAIL_SCOPE not in scopes and CALENDAR_SCOPE not in scopes:
        _revoke(refresh_token)
        raise InvalidInput("Kasa needs Gmail or Calendar access; tick at least one box on Google's screen")

    email = None
    if body.get("id_token"):
        email = _email_from_id_token(str(body["id_token"]), settings.google_oauth_client_id)
    if not email:
        email = _email_from_userinfo(access_token)
    if not email:
        _revoke(refresh_token)
        raise InvalidInput("Google did not share a verified email address")
    return GoogleTokens(
        refresh_token=refresh_token,
        access_token=access_token,
        google_email=email,
        scopes=scopes,
        expires_in=int(body.get("expires_in") or 3600),
    )


# --- stored account ------------------------------------------------------------------------

# user_id -> (refresh_token_enc it was made from, access token, expiry naive UTC)
_token_cache: dict[str, tuple[str, str, dt.datetime]] = {}
_cache_lock = threading.Lock()


def _utcnow() -> dt.datetime:
    """Naive UTC, the convention of google-auth Credentials.expiry and our DateTime columns."""
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def _cache_put(user_id: str, refresh_enc: str, access_token: str, expires_in: int) -> dt.datetime:
    expiry = _utcnow() + dt.timedelta(seconds=max(60, expires_in))
    with _cache_lock:
        _token_cache[user_id] = (refresh_enc, access_token, expiry)
    return expiry


def _cache_drop(user_id: str) -> None:
    with _cache_lock:
        _token_cache.pop(user_id, None)


def save_account(db: Session, user_id: str, tokens: GoogleTokens) -> GoogleAccount:
    """Upsert the google_accounts row (refresh token encrypted) and commit."""
    _require_config()
    account = db.get(GoogleAccount, user_id)
    enc = crypto.encrypt(tokens.refresh_token)
    if account is None:
        account = GoogleAccount(user_id=user_id, google_email=tokens.google_email[:320])
        db.add(account)
    elif account.google_email.lower() != tokens.google_email.lower():
        # Another Google account: its mailbox has its own history and watch.
        account.gmail_history_id = None
        account.gmail_watch_expires_at = None
    account.google_email = tokens.google_email[:320]
    account.refresh_token_enc = enc
    account.scopes = " ".join(tokens.scopes)[:1000]
    db.commit()
    _cache_put(user_id, enc, tokens.access_token, tokens.expires_in)
    return account


def get_account(db: Session, user_id: str) -> GoogleAccount | None:
    return db.get(GoogleAccount, user_id)


def _forget_account(user_id: str) -> None:
    """Delete the row in its own session, so the caller's session is not committed."""
    _cache_drop(user_id)
    with session_for(user_id) as own:
        row = own.get(GoogleAccount, user_id)
        if row is not None:
            own.delete(row)
            own.commit()


def _credentials(account: GoogleAccount, refresh_token: str, access_token: str, expiry: dt.datetime):
    settings = get_settings()
    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=TOKEN_URL,
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=(account.scopes or "").split(),
        expiry=expiry,
    )


def credentials_for_user(db: Session, user_id: str) -> Credentials | None:
    """google.oauth2.credentials.Credentials for the user's connected account, or None if
    they have not connected Google (or Google revoked the grant, which disconnects them).

    `creds.token` is a valid access token for at least two more minutes. NotConfigured when
    the server lacks OAuth settings; UpstreamError when Google cannot be reached."""
    account = get_account(db, user_id)
    if account is None:
        return None
    settings = _require_config()
    try:
        refresh_token = crypto.decrypt(account.refresh_token_enc)
    except crypto.CryptoError as exc:
        raise NotConfigured("the stored Google token cannot be decrypted (key changed?); reconnect") from exc

    with _cache_lock:
        cached = _token_cache.get(user_id)
    if cached and cached[0] == account.refresh_token_enc and cached[2] - _EXPIRY_MARGIN > _utcnow():
        return _credentials(account, refresh_token, cached[1], cached[2])

    try:
        body = _post_token(
            {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            }
        )
    except _TokenRejected as exc:
        if exc.code in ("invalid_grant", "unauthorized_client"):
            log.info("Google grant for user %s is no longer valid; disconnecting", user_id)
            _forget_account(user_id)
            return None
        raise UpstreamError(f"Google refused the token refresh ({exc.code})") from exc
    access_token = str(body.get("access_token") or "")
    if not access_token:
        raise UpstreamError("Google returned no access token")
    expiry = _cache_put(user_id, account.refresh_token_enc, access_token, int(body.get("expires_in") or 3600))
    return _credentials(account, refresh_token, access_token, expiry)


def _revoke(token: str) -> bool:
    try:
        with http_client() as client:
            r = client.post(
                REVOKE_URL,
                data={"token": token},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError:
        return False
    return r.status_code == 200


def disconnect(db: Session, user_id: str) -> None:
    """Stop the Gmail watch, revoke the token at Google (best effort), delete the row."""
    account = get_account(db, user_id)
    if account is None:
        return
    if account.gmail_watch_expires_at is not None and has_scope(account, GMAIL_SCOPE):
        from app.integrations import gmail

        try:
            creds = credentials_for_user(db, user_id)
            if creds is not None:
                gmail.stop_watch(creds)
        except DomainError as exc:  # best effort: the watch expires by itself within 7 days
            log.info("could not stop the Gmail watch for %s: %s", user_id, type(exc).__name__)
    account = get_account(db, user_id)  # credentials_for_user may have removed it
    if account is None:
        return
    try:
        refresh_token = crypto.decrypt(account.refresh_token_enc)
    except crypto.CryptoError:
        refresh_token = ""
    if refresh_token and not _revoke(refresh_token):
        log.info("token revocation for %s did not succeed; deleting the row anyway", user_id)
    db.delete(account)
    db.commit()
    _cache_drop(user_id)
