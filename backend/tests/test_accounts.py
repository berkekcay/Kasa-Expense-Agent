"""Kasa accounts: register, sign in, mandatory 2FA, recovery codes, sessions, Google."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import pytest

from app.config import get_settings
from app.integrations import google_signin
from app.services import accounts, crypto, security

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    monkeypatch.setattr(get_settings(), "token_encryption_key", crypto.generate_key())
    monkeypatch.setattr(get_settings(), "auth_mode", "dev")


def _code(secret: str, ahead: int = 0) -> str:
    return security.totp_code(secret, security.current_step() + ahead)


def _register(client, email: str) -> tuple[str, list[str], str]:
    """A finished account: (session token, recovery codes, TOTP secret)."""
    r = client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "display_name": "Elif Y", "accept_terms": True},
    )
    assert r.status_code == 201, r.text
    pending = r.json()
    assert pending["step"] == "totp_setup"
    setup = client.post("/auth/totp/setup", json={"pending_token": pending["pending_token"]}).json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/Kasa%3A") and "<svg" in setup["qr_svg"]
    r = client.post(
        "/auth/totp/confirm", json={"pending_token": pending["pending_token"], "code": _code(setup["secret"])}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token"].startswith("ks_") and body["user"]["totp_enabled"] is True
    assert body["user"]["kind"] == "account" and len(body["recovery_codes"]) == 10
    return body["token"], body["recovery_codes"], setup["secret"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_totp_matches_the_rfc_6238_test_vector_and_refuses_replays():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # base32 of "12345678901234567890"
    assert security.totp_code(secret, 59 // 30) == "287082"
    step = security.verify_totp(secret, "287082", now=59)
    assert step == 1
    assert security.verify_totp(secret, "287082", now=59, last_step=step) is None
    assert security.verify_totp(secret, "000000", now=59) is None


def test_passwords_are_salted_scrypt_and_weak_ones_refused():
    stored = security.hash_password(PASSWORD)
    assert stored.startswith("scrypt$") and PASSWORD not in stored
    assert security.verify_password(PASSWORD, stored) and not security.verify_password("wrong one!!", stored)
    assert stored != security.hash_password(PASSWORD)
    assert security.password_problem("short") and security.password_problem("1234567890")
    assert security.password_problem(PASSWORD) is None


def test_register_sets_up_2fa_and_the_session_works(client):
    token, _codes, _secret = _register(client, "elif.reg@example.com")
    me = client.get("/me", headers=_auth(token)).json()
    assert me["login_email"] == "elif.reg@example.com" and me["has_password"] is True
    again = client.post(
        "/auth/register",
        json={
            "email": "ELIF.REG@example.com",
            "password": PASSWORD,
            "display_name": "x",
            "accept_terms": True,
        },
    )
    assert again.status_code == 409
    weak = client.post(
        "/auth/register",
        json={"email": "weak@example.com", "password": "123", "display_name": "x", "accept_terms": True},
    )
    assert weak.status_code == 400
    no_terms = client.post(
        "/auth/register",
        json={"email": "t@example.com", "password": PASSWORD, "display_name": "x", "accept_terms": False},
    )
    assert no_terms.status_code == 400


def test_login_needs_the_code_and_recovery_codes_work_once(client):
    _token, codes, secret = _register(client, "elif.login@example.com")
    assert (
        client.post(
            "/auth/login", json={"email": "elif.login@example.com", "password": "nope nope nope"}
        ).status_code
        == 401
    )
    pending = client.post(
        "/auth/login", json={"email": "Elif.Login@example.com", "password": PASSWORD}
    ).json()
    assert pending["step"] == "totp"
    bad = client.post(
        "/auth/login/verify", json={"pending_token": pending["pending_token"], "code": "000000"}
    )
    assert bad.status_code == 400
    ok = client.post(
        "/auth/login/verify", json={"pending_token": pending["pending_token"], "code": _code(secret, 1)}
    )
    assert ok.status_code == 200 and ok.json()["token"].startswith("ks_")

    pending = client.post(
        "/auth/login", json={"email": "elif.login@example.com", "password": PASSWORD}
    ).json()
    used = codes[0].upper().replace("-", " ")
    r = client.post(
        "/auth/login/verify", json={"pending_token": pending["pending_token"], "recovery_code": used}
    )
    assert r.status_code == 200
    r = client.post(
        "/auth/login/verify", json={"pending_token": pending["pending_token"], "recovery_code": codes[0]}
    )
    assert r.status_code == 400  # each recovery code works once


def test_five_failures_lock_the_account(client):
    _register(client, "elif.lock@example.com")
    for _ in range(5):
        r = client.post(
            "/auth/login", json={"email": "elif.lock@example.com", "password": "wrong wrong wrong"}
        )
        assert r.status_code == 401
    r = client.post("/auth/login", json={"email": "elif.lock@example.com", "password": PASSWORD})
    assert r.status_code == 423 and "try again after" in r.json()["detail"]


def test_a_setup_step_cannot_replace_the_secret_after_2fa_is_on(client):
    r = client.post(
        "/auth/register",
        json={
            "email": "elif.setup@example.com",
            "password": PASSWORD,
            "display_name": "E",
            "accept_terms": True,
        },
    )
    pending = r.json()["pending_token"]
    secret = client.post("/auth/totp/setup", json={"pending_token": pending}).json()["secret"]
    client.post("/auth/totp/confirm", json={"pending_token": pending, "code": _code(secret)})
    assert client.post("/auth/totp/setup", json={"pending_token": pending}).status_code == 401


def test_accounts_mode_requires_a_session_and_ignores_the_dev_header(client, monkeypatch):
    token, _codes, _secret = _register(client, "elif.mode@example.com")
    monkeypatch.setattr(get_settings(), "auth_mode", "accounts")
    assert client.get("/me", headers={"X-User-Id": "demo"}).status_code == 401
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers=_auth(token)).json()["login_email"] == "elif.mode@example.com"
    assert client.get("/me", headers=_auth("ks_not-a-real-token")).status_code == 401
    assert client.get("/health").json()["auth"] == "accounts"


def test_sessions_can_be_listed_revoked_and_logged_out(client):
    token, _codes, secret = _register(client, "elif.sessions@example.com")
    pending = client.post(
        "/auth/login", json={"email": "elif.sessions@example.com", "password": PASSWORD}
    ).json()
    other = client.post(
        "/auth/login/verify", json={"pending_token": pending["pending_token"], "code": _code(secret, 1)}
    ).json()["token"]
    listed = client.get("/auth/sessions", headers=_auth(token)).json()
    assert len(listed) == 2 and sum(s["current"] for s in listed) == 1
    other_id = next(s["id"] for s in listed if not s["current"])
    assert client.delete(f"/auth/sessions/{other_id}", headers=_auth(token)).status_code == 204
    assert client.get("/me", headers=_auth(other)).status_code == 401
    assert client.post("/auth/logout", headers=_auth(token)).status_code == 204
    assert client.get("/me", headers=_auth(token)).status_code == 401


def test_new_recovery_codes_and_password_change_need_a_code(client):
    token, old_codes, secret = _register(client, "elif.pw@example.com")
    assert (
        client.post("/auth/recovery-codes", json={"code": "123456"}, headers=_auth(token)).status_code == 400
    )
    fresh = client.post("/auth/recovery-codes", json={"code": _code(secret, 1)}, headers=_auth(token)).json()
    assert len(fresh["recovery_codes"]) == 10 and set(fresh["recovery_codes"]).isdisjoint(old_codes)
    r = client.post(
        "/auth/password",
        json={
            "current_password": PASSWORD,
            "new_password": "a much better passphrase",
            "code": _code(secret, -1),
        },
        headers=_auth(token),
    )
    assert r.status_code == 400  # an older step than the last used code is refused
    pending = client.post("/auth/login", json={"email": "elif.pw@example.com", "password": PASSWORD}).json()
    assert pending["step"] == "totp"


def test_google_sign_in_asks_for_2fa_and_never_takes_over_a_password_account(client, monkeypatch):
    _register(client, "elif.google@example.com")
    monkeypatch.setattr(get_settings(), "google_oauth_client_id", "client-id")
    monkeypatch.setattr(get_settings(), "google_oauth_client_secret", "client-secret")
    start = client.get("/auth/google/start", params={"next": "/houses"}, follow_redirects=False)
    assert start.status_code == 307
    query = parse_qs(urlparse(start.headers["location"]).query)
    assert query["scope"] == ["openid email profile"]
    state = query["state"][0]

    def callback(sub: str, email: str) -> str:
        monkeypatch.setattr(
            google_signin,
            "exchange",
            lambda code: google_signin.GoogleIdentity(sub=sub, email=email, name="E"),
        )
        r = client.get("/auth/google/callback", params={"code": "c", "state": state}, follow_redirects=False)
        assert r.status_code == 303
        return r.headers["location"]

    # Someone registered this email with a password: Google sign-in must not land in it.
    assert "#error=" in callback("g-attacker", "Elif.Google@example.com")
    # A new Google user sets up the authenticator first, then signs in with codes.
    location = callback("g-456", "new.google@example.com")
    fragment = dict(part.split("=", 1) for part in urlparse(location).fragment.split("&"))
    assert fragment["step"] == "totp_setup" and unquote(fragment["next"]) == "/houses"
    pending = unquote(fragment["pending"])
    secret = client.post("/auth/totp/setup", json={"pending_token": pending}).json()["secret"]
    signed = client.post("/auth/totp/confirm", json={"pending_token": pending, "code": _code(secret)}).json()
    assert signed["user"]["google_linked"] is True and signed["user"]["has_password"] is False
    assert "step=totp&" in callback("g-456", "new.google@example.com")
    forged = client.get(
        "/auth/google/callback", params={"code": "c", "state": "forged.state"}, follow_redirects=False
    )
    assert "#error=" in forged.headers["location"]


def test_safe_next_only_allows_same_site_paths():
    assert google_signin.safe_next("/houses") == "/houses"
    for bad in ("https://evil.example", "//evil.example", "/\\evil", None, ""):
        assert google_signin.safe_next(bad) == "/"


def test_pending_tokens_are_signed_and_purpose_bound():
    token = security.sign("kasa-login", {"uid": "u1"}, 60)
    assert security.unsign("kasa-login", token)["uid"] == "u1"
    assert security.unsign("kasa-google-login", token) is None
    data, mac = token.split(".")
    assert security.unsign("kasa-login", data + "." + mac[::-1]) is None
    assert accounts.PENDING_TTL_SECONDS == 600
