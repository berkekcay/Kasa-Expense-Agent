"""Track MONEY: the dashboard summary (no LLM), through the service and the API.
"Today" is frozen at 2026-06-20 so every month boundary is known."""

from __future__ import annotations

import datetime as dt

import pytest

from app.db.models import Expense, InboxItem
from app.db.session import session_for
from app.services import budgets, clock, dashboard, houses
from app.services import subscriptions as subs
from app.services.expenses import ExpenseInput, add_expense

TODAY = dt.date(2026, 6, 20)
JUNE, MAY = dt.date(2026, 6, 1), dt.date(2026, 5, 1)


@pytest.fixture(autouse=True)
def _frozen_today(monkeypatch):
    monkeypatch.setattr(clock, "today", lambda: TODAY)


def _add(db, user: str, total: str, category: str | None, day: dt.date) -> None:
    add_expense(db, user, ExpenseInput("Shop", total, expense_date=day, category=category))


def _setup(db, me: str, flatmate: str) -> None:
    _add(db, me, "120.00", "market", JUNE)
    _add(db, me, "80.50", "yemek", JUNE)
    _add(db, me, "40.00", None, JUNE)
    _add(db, me, "300.00", "kira", MAY)
    _add(db, me, "55.55", "food", dt.date(2026, 1, 1))
    _add(db, me, "999.00", "food", dt.date(2025, 12, 31))  # before the 6-month window
    _add(db, flatmate, "777.00", "food", JUNE)  # someone else's

    house = houses.create_house(db, me, "Dash flat")
    houses.add_member(db, me, house.id, flatmate)
    # The flatmate pays 100 of utilities: 50 is my share and I owe it.
    houses.add_equal_split_expense(
        db, flatmate, house.id, ExpenseInput("Elektrik", "100", expense_date=JUNE, category="fatura")
    )
    budgets.set_budget(db, me, category="groceries", limit="150")

    for day in (dt.date(2026, 3, 26), dt.date(2026, 4, 26), dt.date(2026, 5, 26)):
        db.add(Expense(owner_id=me, merchant="Spotify", expense_date=day, currency="TRY", total_minor=5999))
    for n, status in enumerate(("pending", "pending", "approved")):
        db.add(
            InboxItem(
                user_id=me,
                source="email",
                external_ref=f"dash-{me}-{n}",
                received_at=dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.UTC).replace(tzinfo=None),
                title="Fatura",
                status=status,
            )
        )
    db.commit()
    subs.detect_subscriptions(db, me)


def test_dashboard_summary_numbers(db):
    me = "dash-me"
    _setup(db, me, "dash-flatmate")
    s = dashboard.dashboard_summary(db, me)

    assert (s.month, s.currency) == (JUNE, "TRY")
    assert s.total_minor == 12000 + 8050 + 4000 + 5000  # house: my 50 share, not the 100
    assert s.previous_month_total_minor == 30000 + 5999
    assert [(c.category, c.total_minor) for c in s.by_category] == [
        ("groceries", 12000),
        ("food", 8050),
        ("utilities", 5000),
        ("uncategorised", 4000),
    ]
    assert [(m.month.month, m.total_minor) for m in s.trend] == [
        (1, 5555),
        (2, 0),
        (3, 5999),
        (4, 5999),
        (5, 35999),
        (6, 29050),
    ]
    [budget] = s.budgets
    assert (budget.budget.category, budget.spent_minor, budget.pct_used, budget.level) == (
        "groceries",
        12000,
        80,
        "warning",
    )
    [spotify] = s.upcoming_subscriptions
    assert (spotify.merchant_key, spotify.next_expected_date) == ("spotify", dt.date(2026, 6, 26))
    [house] = s.house_balances
    assert (house.house_name, house.balance_minor, house.currency) == ("Dash flat", -5000, "TRY")
    assert s.pending_inbox == 2
    assert [(r.expense.merchant, r.expense.total_minor, r.my_amount_minor) for r in s.recent_expenses] == [
        ("Elektrik", 10000, 5000),
        ("Shop", 4000, 4000),
        ("Shop", 8050, 8050),
        ("Shop", 12000, 12000),
        ("Spotify", 5999, 5999),
    ]


def test_dashboard_for_a_new_user_is_all_zero(db):
    s = dashboard.dashboard_summary(db, "dash-nobody", dt.date(2026, 3, 17))
    assert s.month == dt.date(2026, 3, 1)
    assert (s.total_minor, s.previous_month_total_minor, s.pending_inbox) == (0, 0, 0)
    assert s.by_category == [] and s.budgets == [] and s.house_balances == [] and s.recent_expenses == []
    assert [m.month for m in s.trend] == [dt.date(2025, 10 + k, 1) for k in range(3)] + [
        dt.date(2026, k, 1) for k in (1, 2, 3)
    ]


def test_dashboard_api_shape(client):
    me = "dash-api"
    with session_for(me) as db:
        _setup(db, me, "dash-api-flatmate")
    r = client.get("/dashboard", headers={"X-User-Id": me})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["month"], body["currency"], body["total"], body["total_minor"]) == (
        "2026-06-01",
        "TRY",
        "290.50",
        29050,
    )
    assert (body["previous_month_total"], body["previous_month_total_minor"]) == ("359.99", 35999)
    assert body["by_category"][0] == {"category": "groceries", "total": "120.00", "total_minor": 12000}
    assert body["trend"][-2:] == [
        {"month": "2026-05-01", "total": "359.99", "total_minor": 35999},
        {"month": "2026-06-01", "total": "290.50", "total_minor": 29050},
    ]
    assert body["house_balances"] == [
        {
            "house_id": body["house_balances"][0]["house_id"],
            "house_name": "Dash flat",
            "balance": "-50.00",
            "balance_minor": -5000,
            "currency": "TRY",
        }
    ]
    assert body["budgets"][0]["level"] == "warning" and body["budgets"][0]["spent"] == "120.00"
    assert body["upcoming_subscriptions"][0]["next_expected_date"] == "2026-06-26"
    first = body["recent_expenses"][0]
    assert (first["merchant"], first["total"], first["my_amount"], first["house_id"] is not None) == (
        "Elektrik",
        "100.00",
        "50.00",
        True,
    )
    assert body["pending_inbox"] == 2

    past = client.get("/dashboard", params={"month": "2020-02-10"}, headers={"X-User-Id": me}).json()
    assert (
        past["month"] == "2020-02-01" and past["total_minor"] == 0 and past["budgets"][0]["spent_minor"] == 0
    )
