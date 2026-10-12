"""Cross-track checks: house budget alerts, habit categories, Calendar scope."""

from __future__ import annotations

from app.services import budgets, houses
from app.services.expenses import ExpenseInput


def test_house_bill_warns_on_payers_share_only(db):
    payer = "hb-payer"
    house = houses.create_house(db, payer, "Budget flat")
    houses.add_member(db, payer, house.id, "hb-flatmate-1")
    houses.add_member(db, payer, house.id, "hb-flatmate-2")
    budgets.set_budget(db, payer, category="utilities", limit="500")

    # 900 split three ways: my share is 300 (60% of 500), below the 80% alert.
    _expense, warnings = houses.add_split_expense(
        db, payer, house.id, ExpenseInput("Enerjisa", "900", category="utilities"), split_type="equal"
    )
    assert warnings == []

    # Another 300 share takes me to 600 of 500: now the budget is exceeded.
    _expense, warnings = houses.add_split_expense(
        db, payer, house.id, ExpenseInput("Enerjisa", "900", category="utilities"), split_type="equal"
    )
    assert warnings == ["Utilities budget exceeded this month: 600.00 of 500.00 TRY (120%, 100.00 TRY over)."]


def test_monthly_groceries_are_not_subscriptions(db):
    import datetime as dt

    from app.services import subscriptions
    from app.services.expenses import add_expense

    user = "sub-habits"
    today = dt.date(2026, 10, 20)
    for months_back in range(4):
        day = subscriptions.add_months(dt.date(2026, 10, 5), -months_back)
        add_expense(db, user, ExpenseInput("Migros", "850.00", expense_date=day, category="groceries"))
        add_expense(db, user, ExpenseInput("ISTANBULKART", "500.00", expense_date=day, category="transport"))
        add_expense(
            db, user, ExpenseInput("NETFLIX.COM", "229.99", expense_date=day, category="subscriptions")
        )

    found = subscriptions.detect_subscriptions(db, user, today=today)
    assert [s.merchant_key for s in found] == ["netflix"]


def test_gmail_only_grant_skips_calendar(monkeypatch, db):
    from google.oauth2.credentials import Credentials

    from app.integrations import google_oauth
    from app.services import reminders

    gmail_only = Credentials(token="t", scopes=[google_oauth.GMAIL_SCOPE])
    monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: gmail_only)
    assert reminders.calendar_credentials(db, "cal-user") is None

    both = Credentials(token="t", scopes=[google_oauth.GMAIL_SCOPE, google_oauth.CALENDAR_SCOPE])
    monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: both)
    assert reminders.calendar_credentials(db, "cal-user") is both


def test_my_spending_matches_dashboard_and_blocks_double_counting(db):
    import pytest

    from app.services import dashboard, reports
    from app.services.expenses import add_expense

    me = "rep-spend"
    house = houses.create_house(db, me, "Spend flat")
    houses.add_member(db, me, house.id, "rep-flatmate")
    add_expense(db, me, ExpenseInput("Migros", "100.00", category="groceries"))
    houses.add_split_expense(
        db, me, house.id, ExpenseInput("Rent", "1000.00", category="rent"), split_type="equal"
    )

    summary = dashboard.dashboard_summary(db, me)
    month = summary.month.strftime("%Y-%m")
    result = reports.run_report_query(
        db, me, f"SELECT SUM(amount_minor) AS total_minor FROM my_spending WHERE expense_month = '{month}'"
    )
    assert result["rows"] == [{"total": "600.00"}]  # 100 personal + 500 share, not + the 1000 bill
    assert summary.total_minor == 60000

    with pytest.raises(reports.DoubleCounting):
        reports.run_report_query(db, me, "SELECT SUM(total_minor) AS total_minor FROM my_expenses")
    # Thinking about house_id (excluding or grouping) is allowed.
    ok = reports.run_report_query(
        db, me, "SELECT SUM(total_minor) AS total_minor FROM my_expenses WHERE house_id IS NULL"
    )
    assert ok["rows"] == [{"total": "100.00"}]


def test_reply_language_detection():
    from app.agents.language import detect_language, reply_language_note

    assert detect_language("Ayşe bana 150 TL ödedi, kaydet") == "tr"
    assert detect_language("bu ay ne kadar harcadim") == "tr"
    assert detect_language("Who owes whom in the flat?") == "en"
    assert detect_language("How much did I spend on Migros this month?") == "en"
    assert detect_language("kira") == "tr"
    assert reply_language_note("Who owes whom?") == "(Kasa: reply in English.)"


def test_house_tools_fall_back_to_the_only_house(db):
    from types import SimpleNamespace

    from app.agents.tools import house_tools

    me = "tool-one-house"
    house = houses.create_house(db, me, "Only flat")
    houses.add_member(db, me, house.id, "tool-mate")
    houses.add_split_expense(
        db, me, house.id, ExpenseInput("Su", "100", category="utilities"), split_type="equal"
    )
    ctx = SimpleNamespace(user_id=me)

    # The model passed 0 instead of an id from list_my_houses.
    paid = house_tools.record_payment(0, "tool-mate", "me", "20", ctx)
    assert paid["status"] == "saved" and paid["amount"] == "20.00"
    assert house_tools.get_house_balances(0, ctx)["settle_up"] == [
        {"from": "tool-mate", "to": me, "amount": "30.00"}
    ]

    houses.create_house(db, me, "Second flat")
    ambiguous = house_tools.get_house_balances(0, ctx)
    assert ambiguous["status"] == "error" and "which house?" in ambiguous["error"]
