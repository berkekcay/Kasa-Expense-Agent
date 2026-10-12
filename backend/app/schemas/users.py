"""Profile schemas for GET/PATCH /me (shared)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.db.models import User


class MeOut(BaseModel):
    user_id: str
    display_name: str
    email: str | None

    @classmethod
    def from_model(cls, u: User) -> MeOut:
        return cls(user_id=u.id, display_name=u.display_name, email=u.email)


class MeUpdateIn(BaseModel):
    display_name: str = Field(
        min_length=1, max_length=200, description="1 to 100 characters after trimming spaces"
    )
