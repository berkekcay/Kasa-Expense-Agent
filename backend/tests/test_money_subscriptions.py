"""Track MONEY: merchant keys, the pure recurring-charge detector on synthetic histories
(with noise), and persistence (upsert, links, dismiss, upcoming, API)."""

from __future__ import annotations

import datetime as dt
import random

import pytest

from app.db.models import Expense, Subscription
from app.services import clock
from app.services import subscriptions as subs
from app.services.errors import NotFound
from app.services.subscriptions import Charge, find_recurring

TODAY = dt.date(2026, 6, 15)


def monthly(start: dt.date, count: int, amount: int, day_jitter: list[int] | None = None) -> list[Charge]:
    jitter = day_jitter or [0] * count
    return [
        Charge(subs.add_months(start, i) + dt.timedelta(days=jitter[i]), amount, "TRY", ref=1000 + i)
        for i in range(count)
    ]


def every(start: dt.date, days: int, count: int, amount: int, ref0: int = 0) -> list[Charge]:
    return [Charge(start + dt.timedelta(days=days * i), amount, "TRY", ref=ref0 + i) for i in range(count)]


# --- merchant keys ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("NETFLIX.COM 12345", "netflix"),
        ("Netflix", "netflix"),
        ("netflix.com/bill 866-579-7172 CA", "netflix ca"),
        ("PAYPAL *SPOTIFY P3A9F2", "spotify"),
        ("Spotify AB Stockholm", "spotify"),
        ("APPLE.COM/BILL", "apple"),
        ("Apple", "apple"),
        ("GOOGLE *YouTubePremium g.co/helppay#", "youtubepremium"),
        ("Kahve Dünyası", "kahve dunyasi"),
        ("KAHVE DÜNYASI 34 IST", "kahve dunyasi ist"),
        ("İSTANBULKART DOLUM", "istanbulkart dolum"),
        ("Migros Ticaret A.Ş.", "migros ticaret"),
        ("Café Nero", "cafe nero"),
        ("12345", ""),
    ],
)
def test_merchant_key(raw, key):
    assert subs.merchant_key(raw) == key


def test_merchant_key_groups_statement_noise():
    variants = ["NETFLIX.COM 12345", "Netflix", "NETFLIX.COM 99812", "netflix", "Netflix.com"]
    assert {subs.merchant_key(v) for v in variants} == {"netflix"}


# --- the pure detector --------------------------------------------------------------------


def test_monthly_with_jitter_and_one_off_noise():
    charges = monthly(dt.date(2026, 1, 3), 6, 14999, day_jitter=[0, 2, -1, 1, 0, 3])
    charges.append(Charge(dt.date(2026, 3, 20), 89900, "TRY", ref=1))  # a one-off gift card
    found = find_recurring(charges, TODAY)
    assert found is not None and found.period == "monthly"
    assert len(found.charges) == 6 and found.last.day == dt.date(2026, 6, 6)


def test_weekly_and_yearly():
    weekly = every(dt.date(2026, 5, 4), 7, 6, 25000)
    assert find_recurring(weekly, TODAY).period == "weekly"  # not "monthly" by picking every 4th

    yearly = [Charge(dt.date(2024, 9, 1), 39900, "TRY", 1), Charge(dt.date(2025, 8, 30), 41900, "TRY", 2)]
    found = find_recurring(yearly, TODAY)
    assert found.period == "yearly" and len(found.charges) == 2


def test_month_end_billing():
    days = [dt.date(2026, 1, 31), dt.date(2026, 2, 28), dt.date(2026, 3, 31), dt.date(2026, 4, 30)]
    charges = [Charge(d, 5000, "TRY", ref=i) for i, d in enumerate(days)]
    assert find_recurring(charges, dt.date(2026, 5, 10)).period == "monthly"


def test_amounts_within_ten_percent_only():
    ok = monthly(dt.date(2026, 3, 10), 4, 10000)
    ok[0] = Charge(ok[0].day, 9100, "TRY", ok[0].ref)  # 9% below the newest
    assert find_recurring(ok, TODAY) is not None

    bad = monthly(dt.date(2026, 3, 10), 4, 10000)
    bad = [Charge(c.day, a, "TRY", c.ref) for c, a in zip(bad, [10000, 13000, 7000, 10000], strict=True)]
    assert find_recurring(bad, TODAY) is None


def test_not_enough_charges_or_stale():
    assert find_recurring(monthly(dt.date(2026, 4, 10), 2, 10000), TODAY) is None
    lapsed = monthly(dt.date(2025, 6, 1), 6, 10000)  # last charge 2025-11-01
    assert find_recurring(lapsed, TODAY) is None
    one_year = [Charge(dt.date(2025, 7, 1), 10000, "TRY", 1)]
    assert find_recurring(one_year, TODAY) is None


def test_different_currencies_do_not_chain():
    charges = monthly(dt.date(2026, 2, 5), 4, 1000)
    charges = [Charge(c.day, c.amount_minor, "USD" if i % 2 else "TRY", c.ref) for i, c in enumerate(charges)]
    assert find_recurring(charges, TODAY) is None


def test_daily_coffee_and_irregular_groceries_are_not_subscriptions():
    rng = random.Random(7)
    coffee = every(dt.date(2026, 4, 1), 1, 70, 4500)
    assert find_recurring(coffee, TODAY) is None

    day = dt.date(2026, 1, 2)
    groceries = []
    for i in range(40):
        day += dt.timedelta(days=rng.randint(1, 9))
        groceries.append(Charge(day, rng.randint(8000, 60000), "TRY", ref=i))
    assert find_recurring(groceries, TODAY) is None


def test_a_missed_month_breaks_the_chain_but_the_recent_run_counts():
    charges = monthly(dt.date(2025, 10, 9), 3, 9999) + monthly(dt.date(2026, 3, 9), 4, 9999)
    found = find_recurring(charges, TODAY)
    assert found.period == "monthly" and [c.day.month for c in found.charges] == [3, 4, 5, 6]


def test_random_histories_with_a_hidden_subscription():
    """Fuzz: a monthly charge hidden among random purchases at the same merchant."""
    rng = random.Random(42)
    for _ in range(30):
        sub = monthly(dt.date(2026, 1, 12), 6, 19900, day_jitter=[rng.randint(-2, 2) for _ in range(6)])
        noise = [
            Charge(
                dt.date(2026, 1, 1) + dt.timedelta(days=rng.randint(0, 160)),
                rng.randint(1000, 90000),
                "TRY",
                5000 + k,
            )
            for k in range(rng.randint(0, 4))
        ]
        found = find_recurring(sub + noise, TODAY)
        assert found is not None and found.period == "monthly", (sub, noise)
        assert found.last.amount_minor == 19900 or abs(found.last.amount_minor - 19900) * 10 <= 19900


def test_next_charge():
    assert subs.next_charge(dt.date(2026, 1, 31), "monthly", dt.date(2026, 2, 1)) == dt.date(2026, 2, 28)
    assert subs.next_charge(dt.date(2026, 1, 31), "monthly", dt.date(2026, 3, 1)) == dt.date(2026, 3, 31)
    assert subs.next_charge(dt.date(2026, 6, 1), "weekly", dt.date(2026, 6, 20)) == dt.date(2026, 6, 22)
    assert subs.next_charge(dt.date(2024, 2, 29), "yearly", dt.date(2024, 3, 1)) == dt.date(2025, 2, 28)
    assert subs.next_charge(dt.date(2026, 6, 10), "monthly", dt.date(2026, 6, 10)) == dt.date(2026, 7, 10)


# --- persistence --------------------------------------------------------------------------


def _expense(db, user: str, merchant: str, day: dt.date, total: int, **extra) -> Expense:
    e = Expense(
        owner_id=user, merchant=merchant, expense_date=day, currency="TRY", total_minor=total, **extra
    )
    db.add(e)
    return e


def _history(db, user: str) -> None:
    from app.services.expenses import ensure_user

    ensure_user(db, user)
    for i, name in enumerate(["NETFLIX.COM 4411", "Netflix", "NETFLIX.COM 9921", "Netflix.com"]):
        _expense(db, user, name, subs.add_months(dt.date(2026, 3, 2), i), 22999)
    for i in range(4):  # a USD subscription: TRY totals move with the rate, USD amount does not
        _expense(
            db,
            user,
            "PAYPAL *SPOTIFY",
            subs.add_months(dt.date(2026, 3, 20), i) if i < 3 else dt.date(2026, 6, 18),
            40000 + 731 * i,
            original_currency="USD",
            original_total_minor=999,
        )
    for d, amount in [(1, 45000), (4, 12000), (11, 89000), (13, 30000), (25, 61000)]:
        _expense(db, user, "Migros", dt.date(2026, 5, d), amount)
    _expense(db, user, "Netflix", dt.date(2026, 6, 1), 349900)  # a one-off at the same merchant
    db.commit()


def test_detect_persists_links_and_is_idempotent(db):
    user = "sub-detect"
    _history(db, user)
    found = subs.detect_subscriptions(db, user, today=TODAY)
    assert [(s.merchant_key, s.period, s.amount_minor, s.currency) for s in found] == [
        ("netflix", "monthly", 22999, "TRY"),
        ("spotify", "monthly", 42193, "TRY"),
    ]
    netflix, spotify = found
    assert netflix.last_charge_date == dt.date(2026, 6, 2)
    assert netflix.next_expected_date == dt.date(2026, 7, 2)
    assert netflix.display_name == "Netflix.com"
    assert spotify.next_expected_date == dt.date(2026, 7, 18)

    linked = db.query(Expense).filter(Expense.owner_id == user, Expense.subscription_id == netflix.id).count()
    assert linked == 4  # not the one-off
    ids = (netflix.id, spotify.id)
    again = subs.detect_subscriptions(db, user, today=TODAY)
    assert tuple(s.id for s in again) == ids
    assert db.query(Subscription).filter(Subscription.user_id == user).count() == 2


def test_dismissed_stays_dismissed_and_stale_ones_go(db):
    user = "sub-dismiss"
    _history(db, user)
    netflix, _spotify = subs.detect_subscriptions(db, user, today=TODAY)
    with pytest.raises(NotFound):
        subs.dismiss_subscription(db, "sub-intruder", netflix.id)
    subs.dismiss_subscription(db, user, netflix.id)
    assert db.query(Expense).filter(Expense.subscription_id == netflix.id).count() == 0

    active = subs.detect_subscriptions(db, user, today=TODAY)
    assert [s.merchant_key for s in active] == ["spotify"]
    everything = subs.list_subscriptions(db, user, include_dismissed=True)
    assert [(s.merchant_key, s.status) for s in everything] == [
        ("spotify", "active"),
        ("netflix", "dismissed"),
    ]
    assert db.query(Expense).filter(Expense.subscription_id == netflix.id).count() == 0

    # Months later nothing recurs any more: the active one is removed, the dismissed one kept.
    later = subs.detect_subscriptions(db, user, today=dt.date(2026, 12, 1))
    assert later == []
    assert [s.merchant_key for s in subs.list_subscriptions(db, user, include_dismissed=True)] == ["netflix"]
    assert (
        db.query(Expense).filter(Expense.owner_id == user, Expense.subscription_id.is_not(None)).count() == 0
    )


def test_upcoming_charges_window(db, monkeypatch):
    user = "sub-upcoming"
    _history(db, user)
    subs.detect_subscriptions(db, user, today=TODAY)
    monkeypatch.setattr(clock, "today", lambda: dt.date(2026, 6, 25))
    assert [s.merchant_key for s in subs.upcoming_charges(db, user, within_days=7)] == ["netflix"]
    assert [s.merchant_key for s in subs.upcoming_charges(db, user, within_days=30)] == ["netflix", "spotify"]
    monkeypatch.setattr(clock, "today", lambda: dt.date(2026, 7, 3))
    assert [s.merchant_key for s in subs.upcoming_charges(db, user, within_days=30)] == ["spotify"]


def test_subscription_api(client, monkeypatch):
    from app.db.session import session_for

    user, other = {"X-User-Id": "sub-api"}, {"X-User-Id": "sub-api-other"}
    with session_for("sub-api") as db:
        _history(db, "sub-api")
    monkeypatch.setattr(clock, "today", lambda: TODAY)

    assert client.get("/subscriptions", headers=user).json() == []
    r = client.post("/subscriptions/detect", headers=user)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body[0] == {
        "id": body[0]["id"],
        "merchant_key": "netflix",
        "display_name": "Netflix.com",
        "amount": "229.99",
        "amount_minor": 22999,
        "currency": "TRY",
        "period": "monthly",
        "last_charge_date": "2026-06-02",
        "next_expected_date": "2026-07-02",
        "status": "active",
    }
    upcoming = client.get("/subscriptions/upcoming", params={"within_days": 20}, headers=user).json()
    assert [s["merchant_key"] for s in upcoming] == ["netflix"]
    assert client.get("/subscriptions/upcoming", params={"within_days": -1}, headers=user).status_code == 422

    sub_id = body[0]["id"]
    assert client.post(f"/subscriptions/{sub_id}/dismiss", headers=other).status_code == 404
    r = client.post(f"/subscriptions/{sub_id}/dismiss", headers=user)
    assert r.json()["status"] == "dismissed"
    assert [s["merchant_key"] for s in client.get("/subscriptions", headers=user).json()] == ["spotify"]
    listed = client.get("/subscriptions", params={"include_dismissed": True}, headers=user).json()
    assert len(listed) == 2
    assert client.get("/subscriptions", headers=other).json() == []
