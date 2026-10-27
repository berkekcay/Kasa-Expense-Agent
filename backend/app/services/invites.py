"""House invite links (owner: track HOUSE, US-HOUSE-02).

A member creates a link with a random code; whoever opens it while it is still usable can
join the house. Nobody can add another person to a house any more except through a link the
person accepts themselves (the dev-only `houses.add_member` aside).

Sessions: `create_invite`, `list_invites` and `revoke_invite` run in the caller's normal
session and check membership like `services.houses`. `preview_invite` and `accept_invite`
run for someone who is not a member yet, so the router gives them a *system* session
(`session_for(user_id, system=True)`): on SQL Server that is what lets them read the invite
row and insert the new membership. They only touch `house_invites`, the caller's own
`house_members` row and `users` (display names), never the house's other data.

Times are naive UTC, like every DateTime column.
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import HouseInvite, HouseMember, User
from app.services import houses as house_service
from app.services.errors import Conflict, InvalidInput, NotFound

# No 0/O, 1/I/L: easy to read out loud or type from a phone screen.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 10
DEFAULT_DAYS = 7
MAX_DAYS = 30
DEFAULT_MAX_USES = 10
MAX_MAX_USES = 50

REASON_MESSAGES = {
    "revoked": "this invite link was cancelled; ask your flatmate for a new one",
    "expired": "this invite link has expired; ask your flatmate for a new one",
    "used_up": "this invite link has been used the maximum number of times; ask for a new one",
}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(code: str) -> str:
    """Accept the code as typed or pasted: any case, with dashes or spaces."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def invite_url(code: str) -> str:
    return f"{get_settings().frontend_url.rstrip('/')}/invite/{code}"


def unusable_reason(invite: HouseInvite, now: dt.datetime | None = None) -> str | None:
    """None when the invite can still be used, else "revoked", "expired" or "used_up"."""
    now = now or utcnow()
    if invite.revoked_at is not None:
        return "revoked"
    if invite.expires_at <= now:
        return "expired"
    if invite.uses >= invite.max_uses:
        return "used_up"
    return None


def create_invite(
    db: Session,
    user_id: str,
    house_id: int,
    *,
    days: int = DEFAULT_DAYS,
    max_uses: int = DEFAULT_MAX_USES,
) -> HouseInvite:
    """A new invite link for a house the caller is a member of (404 otherwise)."""
    house = house_service.get_house(db, user_id, house_id)
    if not 1 <= days <= MAX_DAYS:
        raise InvalidInput(f"an invite can be valid for 1 to {MAX_DAYS} days")
    if not 1 <= max_uses <= MAX_MAX_USES:
        raise InvalidInput(f"an invite can be used 1 to {MAX_MAX_USES} times")
    now = utcnow()
    for _attempt in range(5):  # 31^10 codes: a clash is practically impossible, but cheap to handle
        invite = HouseInvite(
            house_id=house.id,
            code=new_code(),
            house_name=house.name,
            created_by=user_id,
            created_at=now,
            expires_at=now + dt.timedelta(days=days),
            max_uses=max_uses,
            uses=0,
        )
        db.add(invite)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        return invite
    raise Conflict("could not create an invite code, please try again")


def list_invites(db: Session, user_id: str, house_id: int) -> list[HouseInvite]:
    """Invites of the house that can still be used, newest first (members only)."""
    house_service.get_house(db, user_id, house_id)
    rows = db.scalars(
        select(HouseInvite)
        .where(HouseInvite.house_id == house_id, HouseInvite.revoked_at.is_(None))
        .order_by(HouseInvite.id.desc())
    )
    now = utcnow()
    return [i for i in rows if unusable_reason(i, now) is None]


def revoke_invite(db: Session, user_id: str, house_id: int, invite_id: int) -> None:
    """Cancel an invite of the house (any member). Cancelling twice is harmless."""
    house_service.get_house(db, user_id, house_id)
    invite = db.get(HouseInvite, invite_id)
    if invite is None or invite.house_id != house_id:
        raise NotFound(f"invite {invite_id} not found")
    if invite.revoked_at is None:
        invite.revoked_at = utcnow()
        db.commit()


@dataclass
class InvitePreview:
    code: str
    house_name: str
    invited_by: str  # display name of the member who made the link
    expires_at: dt.datetime
    reason: str | None  # None = usable; else "revoked", "expired" or "used_up"
    already_member: bool
    house_id: int | None  # only told to people who are already members

    @property
    def usable(self) -> bool:
        return self.reason is None


def _find(db: Session, code: str) -> HouseInvite:
    normalized = normalize_code(code)
    invite = None
    if normalized:
        invite = db.scalars(select(HouseInvite).where(HouseInvite.code == normalized)).first()
    if invite is None:
        raise NotFound("invite not found; check the link or ask for a new one")
    return invite


def _is_member(db: Session, user_id: str, house_id: int) -> bool:
    row = db.scalars(
        select(HouseMember.id).where(HouseMember.house_id == house_id, HouseMember.user_id == user_id)
    ).first()
    return row is not None


def preview_invite(db: Session, user_id: str, code: str) -> InvitePreview:
    """Where a link leads, for any signed-in user. `db` is a system session (see top)."""
    invite = _find(db, code)
    inviter = db.get(User, invite.created_by)
    member = _is_member(db, user_id, invite.house_id)
    return InvitePreview(
        code=invite.code,
        house_name=invite.house_name,
        invited_by=inviter.display_name if inviter else invite.created_by,
        expires_at=invite.expires_at,
        reason=unusable_reason(invite),
        already_member=member,
        house_id=invite.house_id if member else None,
    )


def accept_invite(db: Session, user_id: str, code: str) -> int:
    """Join the house behind `code`; returns its id. `db` is a system session (see top).

    Someone who is already a member just gets the house id back and uses nothing. A revoked,
    expired or used-up link raises Conflict with the reason.
    """
    invite = _find(db, code)
    if _is_member(db, user_id, invite.house_id):
        return invite.house_id
    reason = unusable_reason(invite)
    if reason:
        raise Conflict(REASON_MESSAGES[reason])
    # One atomic UPDATE so two people joining at once cannot go over max_uses.
    now = utcnow()
    taken = db.execute(
        update(HouseInvite)
        .where(
            HouseInvite.id == invite.id,
            HouseInvite.revoked_at.is_(None),
            HouseInvite.expires_at > now,
            HouseInvite.uses < HouseInvite.max_uses,
        )
        .values(uses=HouseInvite.uses + 1)
        .execution_options(synchronize_session=False)
    ).rowcount
    if taken != 1:
        db.rollback()
        db.expire_all()
        raise Conflict(REASON_MESSAGES[unusable_reason(_find(db, code), now) or "used_up"])
    db.add(HouseMember(house_id=invite.house_id, user_id=user_id))
    try:
        db.commit()
    except IntegrityError:  # joined through another request at the same moment
        db.rollback()
    return invite.house_id
