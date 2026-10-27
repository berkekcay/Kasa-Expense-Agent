"""Profile schemas for GET/PATCH /me (shared)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import User


class MeOut(BaseModel):
    user_id: str
    display_name: str
    email: str | None
    login_email: str | None = None
    has_password: bool = False
    google_linked: bool = False
    totp_enabled: bool = False
    kind: Literal["account", "dev"] = Field(
        default="dev",
        description="account: signs in with email/Google and 2FA; dev: a dev-mode or Firebase id",
    )

    @classmethod
    def from_model(cls, u: User) -> MeOut:
        account = bool(u.login_email or u.google_sub)
        return cls(
            user_id=u.id,
            display_name=u.display_name,
            email=u.email,
            login_email=u.login_email,
            has_password=bool(u.password_hash),
            google_linked=bool(u.google_sub),
            totp_enabled=u.totp_enabled_at is not None,
            kind="account" if account else "dev",
        )


class MeUpdateIn(BaseModel):
    display_name: str = Field(
        min_length=1, max_length=200, description="1 to 100 characters after trimming spaces"
    )
