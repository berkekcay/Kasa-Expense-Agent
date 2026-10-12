"""Detected subscriptions (owner: track MONEY). Errors: 404 unknown subscription."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import DB, CurrentUser
from app.schemas.subscriptions import SubscriptionOut
from app.services import subscriptions as subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionOut], summary="List detected subscriptions")
def list_subscriptions(
    db: DB, user_id: CurrentUser, include_dismissed: bool = False
) -> list[SubscriptionOut]:
    """What the last detection found; run POST /subscriptions/detect to refresh."""
    rows = subscription_service.list_subscriptions(db, user_id, include_dismissed=include_dismissed)
    return [SubscriptionOut.from_model(s) for s in rows]


@router.post("/detect", response_model=list[SubscriptionOut], summary="Scan expenses for recurring charges")
def detect(db: DB, user_id: CurrentUser) -> list[SubscriptionOut]:
    """Re-scan the user's expenses for recurring charges and return the active ones.
    Dismissed subscriptions stay dismissed."""
    return [SubscriptionOut.from_model(s) for s in subscription_service.detect_subscriptions(db, user_id)]


@router.get("/upcoming", response_model=list[SubscriptionOut], summary="Charges expected soon")
def upcoming(
    db: DB, user_id: CurrentUser, within_days: Annotated[int, Query(ge=0, le=366)] = 30
) -> list[SubscriptionOut]:
    """Active subscriptions expected within the next `within_days` days, soonest first."""
    rows = subscription_service.upcoming_charges(db, user_id, within_days=within_days)
    return [SubscriptionOut.from_model(s) for s in rows]


@router.post("/{subscription_id}/dismiss", response_model=SubscriptionOut, summary="Not a subscription")
def dismiss(subscription_id: int, db: DB, user_id: CurrentUser) -> SubscriptionOut:
    """Hide it, unlink its expenses, and never re-detect it."""
    return SubscriptionOut.from_model(subscription_service.dismiss_subscription(db, user_id, subscription_id))
