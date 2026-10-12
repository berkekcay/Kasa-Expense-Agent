"""Subscription schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models import Subscription
from app.services.money import format_minor


class SubscriptionOut(BaseModel):
    id: int
    merchant_key: str = Field(description="Normalised merchant name used for grouping")
    display_name: str = Field(description="Merchant as written on the newest charge")
    amount: str = Field(description="Newest charge, in the base currency")
    amount_minor: int
    currency: str
    period: Literal["weekly", "monthly", "yearly"]
    last_charge_date: dt.date
    next_expected_date: dt.date
    status: Literal["active", "dismissed"]

    @classmethod
    def from_model(cls, s: Subscription) -> SubscriptionOut:
        return cls(
            id=s.id,
            merchant_key=s.merchant_key,
            display_name=s.display_name,
            amount=format_minor(s.amount_minor),
            amount_minor=s.amount_minor,
            currency=s.currency,
            period=s.period,
            last_charge_date=s.last_charge_date,
            next_expected_date=s.next_expected_date,
            status=s.status,
        )
