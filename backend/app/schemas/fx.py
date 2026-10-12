"""FX schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class FxRateOut(BaseModel):
    currency: str
    rate_date: dt.date
    try_per_unit: str  # Decimal as string, 6 places


class FxConvertOut(BaseModel):
    from_currency: str
    to_currency: str
    on: dt.date
    rate: str
    amount: str
    amount_minor: int
    converted: str
    converted_minor: int
