"""House invite links (owner: track HOUSE, US-HOUSE-02).

Members create, list and cancel links under /houses/{house_id}/invites (404 for anyone else,
like every house endpoint). Any signed-in user can preview a code and accept it; those two
run in a system session because the caller is not a member yet (see `services.invites`).
"""

from typing import Annotated

from fastapi import APIRouter, Body, Response

from app.auth import DB, CurrentUser
from app.db.session import session_for
from app.schemas.houses import HouseOut
from app.schemas.invites import InviteIn, InviteOut, InvitePreviewOut
from app.services import houses as house_service
from app.services import invites as invite_service

router = APIRouter(tags=["invites"])


@router.post("/houses/{house_id}/invites", response_model=InviteOut, status_code=201)
def create_invite(
    house_id: int,
    db: DB,
    user_id: CurrentUser,
    body: Annotated[InviteIn | None, Body()] = None,
) -> InviteOut:
    """A new invite link (default: 7 days, 10 people). Share `url`; the code is in it."""
    body = body or InviteIn()
    invite = invite_service.create_invite(db, user_id, house_id, days=body.days, max_uses=body.max_uses)
    return InviteOut.from_model(invite)


@router.get("/houses/{house_id}/invites", response_model=list[InviteOut])
def list_invites(house_id: int, db: DB, user_id: CurrentUser) -> list[InviteOut]:
    """Links that still work (not cancelled, not expired, not used up), newest first."""
    return [InviteOut.from_model(i) for i in invite_service.list_invites(db, user_id, house_id)]


@router.delete("/houses/{house_id}/invites/{invite_id}", status_code=204)
def revoke_invite(house_id: int, invite_id: int, db: DB, user_id: CurrentUser) -> Response:
    """Cancel a link; it stops working right away. Any member can cancel any link."""
    invite_service.revoke_invite(db, user_id, house_id, invite_id)
    return Response(status_code=204)


@router.get("/invites/{code}", response_model=InvitePreviewOut)
def preview_invite(code: str, user_id: CurrentUser) -> InvitePreviewOut:
    """Where a link leads: house name, who invited you, expiry and whether it still works.
    404 for an unknown code."""
    with session_for(user_id, system=True) as sys_db:
        return InvitePreviewOut.from_preview(invite_service.preview_invite(sys_db, user_id, code))


@router.post("/invites/{code}/accept", response_model=HouseOut)
def accept_invite(code: str, db: DB, user_id: CurrentUser) -> HouseOut:
    """Join the house. Already a member: the house comes back and nothing changes.
    409 with the reason for a cancelled, expired or used-up link; 404 for an unknown code."""
    with session_for(user_id, system=True) as sys_db:
        house_id = invite_service.accept_invite(sys_db, user_id, code)
    return HouseOut.from_model(house_service.get_house(db, user_id, house_id))
