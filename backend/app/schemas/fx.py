"""FX schemas (owner: track MONEY)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field

from app.services.fx import Conversion, Rate
from app.services.money import format_minor


class FxRateOut(BaseModel):
    currency: str
    rate_date: dt.date = Field(description="TCMB bulletin date used (on or before the asked day)")
    try_per_unit: str = Field(description="TRY per 1 unit, 6 decimals (TCMB ForexSelling / Unit)")

    @classmethod
    def from_rate(cls, r: Rate) -> FxRateOut:
        return cls(currency=r.currency, rate_date=r.rate_date, try_per_unit=f"{r.try_per_unit:.6f}")


class FxRatesOut(BaseModel):
    rate_date: dt.date = Field(description="TCMB bulletin date used (on or before the asked day)")
    rates: list[FxRateOut]


class FxConvertOut(BaseModel):
    from_currency: str
    to_currency: str
    on: dt.date = Field(description="TCMB bulletin date used (on or before the asked day)")
    rate: str = Field(description="to_currency per 1 from_currency, 6 decimals")
    amount: str
    amount_minor: int
    converted: str = Field(description="Exact conversion rounded half-even to 2 decimals")
    converted_minor: int

    @classmethod
    def from_conversion(cls, c: Conversion) -> FxConvertOut:
        return cls(
            from_currency=c.from_currency,
            to_currency=c.to_currency,
            on=c.rate_date,
            rate=f"{c.rate:.6f}",
            amount=format_minor(c.amount_minor),
            amount_minor=c.amount_minor,
            converted=format_minor(c.converted_minor),
            converted_minor=c.converted_minor,
        )
