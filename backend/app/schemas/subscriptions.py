"""Subscription schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    id: int
    merchant_key: str
    display_name: str
    amount: str
    amount_minor: int
    currency: str
    period: str
    last_charge_date: dt.date
    next_expected_date: dt.date
    status: str
