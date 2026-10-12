"""Recurring charge detection (owner: track MONEY).

Looks at the user's expenses grouped by `merchant_key` and finds regular intervals
(weekly ~7 days, monthly ~28-31, yearly ~365) with similar amounts. Detected rows go to
`subscriptions` (upsert on user + merchant_key); matching expenses get `subscription_id`.
A dismissed subscription is never re-activated by detection.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.db.models import Subscription


def merchant_key(merchant: str) -> str:
    """Normalise a merchant name for grouping: Turkish-aware lowercase, strip punctuation,
    card-statement noise (e.g. "NETFLIX.COM 866-579" -> "netflix")."""
    raise NotImplementedError("merchant_key: track MONEY")


def detect_subscriptions(db: Session, user_id: str, *, today: dt.date | None = None) -> list[Subscription]:
    """Scan the user's expenses, upsert detected subscriptions, return the active ones."""
    raise NotImplementedError("detect_subscriptions: track MONEY")


def list_subscriptions(db: Session, user_id: str, *, include_dismissed: bool = False) -> list[Subscription]:
    raise NotImplementedError("list_subscriptions: track MONEY")


def dismiss_subscription(db: Session, user_id: str, subscription_id: int) -> Subscription:
    raise NotImplementedError("dismiss_subscription: track MONEY")


def upcoming_charges(db: Session, user_id: str, *, within_days: int = 30) -> list[Subscription]:
    """Active subscriptions whose next_expected_date is within the next `within_days`."""
    raise NotImplementedError("upcoming_charges: track MONEY")
