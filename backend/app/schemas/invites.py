"""House invite link schemas (owner: track HOUSE, US-HOUSE-02)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import HouseInvite
from app.services import invites as invite_service
from app.services.invites import InvitePreview


def _utc(value: dt.datetime) -> dt.datetime:
    """Stored times are naive UTC; send them with an offset so browsers read them right."""
    return value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value


class InviteIn(BaseModel):
    days: int = Field(
        default=invite_service.DEFAULT_DAYS,
        ge=1,
        le=invite_service.MAX_DAYS,
        description="how many days the link works",
    )
    max_uses: int = Field(
        default=invite_service.DEFAULT_MAX_USES,
        ge=1,
        le=invite_service.MAX_MAX_USES,
        description="how many people can join with it",
    )


class InviteOut(BaseModel):
    id: int
    code: str
    url: str = Field(description="the page to share; it opens the join screen")
    created_by: str
    created_at: dt.datetime
    expires_at: dt.datetime
    max_uses: int
    uses: int

    @classmethod
    def from_model(cls, invite: HouseInvite) -> InviteOut:
        return cls(
            id=invite.id,
            code=invite.code,
            url=invite_service.invite_url(invite.code),
            created_by=invite.created_by,
            created_at=_utc(invite.created_at),
            expires_at=_utc(invite.expires_at),
            max_uses=invite.max_uses,
            uses=invite.uses,
        )


class InvitePreviewOut(BaseModel):
    code: str
    house_name: str
    invited_by: str = Field(description="display name of the member who made the link")
    expires_at: dt.datetime
    usable: bool
    reason: Literal["revoked", "expired", "used_up"] | None = Field(
        default=None, description="why the link cannot be used; null when it can"
    )
    message: str | None = Field(default=None, description="the reason in words")
    already_member: bool
    house_id: int | None = Field(default=None, description="only set when you are already a member")

    @classmethod
    def from_preview(cls, p: InvitePreview) -> InvitePreviewOut:
        return cls(
            code=p.code,
            house_name=p.house_name,
            invited_by=p.invited_by,
            expires_at=_utc(p.expires_at),
            usable=p.usable,
            reason=p.reason,
            message=invite_service.REASON_MESSAGES.get(p.reason) if p.reason else None,
            already_member=p.already_member,
            house_id=p.house_id,
        )
