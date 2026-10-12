"""Detected subscriptions (owner: track MONEY)."""

from fastapi import APIRouter

from app.auth import DB, CurrentUser
from app.schemas.subscriptions import SubscriptionOut
from app.services import subscriptions as subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=list[SubscriptionOut])
def list_subscriptions(
    db: DB, user_id: CurrentUser, include_dismissed: bool = False
) -> list[SubscriptionOut]:
    subscription_service.list_subscriptions(db, user_id, include_dismissed=include_dismissed)
    raise NotImplementedError("GET /subscriptions: track MONEY")


@router.post("/detect", response_model=list[SubscriptionOut])
def detect(db: DB, user_id: CurrentUser) -> list[SubscriptionOut]:
    """Re-scan the user's expenses for recurring charges."""
    subscription_service.detect_subscriptions(db, user_id)
    raise NotImplementedError("POST /subscriptions/detect: track MONEY")


@router.post("/{subscription_id}/dismiss", response_model=SubscriptionOut)
def dismiss(subscription_id: int, db: DB, user_id: CurrentUser) -> SubscriptionOut:
    subscription_service.dismiss_subscription(db, user_id, subscription_id)
    raise NotImplementedError("POST /subscriptions/{id}/dismiss: track MONEY")
