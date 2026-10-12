"""Types shared by every schema module."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from app.services.money import format_minor

Amount = Decimal  # validated to max 2 decimal places via Field(decimal_places=2)


class MoneyOut(BaseModel):
    """An exact amount: decimal string for display plus integer minor units."""

    amount: str
    amount_minor: int
    currency: str

    @classmethod
    def of(cls, minor: int, currency: str) -> MoneyOut:
        return cls(amount=format_minor(minor), amount_minor=minor, currency=currency)


def money_str(minor: int | None) -> str | None:
    return None if minor is None else format_minor(minor)
