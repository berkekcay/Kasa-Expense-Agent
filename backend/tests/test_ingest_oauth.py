"""Google OAuth (track INGEST): state signing, code exchange, encrypted storage, refresh,
revocation handling, disconnect and the REST endpoints. Google is faked with httpx."""

from __future__ import annotations

import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.fernet import Fernet

from app.config import get_settings
from app.db.models import GoogleAccount
from app.db.session import init_db, session_for
from app.integrations import gmail, google_oauth
from app.services import crypto
from app.services.errors import InvalidInput, NotConfigured
from tests.fixtures.ingest_fakes import ALL_SCOPES, CLIENT_ID, FakeGoogle


@pytest.fixture(autouse=True)
def _schema():
    init_db()


@pytest.fixture
def google(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "google_oauth_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "google_oauth_client_secret", "test-secret")
    monkeypatch.setattr(settings, "token_encryption_key", crypto.generate_key())
    monkeypatch.setattr(settings, "frontend_url", "http://web.test")
    monkeypatch.setattr(settings, "pubsub_topic", "")
    fake = FakeGoogle()
    monkeypatch.setattr(google_oauth, "http_client", fake.client)
    monkeypatch.setattr(gmail, "http_client", fake.client)
    google_oauth._token_cache.clear()
    yield fake
    google_oauth._token_cache.clear()


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def state_from(url: str) -> str:
    return parse_qs(urlparse(url).query)["state"][0]


# --- state -----------------------------------------------------------------------------------


def test_authorization_url_asks_for_offline_access(google):
    url = google_oauth.authorization_url("oauth-ayse")
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == google_oauth.AUTH_URL
    assert params["client_id"] == CLIENT_ID
    assert params["access_type"] == "offline" and params["prompt"] == "consent"
    assert params["response_type"] == "code" and params["include_granted_scopes"] == "true"
    assert params["redirect_uri"] == get_settings().google_oauth_redirect_uri
    assert set(params["scope"].split()) == set(ALL_SCOPES.split())
    assert "oauth-ayse" not in params["state"]  # encrypted, not readable
    assert google_oauth.read_state(params["state"]) == "oauth-ayse"


def test_state_tampered_expired_or_foreign_is_rejected(google):
    state = google_oauth.make_state("oauth-ayse")
    tampered = state[:-4] + ("AAAA" if not state.endswith("AAAA") else "BBBB")
    with pytest.raises(InvalidInput):
        google_oauth.read_state(tampered)
    with pytest.raises(InvalidInput):
        google_oauth.read_state("not-a-state")

    key = get_settings().token_encryption_key
    payload = json.dumps({"p": "kasa-google-oauth", "uid": "oauth-ayse", "n": "x"}).encode()
    old = Fernet(key.encode()).encrypt_at_time(payload, int(time.time()) - 700).decode()
    with pytest.raises(InvalidInput, match="expired"):
        google_oauth.read_state(old)

    # A valid Fernet value made for something else (e.g. a stored refresh token).
    with pytest.raises(InvalidInput):
        google_oauth.read_state(crypto.encrypt("1//refresh-token"))
    # Signed with another key.
    other = Fernet(Fernet.generate_key()).encrypt(payload).decode()
    with pytest.raises(InvalidInput):
        google_oauth.read_state(other)


def test_not_configured_without_client_settings(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", "")
    with pytest.raises(NotConfigured):
        google_oauth.authorization_url("u")
    assert client.get("/integrations/google/connect").status_code == 503
    status = client.get("/integrations/google/status", headers=as_user("oauth-nocfg")).json()
    assert status == {
        "configured": False,
        "connected": False,
        "google_email": None,
        "scopes": [],
        "gmail_access": False,
        "calendar_access": False,
        "gmail_watch_expires_at": None,
    }


# --- full flow through the API ---------------------------------------------------------------


def test_connect_callback_status_and_disconnect(client, google):
    user = "oauth-flow"
    url = client.get("/integrations/google/connect", headers=as_user(user)).json()["url"]
    google.add_code("code-1", "Ayse.Ogrenci@gmail.com")

    r = client.get(
        "/integrations/google/callback",
        params={"code": "code-1", "state": state_from(url)},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "http://web.test/settings?google=connected"

    with session_for(user) as db:
        row = db.get(GoogleAccount, user)
        assert row.google_email == "Ayse.Ogrenci@gmail.com"
        assert "rt-1" not in row.refresh_token_enc  # encrypted at rest
        assert crypto.decrypt(row.refresh_token_enc) == "rt-1"
        assert set(row.scopes.split()) == set(ALL_SCOPES.split())

    status = client.get("/integrations/google/status", headers=as_user(user)).json()
    assert status["connected"] and status["configured"]
    assert status["gmail_access"] and status["calendar_access"]
    assert status["google_email"] == "Ayse.Ogrenci@gmail.com"

    # The code was exchanged with the server-side secret and redirect URI.
    token_call = next(r for r in google.requests if r.url.path == "/token")
    form = parse_qs(token_call.content.decode())
    assert form["client_secret"] == ["test-secret"]
    assert form["redirect_uri"] == [get_settings().google_oauth_redirect_uri]

    assert client.delete("/integrations/google", headers=as_user(user)).status_code == 204
    assert google.revoked == ["rt-1"]
    assert client.get("/integrations/google/status", headers=as_user(user)).json()["connected"] is False
    # Disconnecting twice is fine.
    assert client.delete("/integrations/google", headers=as_user(user)).status_code == 204


def test_callback_errors_redirect_without_storing_anything(client, google):
    user = "oauth-errors"
    url = client.get("/integrations/google/connect", headers=as_user(user)).json()["url"]
    state = state_from(url)

    def callback(**params):
        r = client.get("/integrations/google/callback", params=params, follow_redirects=False)
        assert r.status_code == 303
        return parse_qs(urlparse(r.headers["location"]).query)

    assert callback(error="access_denied", state=state) == {"google": ["error"], "reason": ["denied"]}
    assert callback(code="whatever", state="forged") == {"google": ["error"], "reason": ["invalid"]}
    assert callback(code="unknown-code", state=state)["reason"] == ["invalid"]  # invalid_grant

    # The user unticked both Gmail and Calendar on Google's screen: the grant is revoked.
    google.add_code(
        "code-narrow", "a@gmail.com", scope="openid https://www.googleapis.com/auth/userinfo.email"
    )
    assert callback(code="code-narrow", state=state)["reason"] == ["scopes"]
    assert google.revoked == ["rt-1"]

    # An id_token minted for another OAuth client is refused.
    google.add_code("code-aud", "a@gmail.com", aud="someone-else.apps.googleusercontent.com")
    assert callback(code="code-aud", state=state)["reason"] == ["google"]

    with session_for(user) as db:
        assert db.get(GoogleAccount, user) is None


def test_exchange_endpoint_checks_the_signed_in_user(client, google):
    url = client.get("/integrations/google/connect", headers=as_user("oauth-starter")).json()["url"]
    google.add_code("code-x", "starter@gmail.com")
    body = {"code": "code-x", "state": state_from(url)}
    r = client.post("/integrations/google/exchange", json=body, headers=as_user("oauth-attacker"))
    assert r.status_code == 403
    r = client.post("/integrations/google/exchange", json=body, headers=as_user("oauth-starter"))
    assert r.status_code == 200, r.text
    assert r.json()["connected"] and r.json()["google_email"] == "starter@gmail.com"


def test_partial_grant_and_userinfo_fallback(google):
    tokens_body = {
        "access_token": "at-only",
        "expires_in": 3599,
        "refresh_token": "rt-2",
        "scope": "openid https://www.googleapis.com/auth/gmail.readonly",
        "token_type": "Bearer",
    }
    google.codes["code-noid"] = tokens_body  # no id_token in the answer
    tokens = google_oauth.exchange_code("code-noid")
    assert tokens.google_email == "fallback@gmail.com"
    assert tokens.scopes == ["openid", google_oauth.GMAIL_SCOPE]


# --- refresh ----------------------------------------------------------------------------------


def _connect(google: FakeGoogle, user: str, email: str = "ayse@gmail.com") -> None:
    google.add_code(f"code-{user}", email)
    with session_for(user) as db:
        from app.services.expenses import ensure_user

        ensure_user(db, user)
        google_oauth.save_account(db, user, google_oauth.exchange_code(f"code-{user}"))


def test_credentials_are_cached_then_refreshed(google):
    user = "oauth-refresh"
    _connect(google, user)
    with session_for(user) as db:
        creds = google_oauth.credentials_for_user(db, user)
        assert creds.token == f"at-code-{user}" and google.refresh_count == 0  # from the exchange
        assert creds.refresh_token == "rt-1" and creds.client_id == CLIENT_ID
        assert google_oauth.GMAIL_SCOPE in creds.scopes and creds.valid

        google_oauth._token_cache.clear()  # e.g. a new Cloud Run instance
        creds = google_oauth.credentials_for_user(db, user)
        assert creds.token == "at-refreshed-1" and google.refresh_count == 1
        again = google_oauth.credentials_for_user(db, user)
        assert again.token == "at-refreshed-1" and google.refresh_count == 1  # cached

        # Close to expiry: refreshed before use.
        enc, token, _expiry = google_oauth._token_cache[user]
        google_oauth._token_cache[user] = (enc, token, google_oauth._utcnow())
        assert google_oauth.credentials_for_user(db, user).token == "at-refreshed-2"
        assert google_oauth.credentials_for_user(db, "oauth-nobody") is None


def test_revoked_grant_disconnects_the_user(google):
    user = "oauth-revoked"
    _connect(google, user)
    google_oauth._token_cache.clear()
    google.refresh_error = "invalid_grant"
    with session_for(user) as db:
        assert google_oauth.credentials_for_user(db, user) is None
    with session_for(user) as db:
        assert db.get(GoogleAccount, user) is None


def test_other_refresh_errors_are_upstream_errors(google):
    from app.services.errors import UpstreamError

    user = "oauth-flaky"
    _connect(google, user)
    google_oauth._token_cache.clear()
    google.refresh_error = "invalid_client"
    with session_for(user) as db, pytest.raises(UpstreamError):
        google_oauth.credentials_for_user(db, user)
    with session_for(user) as db:
        assert db.get(GoogleAccount, user) is not None  # not a reason to forget the account


def test_reconnecting_another_google_account_resets_gmail_state(google):
    user = "oauth-switch"
    _connect(google, user, "first@gmail.com")
    with session_for(user) as db:
        row = db.get(GoogleAccount, user)
        row.gmail_history_id = "12345"
        db.commit()
    _connect(google, user, "second@gmail.com")
    with session_for(user) as db:
        row = db.get(GoogleAccount, user)
        assert row.google_email == "second@gmail.com" and row.gmail_history_id is None


def test_disconnect_stops_the_watch(google):
    user = "oauth-watch"
    _connect(google, user)
    with session_for(user) as db:
        db.get(GoogleAccount, user).gmail_watch_expires_at = google_oauth._utcnow()
        db.commit()
        google_oauth.disconnect(db, user)
    assert google.stop_calls == 1 and google.revoked == ["rt-1"]


def test_tokens_never_reach_the_logs(google, caplog):
    caplog.set_level("DEBUG")
    user = "oauth-logs"
    _connect(google, user)
    google_oauth._token_cache.clear()
    google.refresh_error = "invalid_grant"
    with session_for(user) as db:
        google_oauth.credentials_for_user(db, user)
    assert "rt-1" not in caplog.text and "at-code" not in caplog.text
