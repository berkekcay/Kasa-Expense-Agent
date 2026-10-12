"""Google OAuth 2.0 (web server flow) for Gmail read + Calendar events (owner: track INGEST).

Flow: GET /integrations/google/connect -> `authorization_url(user_id)` (access_type=offline,
prompt=consent, include_granted_scopes=true, signed `state`) -> Google -> GET
/integrations/google/callback?code&state -> `read_state` + `exchange_code` + `save_account`
-> redirect to {frontend_url}/settings?google=connected.

The refresh token is stored encrypted (`services.crypto`). `credentials_for_user` is the one
function other tracks use (HOUSE for Calendar, INGEST for Gmail): it returns ready-to-use
google-auth Credentials, refreshed on demand by google-auth itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.db.models import GoogleAccount

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
STATE_MAX_AGE_SECONDS = 600


@dataclass
class GoogleTokens:
    refresh_token: str
    access_token: str
    google_email: str  # from the id_token (openid email scope)
    scopes: list[str]


def authorization_url(user_id: str) -> str:
    """Consent-screen URL. `state` = crypto.encrypt(json {uid, nonce}); checked with
    max_age_seconds=STATE_MAX_AGE_SECONDS in `read_state`. Raises NotConfigured when
    settings.google_oauth_enabled is false."""
    raise NotImplementedError("authorization_url: track INGEST")


def read_state(state: str) -> str:
    """Return the user id inside a state value; InvalidInput if forged or expired."""
    raise NotImplementedError("read_state: track INGEST")


def exchange_code(code: str) -> GoogleTokens:
    """POST the code to TOKEN_URL; verify the id_token; UpstreamError on failure.
    InvalidInput if Google returned no refresh token or a required scope was not granted."""
    raise NotImplementedError("exchange_code: track INGEST")


def save_account(db: Session, user_id: str, tokens: GoogleTokens) -> GoogleAccount:
    """Upsert the google_accounts row (refresh token encrypted) and commit."""
    raise NotImplementedError("save_account: track INGEST")


def get_account(db: Session, user_id: str) -> GoogleAccount | None:
    raise NotImplementedError("get_account: track INGEST")


def credentials_for_user(db: Session, user_id: str) -> Credentials | None:
    """google.oauth2.credentials.Credentials for the user's connected account, or None if
    they have not connected Google."""
    raise NotImplementedError("credentials_for_user: track INGEST")


def disconnect(db: Session, user_id: str) -> None:
    """Stop the Gmail watch, revoke the token at Google (best effort), delete the row."""
    raise NotImplementedError("disconnect: track INGEST")
