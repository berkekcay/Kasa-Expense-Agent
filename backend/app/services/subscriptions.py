"""Recurring charge detection (owner: track MONEY).

The algorithm (`find_recurring`) is pure; `detect_subscriptions` feeds it the user's
personal expenses of the last ~2 years and stores the result.

1. Group charges by `merchant_key` ("NETFLIX.COM 12345", "Netflix" -> "netflix").
2. For each period and each charge as the newest member, build a chain backwards. The
   charge before a chain member is expected one period earlier, on the calendar: 7 days
   (+-1 day) for weekly, the same day of the previous month (+-4 days, so 27-35 days apart,
   month ends clamped) for monthly, the same day a year earlier (+-7 days) for yearly. A
   charge joins when it is near that date and its amount is within 10% of the newest charge
   (same original currency; converted expenses are compared in their original currency, so
   a moving USD/TRY rate does not break a USD subscription). Charges that come too soon
   are skipped as noise; a charge too far back (a missed period) ends the chain.
3. A chain counts when it has at least 3 charges (2 for yearly), at most as many other
   charges of that merchant fall inside its time span (a café visited every day is not a
   weekly subscription), and its newest charge is recent: within two periods of today.
4. Of the valid chains the shortest period wins (a weekly charge also forms a monthly
   chain when every fourth charge is picked), then the most recent and longest chain.

Persistence: one row per user and merchant_key (upsert). Amount and currency are the
newest charge's base-currency amount. next_expected_date = last charge + one period
(months keep the day of month, clamped to the month's end), moved forward by whole periods
until it is today or later. Matching expenses get `subscription_id`. Dismissed rows stay
dismissed and get no links; active rows that are no longer detected are deleted.
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import Expense, Subscription
from app.services import clock
from app.services.errors import NotFound
from app.services.expenses import ensure_user

# --- merchant keys ------------------------------------------------------------------------

# Always removed: domains, legal forms, payment words.
# Always removed: domains, legal forms, payment words.
_HARD_NOISE = frozenset(
    {
        "www",
        "com",
        "net",
        "org",
        "co",
        "io",
        "tr",
        "gov",
        "edu",
        "info",
        "biz",
        "app",
        "ltd",
        "sti",
        "as",
        "inc",
        "llc",
        "gmbh",
        "plc",
        "bv",
        "sa",
        "ab",
        "limited",
        "sirketi",
        "tic",
        "san",
        "ve",
        "pos",
        "sanal",
        "online",
        "odeme",
        "payment",
        "pay",
        "bill",
        "billing",
        "help",
        "helppay",
    }
)
# Removed only when a real name is left: payment processors, app stores, cities and
# countries on card statements. "PAYPAL *SPOTIFY" -> "spotify", "Apple" alone -> "apple".
_SOFT_NOISE = frozenset(
    {
        "paypal",
        "iyzico",
        "iyzi",
        "param",
        "payu",
        "stripe",
        "google",
        "apple",
        "itunes",
        "abonelik",
        "subscription",
        "istanbul",
        "ankara",
        "izmir",
        "los",
        "gatos",
        "stockholm",
        "dublin",
        "amsterdam",
        "luxembourg",
        "london",
        "cupertino",
        "us",
        "usa",
        "gb",
        "uk",
        "ie",
        "nl",
        "se",
        "lu",
        "de",
        "tur",
        "turkiye",
        "turkey",
    }
)
_TR_ASCII = str.maketrans(
    {"ı": "i", "ş": "s", "ğ": "g", "ç": "c", "ö": "o", "ü": "u", "â": "a", "î": "i", "û": "u"}
)


def _fold(text: str) -> str:
    lowered = text.replace("İ", "i").replace("I", "ı").lower().translate(_TR_ASCII)
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def merchant_key(merchant: str) -> str:
    """Normalise a merchant name for grouping: Turkish-aware lowercase, diacritics folded,
    punctuation and card-statement noise (references, digits, domains, cities, payment
    processors) removed. "NETFLIX.COM 866-579" -> "netflix", "PAYPAL *SPOTIFY P3A9" ->
    "spotify", "Kahve Dünyası" -> "kahve dunyasi"."""
    tokens = re.split(r"[^a-z0-9]+", _fold(merchant))
    words = [t for t in tokens if len(t) > 1 and not any(ch.isdigit() for ch in t)]
    named = [w for w in words if w not in _HARD_NOISE] or words
    kept = [w for w in named if w not in _SOFT_NOISE] or named
    return " ".join(kept)[:200]


# --- the pure algorithm -------------------------------------------------------------------


@dataclass(frozen=True)
class Charge:
    day: dt.date
    amount_minor: int  # compared for similarity (the original amount when converted)
    currency: str  # currency of amount_minor
    ref: int | None = None  # expense id


@dataclass(frozen=True)
class Period:
    name: str
    tolerance_days: int  # how far a charge may be from its expected calendar date
    min_charges: int
    stale_after: int  # days after the last charge when it is no longer active

    def step(self, day: dt.date, periods: int) -> dt.date:
        """`day` moved by whole periods (negative = earlier); months clamp to the month end."""
        if self.name == "weekly":
            return day + dt.timedelta(days=7 * periods)
        return add_months(day, periods * (1 if self.name == "monthly" else 12))


PERIODS = (
    Period("weekly", 1, 3, 16),
    Period("monthly", 4, 3, 65),
    Period("yearly", 7, 2, 740),
)
AMOUNT_TOLERANCE_PCT = 10


@dataclass(frozen=True)
class Recurring:
    period: str
    charges: tuple[Charge, ...]  # oldest first; the last one is the newest

    @property
    def last(self) -> Charge:
        return self.charges[-1]


def _similar(amount: int, reference: int) -> bool:
    return abs(amount - reference) * 100 <= AMOUNT_TOLERANCE_PCT * abs(reference)


def _chain(charges: Sequence[Charge], head: int, period: Period) -> list[Charge]:
    newest = charges[head]
    chain = [newest]
    for j in range(head - 1, -1, -1):
        candidate = charges[j]
        offset = (candidate.day - period.step(chain[-1].day, -1)).days
        if offset < -period.tolerance_days:
            break
        if offset > period.tolerance_days:
            continue
        if candidate.currency == newest.currency and _similar(candidate.amount_minor, newest.amount_minor):
            chain.append(candidate)
    chain.reverse()
    return chain


def find_recurring(charges: Sequence[Charge], today: dt.date) -> Recurring | None:
    """The recurring pattern in one merchant's charges, or None (see the module docstring)."""
    ordered = sorted(charges, key=lambda c: (c.day, c.ref or 0))
    for period in PERIODS:  # shortest period first
        best: list[Charge] | None = None
        for head in range(len(ordered) - 1, -1, -1):
            if (today - ordered[head].day).days > period.stale_after:
                break  # older heads are even staler
            chain = _chain(ordered, head, period)
            if len(chain) < period.min_charges:
                continue
            members = {id(c) for c in chain}
            span_start, span_end = chain[0].day, chain[-1].day
            others = sum(1 for c in ordered if span_start <= c.day <= span_end and id(c) not in members)
            if others > len(chain):
                continue
            if best is None or len(chain) > len(best):
                best = chain
            # Heads are visited newest first, so the first valid chain is the most recent;
            # an older head only wins with a longer chain.
        if best is not None:
            return Recurring(period.name, tuple(best))
    return None


def add_months(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_charge(last: dt.date, period: str, today: dt.date) -> dt.date:
    """The first expected charge after `last` that is today or later."""
    rule = next(p for p in PERIODS if p.name == period)
    steps = 1
    while rule.step(last, steps) < today:
        steps += 1
    return rule.step(last, steps)


# --- persistence --------------------------------------------------------------------------

LOOKBACK_DAYS = 800


def _charges_by_key(db: Session, user_id: str, since: dt.date) -> dict[str, list[tuple[Charge, Expense]]]:
    rows = db.scalars(
        select(Expense)
        .where(Expense.owner_id == user_id, Expense.house_id.is_(None), Expense.expense_date >= since)
        .order_by(Expense.expense_date, Expense.id)
    )
    groups: dict[str, list[tuple[Charge, Expense]]] = defaultdict(list)
    for e in rows:
        key = merchant_key(e.merchant)
        if not key:
            continue
        charge = Charge(
            day=e.expense_date,
            amount_minor=e.original_total_minor if e.original_total_minor is not None else e.total_minor,
            currency=e.original_currency or e.currency,
            ref=e.id,
        )
        groups[key].append((charge, e))
    return groups


def detect_subscriptions(db: Session, user_id: str, *, today: dt.date | None = None) -> list[Subscription]:
    """Scan the user's expenses, upsert detected subscriptions, return the active ones."""
    today = today or clock.today()
    ensure_user(db, user_id)
    existing = {
        s.merchant_key: s for s in db.scalars(select(Subscription).where(Subscription.user_id == user_id))
    }
    found: set[str] = set()

    for key, pairs in _charges_by_key(db, user_id, today - dt.timedelta(days=LOOKBACK_DAYS)).items():
        recurring = find_recurring([c for c, _ in pairs], today)
        if recurring is None:
            continue
        found.add(key)
        by_id = {e.id: e for _, e in pairs}
        newest = by_id[recurring.last.ref]
        sub = existing.get(key)
        if sub is None:
            sub = Subscription(user_id=user_id, merchant_key=key, status="active")
            db.add(sub)
            existing[key] = sub
        sub.display_name = newest.merchant[:200]
        sub.amount_minor = newest.total_minor
        sub.currency = newest.currency
        sub.period = recurring.period
        sub.last_charge_date = newest.expense_date
        sub.next_expected_date = next_charge(newest.expense_date, recurring.period, today)
        db.flush()
        _unlink(db, user_id, sub.id)
        if sub.status == "active":
            for charge in recurring.charges:
                by_id[charge.ref].subscription_id = sub.id

    for key, sub in existing.items():
        if key not in found and sub.status == "active":
            _unlink(db, user_id, sub.id)
            db.delete(sub)
    db.commit()
    return list_subscriptions(db, user_id)


def _unlink(db: Session, user_id: str, subscription_id: int) -> None:
    db.execute(
        update(Expense)
        .where(Expense.owner_id == user_id, Expense.subscription_id == subscription_id)
        .values(subscription_id=None)
        .execution_options(synchronize_session="fetch")
    )


def list_subscriptions(db: Session, user_id: str, *, include_dismissed: bool = False) -> list[Subscription]:
    """Active subscriptions (plus dismissed ones if asked), soonest next charge first."""
    stmt = select(Subscription).where(Subscription.user_id == user_id)
    if not include_dismissed:
        stmt = stmt.where(Subscription.status == "active")
    stmt = stmt.order_by(Subscription.status, Subscription.next_expected_date, Subscription.id)
    return list(db.scalars(stmt))


def get_subscription(db: Session, user_id: str, subscription_id: int) -> Subscription:
    sub = db.get(Subscription, subscription_id)
    if sub is None or sub.user_id != user_id:
        raise NotFound(f"subscription {subscription_id} not found")
    return sub


def dismiss_subscription(db: Session, user_id: str, subscription_id: int) -> Subscription:
    """Mark as "not a subscription": hidden from lists and upcoming charges, its expenses
    unlinked, and detection never re-activates it."""
    sub = get_subscription(db, user_id, subscription_id)
    sub.status = "dismissed"
    _unlink(db, user_id, sub.id)
    db.commit()
    return sub


def upcoming_charges(db: Session, user_id: str, *, within_days: int = 30) -> list[Subscription]:
    """Active subscriptions whose next_expected_date is within the next `within_days`
    (today included), soonest first."""
    today = clock.today()
    stmt = (
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.next_expected_date >= today,
            Subscription.next_expected_date <= today + dt.timedelta(days=max(0, within_days)),
        )
        .order_by(Subscription.next_expected_date, Subscription.id)
    )
    return list(db.scalars(stmt))
