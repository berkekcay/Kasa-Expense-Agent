"""Exchange rates (owner: track MONEY). TCMB rates, cached in fx_rates.

Errors: 422 unknown currency or no bulletin in the 7 days before the date, 502 TCMB
unreachable with nothing cached.
"""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import DB, CurrentUser
from app.schemas.common import Amount
from app.schemas.fx import FxConvertOut, FxRateOut, FxRatesOut
from app.services import clock
from app.services import fx as fx_service
from app.services.money import to_minor

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates", response_model=FxRatesOut, summary="All TCMB rates for a day")
def get_rates(db: DB, _user_id: CurrentUser, on: dt.date | None = None) -> FxRatesOut:
    """The latest TCMB bulletin published on or before `on` (default: today)."""
    rates = fx_service.rates_for_day(db, on or clock.today())
    db.commit()
    return FxRatesOut(
        rate_date=rates[0].rate_date if rates else (on or clock.today()),
        rates=[FxRateOut.from_rate(r) for r in rates],
    )


@router.get("/rates/{currency}", response_model=FxRateOut, summary="One TCMB rate")
def get_rate(currency: str, db: DB, _user_id: CurrentUser, on: dt.date | None = None) -> FxRateOut:
    """TRY per 1 unit of `currency`, from the latest bulletin on or before `on`."""
    rate = fx_service.get_rate(db, currency, on or clock.today())
    db.commit()
    return FxRateOut.from_rate(rate)


@router.get("/convert", response_model=FxConvertOut, summary="Convert an amount (preview)")
def convert(
    db: DB,
    _user_id: CurrentUser,
    amount: Annotated[Amount, Query(gt=0, decimal_places=2)],
    from_currency: Annotated[str, Query(min_length=2, max_length=3, alias="from")],
    to_currency: Annotated[str, Query(min_length=2, max_length=3, alias="to")] = "TRY",
    on: dt.date | None = None,
) -> FxConvertOut:
    """Exact Decimal conversion with TCMB rates, rounded half-even to 2 decimals. Nothing
    is saved except the rates themselves."""
    result = fx_service.conversion(db, to_minor(amount), from_currency, to_currency, on or clock.today())
    db.commit()
    return FxConvertOut.from_conversion(result)
