"""The caller's own profile: GET /me and PATCH /me (shared)."""

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.users import MeOut, MeUpdateIn
from app.services import users as user_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=MeOut)
def get_me(db: DB, user_id: CurrentUser) -> MeOut:
    """Who you are in Kasa: user id, display name (what flatmates see) and email."""
    return MeOut.from_model(user_service.get_profile(db, user_id))


@router.patch("/me", response_model=MeOut)
def update_me(body: MeUpdateIn, db: DB, user_id: CurrentUser) -> MeOut:
    """Change your display name (1 to 100 characters, spaces trimmed)."""
    return MeOut.from_model(user_service.set_display_name(db, user_id, body.display_name))
