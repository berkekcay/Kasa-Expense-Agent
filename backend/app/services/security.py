"""Small security primitives for Kasa accounts, standard library only (owner: shared).

- Passwords: scrypt (RFC 7914) with a random salt, stored as
  "scrypt$<n>$<r>$<p>$<salt b64>$<hash b64>"; compared in constant time.
- TOTP (RFC 6238): 30-second steps, 6 digits, HMAC-SHA1, the parameters Google
  Authenticator uses. One step of clock drift is accepted either way, and a code's step is
  returned so the caller can refuse it a second time.
- Recovery codes and session tokens are long random values, so a plain SHA-256 is enough to
  store them (nothing to brute force).
- Signed tokens: base64url(JSON) + HMAC-SHA256, with a purpose and an expiry, for the short
  steps between password and 2FA and for the Google sign-in `state`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
import time
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlencode

from app.config import get_settings

# --- passwords ------------------------------------------------------------------------------

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1
MIN_PASSWORD_LENGTH = 10
_COMMON = {
    "1234567890",
    "12345678910",
    "qwertyuiop",
    "password12",
    "password123",
    "sifre12345",
    "parola1234",
    "1q2w3e4r5t",
    "asdfghjkl1",
    "kasakasa12",
}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def password_problem(password: str) -> str | None:
    """Why a new password is not acceptable, or None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"the password needs at least {MIN_PASSWORD_LENGTH} characters"
    if len(password) > 256:
        return "the password is too long"
    if password.lower() in _COMMON or len(set(password)) < 4:
        return "this password is too easy to guess"
    return None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        # Spend the same time as a real check so missing accounts are not obvious.
        hashlib.scrypt(password.encode("utf-8"), salt=b"0" * 16, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, _unb64(digest))


# --- TOTP -----------------------------------------------------------------------------------

TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6
ISSUER = "Kasa"


def new_totp_secret() -> str:
    """160 random bits as base32 without padding, the format authenticator apps expect."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def totp_code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**TOTP_DIGITS).zfill(TOTP_DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // TOTP_STEP_SECONDS)


def verify_totp(
    secret: str, code: str, *, last_step: int | None = None, now: float | None = None
) -> int | None:
    """The matching time step, or None. Steps at or before `last_step` are refused, so a code
    that was already used (or an older one) cannot be replayed."""
    code = "".join(ch for ch in code if ch.isdigit())
    if len(code) != TOTP_DIGITS:
        return None
    step = current_step(now)
    for candidate in (step - 1, step, step + 1):
        if last_step is not None and candidate <= last_step:
            continue
        if hmac.compare_digest(totp_code(secret, candidate), code):
            return candidate
    return None


def otpauth_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    query = urlencode(
        {"secret": secret, "issuer": ISSUER, "digits": TOTP_DIGITS, "period": TOTP_STEP_SECONDS}
    )
    return f"otpauth://totp/{label}?{query}"


def qr_svg(text: str) -> str:
    """The text as a QR code, as a standalone SVG document."""
    import io

    import segno  # imported lazily: only the 2FA setup screen needs it

    buffer = io.BytesIO()
    segno.make(text, error="m").save(buffer, kind="svg", scale=6, border=2, dark="#111827", light="#ffffff")
    return buffer.getvalue().decode("utf-8")


# --- recovery codes and tokens --------------------------------------------------------------

_RECOVERY_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
SESSION_PREFIX = "ks_"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_recovery_codes(count: int = 10) -> list[str]:
    """Codes like "k3mp-7qz2-x9ad": easy to read out, 60 bits each."""
    codes = []
    for _ in range(count):
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(12))
        codes.append(f"{raw[:4]}-{raw[4:8]}-{raw[8:]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    raw = "".join(ch for ch in code.lower() if ch.isalnum())
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}" if len(raw) == 12 else raw


def new_session_token() -> str:
    return SESSION_PREFIX + secrets.token_urlsafe(32)


@lru_cache
def _process_secret() -> bytes:
    return secrets.token_bytes(32)


def _signing_key() -> bytes:
    configured = get_settings().auth_secret
    return configured.encode("utf-8") if configured else _process_secret()


def sign(purpose: str, payload: dict[str, Any], ttl_seconds: int) -> str:
    body = {**payload, "p": purpose, "exp": int(time.time()) + ttl_seconds, "n": secrets.token_urlsafe(6)}
    data = _b64(json.dumps(body, separators=(",", ":")).encode("utf-8"))
    mac = _b64(hmac.new(_signing_key(), data.encode("ascii"), hashlib.sha256).digest())
    return f"{data}.{mac}"


def unsign(purpose: str, token: str) -> dict[str, Any] | None:
    """The payload of a token made by `sign` for this purpose, or None if forged or expired."""
    try:
        data, mac = token.split(".")
        expected = _b64(hmac.new(_signing_key(), data.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(mac, expected):
            return None
        body = json.loads(_unb64(data))
    except (ValueError, TypeError):
        return None
    if not isinstance(body, dict) or body.get("p") != purpose or int(body.get("exp", 0)) < time.time():
        return None
    return body
