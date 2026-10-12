"""Currency conversion with TCMB rates (owner: track MONEY).

Rates
-----
`fx_rates` caches TCMB bulletins: TRY per 1 unit, ForexSelling (see `integrations.tcmb`
for the fallbacks), 6 decimals, one row per day and currency. A whole bulletin is stored
at once. `get_rate(db, currency, on)` returns the latest rate published on or before `on`:

- days after today (Istanbul) are clamped to today;
- it walks back day by day, at most `LOOKBACK_DAYS` (7) days;
- a day already in `fx_rates` is answered from the cache;
- Saturdays and Sundays are skipped without a request (TCMB never publishes then);
- other days are fetched from the dated archive. A 404 (holiday, or today before the
  15:30 bulletin) is remembered in memory (past days for the life of the process, today for
  30 minutes) and the walk goes on to the day before;
- if TCMB cannot be reached, cached older days are still used; with nothing cached the
  result is UpstreamError. A currency TCMB does not publish is InvalidInput.

New rows are only flushed, inside a SAVEPOINT (a concurrent request storing the same day
is not an error). The caller's commit keeps them; `refresh_rates` and the /fx API commit.

Conversion
----------
`convert_minor(amount, from_rate, to_rate) = amount * from_rate / to_rate`, computed with
Decimal (40 digits) on integer minor units and rounded ROUND_HALF_EVEN to whole minor units
(banker's rounding: no upward drift over many conversions). The rounding happens once, on
the final amount. Every currency is treated as having 2 decimals, like `services.money`.
The rate reported (and stored in `Expense.fx_rate`) is from_rate / to_rate rounded half-even
to 6 decimals; when the base is TRY that is exactly the TCMB number used.

Expenses
--------
`apply_base_currency` is the FX half of the pipeline hook (`expenses.finalize_expense`).
If no rate can be found it raises InvalidInput ("could not convert ..."), so nothing is
ever saved in a currency that budgets, dashboards and house balances cannot add up.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Expense, FxRate
from app.integrations import tcmb
from app.services import clock
from app.services.errors import InvalidInput, UpstreamError
from app.services.money import MoneyError, normalize_currency, to_major

log = logging.getLogger(__name__)

LOOKBACK_DAYS = 7
RATE_PLACES = Decimal("0.000001")
_TODAY_MISS_TTL_SECONDS = 30 * 60

# Days TCMB had no bulletin for: day -> time.monotonic() when we saw the 404.
_no_bulletin: dict[dt.date, float] = {}


@dataclass(frozen=True)
class Rate:
    currency: str
    rate_date: dt.date  # the TCMB publication date actually used (may be before the asked day)
    try_per_unit: Decimal


@dataclass(frozen=True)
class Conversion:
    amount_minor: int
    from_currency: str
    to_currency: str
    converted_minor: int
    rate: Decimal  # to_currency per 1 from_currency, 6 decimals
    rate_date: dt.date
    from_try_per_unit: Decimal
    to_try_per_unit: Decimal


def currency_code(code: str | None) -> str:
    try:
        return normalize_currency(code)
    except MoneyError as exc:
        raise InvalidInput(str(exc)) from exc


def format_amount(minor: int) -> str:
    """12345678 -> '123,456.78' (for messages; APIs use plain decimal strings)."""
    return f"{to_major(minor):,}"


def format_rate(rate: Decimal) -> str:
    """At least 4 and at most 6 decimals: 42 -> '42.0000', 0.311727 -> '0.311727'."""
    text = f"{rate.quantize(RATE_PLACES, rounding=ROUND_HALF_EVEN):f}"
    whole, _, frac = text.partition(".")
    frac = frac.rstrip("0").ljust(4, "0")
    return f"{whole}.{frac}"


# --- cache --------------------------------------------------------------------------------


def _cached_rates(db: Session, day: dt.date) -> dict[str, Decimal]:
    rows = db.execute(select(FxRate.currency, FxRate.try_per_unit).where(FxRate.rate_date == day))
    return {code: Decimal(rate).quantize(RATE_PLACES) for code, rate in rows}


def _store_day(db: Session, day: dt.date, rates: dict[str, Decimal]) -> int:
    """Insert or update one bulletin; returns rows written. Flushes, does not commit."""
    existing = {r.currency: r for r in db.scalars(select(FxRate).where(FxRate.rate_date == day))}
    written = 0
    try:
        with db.begin_nested():
            for code, rate in rates.items():
                row = existing.get(code)
                if row is None:
                    db.add(FxRate(rate_date=day, currency=code, try_per_unit=rate, source="TCMB"))
                elif Decimal(row.try_per_unit).quantize(RATE_PLACES) != rate:
                    row.try_per_unit = rate
                else:
                    continue
                written += 1
    except IntegrityError:
        log.info("fx rates for %s were stored by another request", day)
        return 0
    return written


def _known_missing(day: dt.date, today: dt.date) -> bool:
    seen = _no_bulletin.get(day)
    if seen is None:
        return False
    return day < today or time.monotonic() - seen < _TODAY_MISS_TTL_SECONDS


def _resolve_day(db: Session, on: dt.date, want: str | None = None) -> tuple[dt.date, dict[str, Decimal]]:
    """The latest bulletin published on or before `on` (see the module docstring)."""
    today = clock.today()
    day = min(on, today)
    upstream: UpstreamError | None = None
    for back in range(LOOKBACK_DAYS + 1):
        d = day - dt.timedelta(days=back)
        cached = _cached_rates(db, d)
        if cached and (want is None or want in cached):
            return d, cached
        if not cached and (d.weekday() >= 5 or _known_missing(d, today)):
            continue
        if upstream is not None:
            if cached:
                return d, cached
            continue
        try:
            fetched = tcmb.fetch_rates(d)
        except UpstreamError as exc:
            log.warning("TCMB fetch for %s failed: %s", d, exc)
            upstream = exc
            if cached:
                return d, cached
            continue
        if fetched is None:
            _no_bulletin[d] = time.monotonic()
            if cached:
                return d, cached
            continue
        published, rates = fetched
        _store_day(db, published, rates)
        return published, {**cached, **rates}
    if upstream is not None:
        raise UpstreamError(
            f"TCMB is unreachable and no rate is cached for the {LOOKBACK_DAYS} days up to {day}"
        )
    raise InvalidInput(f"TCMB published no exchange rates in the {LOOKBACK_DAYS} days up to {day}")


# --- public API ---------------------------------------------------------------------------


def get_rate(db: Session, currency: str, on: dt.date) -> Rate:
    """Latest rate for `currency` published on or before `on`. Reads fx_rates first; on a
    miss, fetches from TCMB (`integrations.tcmb`), stores the whole day, and retries.
    TRY returns Rate("TRY", on, Decimal(1)). Raises InvalidInput for unknown currencies and
    UpstreamError when TCMB cannot be reached and nothing is cached."""
    code = currency_code(currency)
    if code == "TRY":
        return Rate("TRY", on, Decimal(1))
    day, rates = _resolve_day(db, on, want=code)
    if code not in rates:
        raise InvalidInput(f"TCMB does not publish an exchange rate for {code}")
    return Rate(code, day, rates[code])


def rates_for_day(db: Session, on: dt.date) -> list[Rate]:
    """Every TCMB rate of the latest bulletin on or before `on`, sorted by currency."""
    day, rates = _resolve_day(db, on)
    return [Rate(code, day, rates[code]) for code in sorted(rates)]


def convert_minor(
    amount_minor: int, from_try_per_unit: Decimal, to_try_per_unit: Decimal = Decimal(1)
) -> int:
    """Convert minor units between two currencies given each one's TRY-per-unit rate:
    amount * from / to, rounded ROUND_HALF_EVEN to an integer."""
    if from_try_per_unit <= 0 or to_try_per_unit <= 0:
        raise InvalidInput("exchange rates must be positive")
    with localcontext() as ctx:
        ctx.prec = 40
        value = Decimal(amount_minor) * Decimal(from_try_per_unit) / Decimal(to_try_per_unit)
        return int(value.to_integral_value(rounding=ROUND_HALF_EVEN))


def conversion(
    db: Session, amount_minor: int, from_currency: str, to_currency: str, on: dt.date
) -> Conversion:
    """Convert with TCMB rates for `on`; see `Conversion` for what comes back."""
    src, dst = currency_code(from_currency), currency_code(to_currency)
    if src == dst:
        return Conversion(amount_minor, src, dst, amount_minor, Decimal(1), on, Decimal(1), Decimal(1))
    from_rate = get_rate(db, src, on)
    to_rate = get_rate(db, dst, on)
    with localcontext() as ctx:
        ctx.prec = 40
        rate = (from_rate.try_per_unit / to_rate.try_per_unit).quantize(RATE_PLACES, rounding=ROUND_HALF_EVEN)
    return Conversion(
        amount_minor=amount_minor,
        from_currency=src,
        to_currency=dst,
        converted_minor=convert_minor(amount_minor, from_rate.try_per_unit, to_rate.try_per_unit),
        rate=rate,
        rate_date=from_rate.rate_date if src != "TRY" else to_rate.rate_date,
        from_try_per_unit=from_rate.try_per_unit,
        to_try_per_unit=to_rate.try_per_unit,
    )


def convert(
    db: Session, amount_minor: int, from_currency: str, to_currency: str, on: dt.date
) -> tuple[int, Decimal]:
    """Convert an amount; returns (converted_minor, rate) where rate = to_currency units per
    1 from_currency unit (what gets stored in Expense.fx_rate when the base is TRY)."""
    result = conversion(db, amount_minor, from_currency, to_currency, on)
    return result.converted_minor, result.rate


def allocate_proportionally(weights: list[int], target: int) -> list[int]:
    """Split `target` in proportion to `weights` (sum > 0) with the largest remainder method:
    floor every exact share, then give the leftover units one by one to the largest
    remainders (ties: earlier index). The result always sums to `target`."""
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must have a positive sum")
    floors: list[int] = []
    remainders: list[tuple[int, int]] = []
    for index, weight in enumerate(weights):
        quotient, remainder = divmod(target * weight, total)
        floors.append(quotient)
        remainders.append((-remainder, index))
    for _, index in sorted(remainders)[: target - sum(floors)]:
        floors[index] += 1
    return floors


def _convert_items(expense: Expense, result: Conversion, original_total: int) -> None:
    amounts = [item.amount_minor for item in expense.items]
    if not amounts:
        return
    items_total = sum(amounts)
    if items_total <= 0:  # only discount lines or nonsense: convert line by line
        for item in expense.items:
            item.amount_minor = convert_minor(
                item.amount_minor, result.from_try_per_unit, result.to_try_per_unit
            )
        return
    # Items that matched the total still match it. Otherwise (discounts, misread lines) the
    # items' own sum is converted, so the gap between items and total converts with it.
    target = (
        result.converted_minor
        if items_total == original_total
        else convert_minor(items_total, result.from_try_per_unit, result.to_try_per_unit)
    )
    for item, amount in zip(expense.items, allocate_proportionally(amounts, target), strict=True):
        item.amount_minor = amount


def apply_base_currency(db: Session, expense: Expense, base_currency: str) -> list[str]:
    """Pipeline hook: make `expense` be in `base_currency`.

    When converting: keep the original in original_currency / original_total_minor, convert
    total_minor with the TCMB rate for expense_date, scale item amounts with the largest
    remainder method (items that summed to the total still do), set currency, fx_rate
    (base units per 1 original unit) and fx_date (the bulletin's date). Returns one warning
    like "Converted 25.00 USD to 1,050.00 TRY at TCMB rate 42.0000 (2026-10-08)."
    Raises InvalidInput when no rate can be found.
    """
    base = currency_code(base_currency)
    current = currency_code(expense.currency)
    expense.currency = current
    if current == base:
        return []
    original_total = expense.total_minor
    on = expense.expense_date or clock.today()
    try:
        result = conversion(db, original_total, current, base, on)
    except (InvalidInput, UpstreamError) as exc:
        raise InvalidInput(
            f"could not convert {format_amount(original_total)} {current} to {base}: {exc}. "
            f"Enter the amount in {base} or try again later."
        ) from exc
    if result.converted_minor <= 0:
        raise InvalidInput(f"{format_amount(original_total)} {current} is too small to convert to {base}")

    _convert_items(expense, result, original_total)
    expense.original_currency = current
    expense.original_total_minor = original_total
    expense.currency = base
    expense.total_minor = result.converted_minor
    expense.fx_rate = result.rate
    expense.fx_date = result.rate_date
    message = (
        f"Converted {format_amount(original_total)} {current} to {format_amount(result.converted_minor)} "
        f"{base} at TCMB rate {format_rate(result.rate)} ({result.rate_date.isoformat()})."
    )
    return [message]


def refresh_rates(db: Session, on: dt.date | None = None) -> int:
    """Fetch the TCMB bulletin for `on` (default: today.xml, the latest one) into fx_rates
    and commit. Returns how many currencies it had (0 when TCMB has no file for that day).
    Called daily by POST /internal/fx/refresh (Cloud Scheduler)."""
    fetched = tcmb.fetch_rates(on)
    if fetched is None:
        return 0
    published, rates = fetched
    _store_day(db, published, rates)
    db.commit()
    return len(rates)
