"""The signed-in user's own profile (display name). Shared."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import User
from app.services.errors import InvalidInput
from app.services.expenses import ensure_user

DISPLAY_NAME_MAX = 100


def get_profile(db: Session, user_id: str) -> User:
    return ensure_user(db, user_id)


def set_display_name(db: Session, user_id: str, display_name: str) -> User:
    """Trim and save the name flatmates see (1 to 100 characters)."""
    name = display_name.strip()
    if not name:
        raise InvalidInput("display name cannot be empty")
    if len(name) > DISPLAY_NAME_MAX:
        raise InvalidInput(f"display name can be at most {DISPLAY_NAME_MAX} characters")
    user = ensure_user(db, user_id)
    user.display_name = name
    db.commit()
    return user
