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
