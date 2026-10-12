"""Track MONEY: budgets CRUD, monthly status (personal + own house shares), and the alerts
the expense pipeline returns. All amounts are TRY, so no exchange rates are needed."""

from __future__ import annotations

import datetime as dt

import pytest

from app.services import budgets, clock, houses
from app.services.errors import InvalidInput, NotFound
from app.services.expenses import ExpenseInput, add_expense, build_expense


def _user(name: str) -> dict[str, str]:
    return {"X-User-Id": name}


def _spend(db, user: str, total: str, category: str | None, day: dt.date | None = None):
    return add_expense(
        db, user, ExpenseInput("Shop", total, expense_date=day or clock.today(), category=category)
    )


def test_set_budget_upserts_and_normalises(db):
    user = "bud-crud"
    first = budgets.set_budget(db, user, category="Market", limit="3000")
    assert (first.category, first.limit_minor, first.currency, first.alert_threshold_pct) == (
        "groceries",
        300000,
        "TRY",
        80,
    )
    again = budgets.set_budget(db, user, category="groceries", limit="2500.50", alert_threshold_pct=90)
    assert again.id == first.id and again.limit_minor == 250050 and again.alert_threshold_pct == 90

    overall = budgets.set_budget(db, user, category="genel", limit="10000", currency="TL")
    assert overall.category is None
    assert budgets.set_budget(db, user, category="", limit="12000").id == overall.id
    assert budgets.set_budget(db, user, category=None, limit="12000").id == overall.id
    budgets.set_budget(db, user, category="ulaşım", limit="800")
    assert [b.category for b in budgets.list_budgets(db, user)] == [None, "groceries", "transport"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"category": "uzay gemisi", "limit": "100"},
        {"category": "food", "limit": "0"},
        {"category": "food", "limit": "12.345"},
        {"category": "food", "limit": "abc"},
        {"category": "food", "limit": "100", "currency": "USD"},
        {"category": "food", "limit": "100", "alert_threshold_pct": 0},
        {"category": "food", "limit": "100", "alert_threshold_pct": 101},
    ],
)
def test_set_budget_validation(db, kwargs):
    with pytest.raises(InvalidInput):
        budgets.set_budget(db, "bud-invalid", **kwargs)


def test_delete_budget_only_own(db):
    budget = budgets.set_budget(db, "bud-del", category="food", limit="100")
    with pytest.raises(NotFound):
        budgets.delete_budget(db, "bud-other", budget.id)
    budgets.delete_budget(db, "bud-del", budget.id)
    assert budgets.list_budgets(db, "bud-del") == []
    with pytest.raises(NotFound):
        budgets.delete_budget(db, "bud-del", budget.id)


def test_status_counts_personal_and_own_house_shares_only(db):
    ali, ayse, can = "bud-ali", "bud-ayse", "bud-can"
    this_month = budgets.month_start(clock.today())
    last_month = budgets.add_months(this_month, -1)
    budgets.set_budget(db, ali, category="groceries", limit="1000", alert_threshold_pct=50)
    budgets.set_budget(db, ali, category=None, limit="2000")

    _spend(db, ali, "300", "market", this_month)
    _spend(db, ali, "150.50", "food", this_month)
    _spend(db, ali, "999", "groceries", last_month)  # other month
    _spend(db, ayse, "777", "groceries", this_month)  # other user

    house = houses.create_house(db, ali, "Bud flat")
    houses.add_member(db, ali, house.id, ayse)
    houses.add_member(db, ali, house.id, can)
    # Ali pays 300 of groceries for three people: only his 100 share is his spending.
    houses.add_equal_split_expense(
        db, ali, house.id, ExpenseInput("Migros", "300", expense_date=this_month, category="groceries")
    )
    # Ayşe pays 90 of utilities: Ali's 30 share counts for him, even though he did not pay.
    houses.add_equal_split_expense(
        db, ayse, house.id, ExpenseInput("Elektrik", "90", expense_date=this_month, category="fatura")
    )

    overall, groceries = budgets.budget_status(db, ali, this_month + dt.timedelta(days=3))
    assert overall.budget.category is None and groceries.budget.category == "groceries"
    assert (groceries.spent_minor, groceries.remaining_minor, groceries.pct_used, groceries.level) == (
        40000,
        60000,
        40,
        "ok",
    )
    assert overall.spent_minor == 30000 + 15050 + 10000 + 3000
    assert overall.month == this_month

    previous = budgets.budget_status(db, ali, last_month)
    assert [s.spent_minor for s in previous] == [99900, 99900]

    ayse_spent = budgets.spending_by_category(db, ayse, this_month, budgets.add_months(this_month, 1))
    assert ayse_spent == {"groceries": 77700 + 10000, "utilities": 3000}


def test_levels_and_pct_floor(db):
    user = "bud-levels"
    budget = budgets.set_budget(db, user, category="food", limit="300", alert_threshold_pct=80)
    day = budgets.month_start(clock.today())

    def status():
        return budgets.budget_status(db, user, day)[0]

    _spend(db, user, "239.99", "food", day)
    assert (status().pct_used, status().level) == (79, "ok")
    _spend(db, user, "0.01", "food", day)
    assert (status().pct_used, status().level) == (80, "warning")
    _spend(db, user, "60", "food", day)
    assert (status().pct_used, status().level, status().remaining_minor) == (100, "warning", 0)
    _spend(db, user, "0.01", "food", day)
    assert (status().pct_used, status().level, status().remaining_minor) == (100, "exceeded", -1)
    assert budget.limit_minor == 30000


def test_alerts_only_when_crossing_a_level(db):
    user = "bud-alerts"
    budgets.set_budget(db, user, category="groceries", limit="2000")
    budgets.set_budget(db, user, category=None, limit="4000", alert_threshold_pct=50)
    day = clock.today()

    assert _spend(db, user, "1500", "market", day).warnings == []
    first = _spend(db, user, "200", "market", day).warnings
    assert first == ["Groceries budget: 85% used this month (1,700.00 of 2,000.00 TRY)."]
    assert _spend(db, user, "100", "market", day).warnings == []  # still "warning": no repeat
    crossed = _spend(db, user, "350", "groceries", day).warnings
    assert crossed == [
        "Groceries budget exceeded this month: 2,150.00 of 2,000.00 TRY (107%, 150.00 TRY over).",
        "Overall budget: 53% used this month (2,150.00 of 4,000.00 TRY).",
    ]
    assert _spend(db, user, "100", "food", day).warnings == []  # other category, overall still 56%


def test_alert_names_the_month_for_old_expenses(db):
    user = "bud-old"
    budgets.set_budget(db, user, category="food", limit="100")
    old = budgets.add_months(budgets.month_start(clock.today()), -2) + dt.timedelta(days=4)
    warnings = _spend(db, user, "150", "food", old).warnings
    assert warnings == [f"Food budget exceeded in {old:%Y-%m}: 150.00 of 100.00 TRY (150%, 50.00 TRY over)."]


def test_hook_never_raises_and_ignores_users_without_budgets(db, monkeypatch):
    expense = build_expense("bud-none", ExpenseInput("Shop", "10"))
    assert budgets.warnings_for_new_expense(db, expense) == []

    budgets.set_budget(db, "bud-broken", category="food", limit="10")
    broken = build_expense("bud-broken", ExpenseInput("Shop", "10", category="food"))

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(budgets, "spending_by_category", boom)
    assert budgets.warnings_for_new_expense(db, broken) == []


def test_month_helpers():
    assert budgets.add_months(dt.date(2026, 1, 1), -1) == dt.date(2025, 12, 1)
    assert budgets.add_months(dt.date(2026, 11, 1), 2) == dt.date(2027, 1, 1)
    assert budgets.month_start(dt.date(2026, 2, 28)) == dt.date(2026, 2, 1)


def test_budget_api(client):
    me, other = _user("bud-api"), _user("bud-api-other")
    r = client.put("/budgets", json={"category": "Market", "limit": "3000"}, headers=me)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created == {
        "id": created["id"],
        "category": "groceries",
        "limit": "3000.00",
        "limit_minor": 300000,
        "currency": "TRY",
        "alert_threshold_pct": 80,
    }
    r = client.put("/budgets", json={"limit": "5000", "alert_threshold_pct": 90}, headers=me)
    assert r.json()["category"] is None
    assert client.put("/budgets", json={"category": "xyzzy", "limit": "1"}, headers=me).status_code == 422
    assert client.put("/budgets", json={"category": "food", "limit": "-1"}, headers=me).status_code == 422

    r = client.post(
        "/expenses",
        json={"merchant": "BİM", "total": "2700", "category": "market"},
        headers=me,
    )
    assert r.json()["warnings"] == ["Groceries budget: 90% used this month (2,700.00 of 3,000.00 TRY)."]

    assert [b["category"] for b in client.get("/budgets", headers=me).json()] == [None, "groceries"]
    status = client.get("/budgets/status", headers=me).json()
    assert [
        (s["budget"]["category"], s["spent"], s["remaining"], s["pct_used"], s["level"]) for s in status
    ] == [
        (None, "2700.00", "2300.00", 54, "ok"),
        ("groceries", "2700.00", "300.00", 90, "warning"),
    ]
    assert status[0]["month"] == budgets.month_start(clock.today()).isoformat()
    last = budgets.add_months(budgets.month_start(clock.today()), -1).isoformat()
    past = client.get("/budgets/status", params={"month": last}, headers=me).json()
    assert [s["spent_minor"] for s in past] == [0, 0]

    assert client.get("/budgets", headers=other).json() == []
    assert client.delete(f"/budgets/{created['id']}", headers=other).status_code == 404
    assert client.delete(f"/budgets/{created['id']}", headers=me).status_code == 204
    assert [b["category"] for b in client.get("/budgets", headers=me).json()] == [None]
