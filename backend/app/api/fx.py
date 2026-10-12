"""Exchange rates (owner: track MONEY)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import DB, CurrentUser
from app.schemas.common import Amount
from app.schemas.fx import FxConvertOut, FxRateOut
from app.services import clock
from app.services import fx as fx_service

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates/{currency}", response_model=FxRateOut)
def get_rate(currency: str, db: DB, _user_id: CurrentUser, on: dt.date | None = None) -> FxRateOut:
    fx_service.get_rate(db, currency, on or clock.today())
    raise NotImplementedError("GET /fx/rates/{currency}: track MONEY")


@router.get("/convert", response_model=FxConvertOut)
def convert(
    db: DB,
    _user_id: CurrentUser,
    amount: Annotated[Amount, Query(gt=0, decimal_places=2)],
    from_currency: Annotated[str, Query(min_length=3, max_length=3, alias="from")],
    to_currency: Annotated[str, Query(min_length=3, max_length=3, alias="to")] = "TRY",
    on: dt.date | None = None,
) -> FxConvertOut:
    raise NotImplementedError("GET /fx/convert: track MONEY")
