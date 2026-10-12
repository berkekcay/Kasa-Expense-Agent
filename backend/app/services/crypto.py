"""Symmetric encryption for secrets we must store (Google refresh tokens).

Fernet = AES-128-CBC + HMAC-SHA256 with a timestamp. The key comes from settings
(`TOKEN_ENCRYPTION_KEY`, Secret Manager in prod) and never from code.

Generate a key:  python -m app.services.crypto
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class CryptoError(RuntimeError):
    """Missing/invalid key, or a ciphertext that was not made with the current key."""


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def _fernet(key: str | None = None) -> Fernet:
    key = key if key is not None else get_settings().token_encryption_key
    if not key:
        raise CryptoError(
            "TOKEN_ENCRYPTION_KEY is not set (generate one with `python -m app.services.crypto`)"
        )
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise CryptoError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt(plaintext: str, *, key: str | None = None) -> str:
    return _fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str, *, key: str | None = None, max_age_seconds: int | None = None) -> str:
    """`max_age_seconds` rejects tokens older than that (Fernet stores the creation time),
    e.g. for short-lived OAuth `state` values."""
    try:
        return _fernet(key).decrypt(ciphertext.encode("ascii"), ttl=max_age_seconds).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError) as exc:
        raise CryptoError("could not decrypt: wrong key, expired or corrupted value") from exc


if __name__ == "__main__":
    print(generate_key())
