"""Currency conversion with TCMB rates (owner: track MONEY).

Rates are cached in `fx_rates` (TRY per 1 unit, TCMB "ForexSelling", per day). A purchase
on a weekend or holiday uses the latest rate published on or before that day. Conversion
is Decimal math rounded half-up to whole minor units; never floats.

`apply_base_currency` is the FX half of the expense pipeline hook
(`services.expenses.finalize_expense`). Until it is implemented it leaves foreign-currency
expenses unconverted and says so in a warning; personal expenses then keep their currency
and house expenses in another currency are rejected (InvalidInput), as in Sprint 1.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Expense


@dataclass(frozen=True)
class Rate:
    currency: str
    rate_date: dt.date  # the TCMB publication date actually used (may be before the asked day)
    try_per_unit: Decimal


def get_rate(db: Session, currency: str, on: dt.date) -> Rate:
    """Latest rate for `currency` published on or before `on`. Reads fx_rates first; on a
    miss, fetches from TCMB (`integrations.tcmb`), stores the whole day, and retries.
    TRY returns Rate("TRY", on, Decimal(1)). Raises InvalidInput for unknown currencies and
    UpstreamError when TCMB cannot be reached and nothing is cached."""
    raise NotImplementedError("get_rate: track MONEY")


def convert_minor(
    amount_minor: int, from_try_per_unit: Decimal, to_try_per_unit: Decimal = Decimal(1)
) -> int:
    """Convert minor units between two currencies given each one's TRY-per-unit rate.
    amount * from / to, rounded ROUND_HALF_UP to an integer."""
    raise NotImplementedError("convert_minor: track MONEY")


def convert(
    db: Session, amount_minor: int, from_currency: str, to_currency: str, on: dt.date
) -> tuple[int, Decimal]:
    """Convert an amount; returns (converted_minor, rate) where rate = to_currency units per
    1 from_currency unit (what gets stored in Expense.fx_rate when the base is TRY)."""
    raise NotImplementedError("convert: track MONEY")


def apply_base_currency(db: Session, expense: Expense, base_currency: str) -> list[str]:
    """Pipeline hook: make `expense` be in `base_currency`.

    When converting: set original_currency / original_total_minor from the current values,
    convert total_minor and every item amount (fix rounding so items still sum like before),
    set currency=base_currency, fx_rate and fx_date (the rate's publication date). Returns
    warnings, e.g. "converted 12.00 EUR at 36.123400 (TCMB 2026-10-10)".
    """
    # Placeholder until track MONEY lands: no conversion.
    if expense.currency == base_currency:
        return []
    return [f"saved in {expense.currency}: currency conversion to {base_currency} is not available yet"]


def refresh_rates(db: Session, on: dt.date | None = None) -> int:
    """Fetch TCMB rates for `on` (default today) into fx_rates; returns rows upserted.
    Called daily by POST /internal/fx/refresh (Cloud Scheduler)."""
    raise NotImplementedError("refresh_rates: track MONEY")
