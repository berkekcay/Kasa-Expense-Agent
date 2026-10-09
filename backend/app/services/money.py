"""Exact money conversions. Amounts are integer minor units (kuruş/cents) internally.

Sprint 1 assumes 2-decimal currencies (TRY, EUR, USD, GBP).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MINOR_PER_MAJOR = 100


class MoneyError(ValueError):
    pass


def to_minor(amount: Decimal | str | int) -> int:
    """'12.5' -> 1250. Rejects floats, NaN and more than 2 decimal places (no silent rounding)."""
    if isinstance(amount, float):
        raise MoneyError("floats are not accepted for money; pass a string or Decimal")
    try:
        value = Decimal(str(amount).strip().replace(",", "."))
    except InvalidOperation as exc:
        raise MoneyError(f"not a valid amount: {amount!r}") from exc
    if not value.is_finite():
        raise MoneyError(f"not a valid amount: {amount!r}")
    minor = value * MINOR_PER_MAJOR
    if minor != minor.to_integral_value():
        raise MoneyError(f"too many decimal places: {amount!r}")
    return int(minor)


def to_major(minor: int) -> Decimal:
    """1250 -> Decimal('12.50')."""
    return (Decimal(minor) / MINOR_PER_MAJOR).quantize(Decimal("0.01"))


def format_minor(minor: int) -> str:
    return str(to_major(minor))


def normalize_currency(code: str | None, default: str = "TRY") -> str:
    code = (code or default).strip().upper()
    if code in {"TL", "₺"}:
        code = "TRY"
    if len(code) != 3 or not code.isalpha():
        raise MoneyError(f"unknown currency code: {code!r}")
    return code
