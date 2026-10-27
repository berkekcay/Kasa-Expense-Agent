"""Sign in with Google (OpenID Connect, web server flow) for Kasa accounts (owner: shared).

Uses the same OAuth client as the Gmail connection (`google_oauth`) with its own redirect URI
(GOOGLE_LOGIN_REDIRECT_URI) and only the `openid email profile` scopes, so signing in never
asks for Gmail. The `state` is signed by `security.sign` and carries where to go afterwards.
Google only proves who the person is; the Kasa 2FA code is still required after it.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from urllib.parse import urlencode

from app.config import get_settings
from app.integrations.google_oauth import AUTH_URL, _jwt_claims, _post_token, _TokenRejected
from app.services import security
from app.services.errors import InvalidInput, NotConfigured, UpstreamError

STATE_PURPOSE = "kasa-google-login"
STATE_TTL_SECONDS = 600
_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str | None


def _settings():
    settings = get_settings()
    if not settings.google_login_enabled:
        raise NotConfigured("Google sign-in is not set up on this server")
    return settings


def safe_next(path: str | None) -> str:
    """Only same-site paths, so the redirect after sign-in cannot be pointed elsewhere."""
    if path and path.startswith("/") and not path.startswith("//") and "\\" not in path:
        return path[:500]
    return "/"


def authorization_url(next_path: str | None) -> str:
    settings = _settings()
    state = security.sign(STATE_PURPOSE, {"next": safe_next(next_path)}, STATE_TTL_SECONDS)
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_login_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def read_state(state: str) -> str:
    body = security.unsign(STATE_PURPOSE, state or "")
    if body is None:
        raise InvalidInput("the Google sign-in link is invalid or expired; start again")
    return safe_next(body.get("next"))


def exchange(code: str) -> GoogleIdentity:
    """Code -> verified Google identity (subject, verified email, name)."""
    settings = _settings()
    if not code:
        raise InvalidInput("missing authorization code")
    try:
        body = _post_token(
            {
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": settings.google_login_redirect_uri,
                "grant_type": "authorization_code",
            }
        )
    except _TokenRejected as exc:
        raise InvalidInput("Google did not accept the sign-in; try again") from exc
    if not body.get("id_token"):
        raise UpstreamError("Google returned no id_token")
    # Straight from Google's token endpoint over TLS (OpenID Connect Core 3.1.3.7), so the
    # TLS check stands in for the signature; issuer, audience and expiry are still checked.
    claims = _jwt_claims(str(body["id_token"]))
    if claims.get("iss") not in _ISSUERS or claims.get("aud") != settings.google_oauth_client_id:
        raise UpstreamError("Google returned an id_token for another client")
    if int(claims.get("exp") or 0) < dt.datetime.now(dt.UTC).timestamp() - 60:
        raise UpstreamError("Google returned an expired id_token")
    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") not in (True, "true"):
        raise InvalidInput("Google did not share a verified email address")
    return GoogleIdentity(sub=str(claims["sub"]), email=str(claims["email"]), name=claims.get("name"))
