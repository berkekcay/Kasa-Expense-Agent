"""Deterministic demo data for the eval cases (owner: track REPORT).

`seed_demo_data(user_id, today=...)` writes, for one fresh user:

- personal expenses over six months (this month and the five before) in groceries, food,
  transport, subscriptions, entertainment and shopping, one with receipt lines and one
  converted from USD;
- a house ("Moda evi") with two flatmates, `<user_id>-ali` (Ali) and `<user_id>-ayse`
  (Ayşe), and equal-split bills from all three this month and last month;
- a personal expense of Ali's that the user must never see ("Ali Gizli Kitapçı");
- budgets (groceries 3000 TL, overall 15000 TL) and a Netflix subscription linked to six
  monthly charges.

Rows are written with the ORM directly (no services, no FX lookups, no budget hooks), so
the data does not depend on other tracks. Expected answers are computed from these rows
with plain SQL in cases.jsonl, never hard-coded here.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import Budget, Expense, ExpenseItem, ExpenseShare, House, HouseMember, Subscription, User

SECRET_MERCHANT = "Ali Gizli Kitapçı"
FLATMATE_EMAIL_DOMAIN = "kasa-eval.example"


def _month(today: dt.date, back: int) -> tuple[int, int]:
    index = today.year * 12 + today.month - 1 - back
    return index // 12, index % 12 + 1


def _day(today: dt.date, back: int, day: int) -> dt.date:
    """Day `day` of the month `back` months ago; this month never goes past today."""
    year, month = _month(today, back)
    if back == 0:
        day = min(day, today.day)
    return dt.date(year, month, min(day, 28))


def _expense(owner: str, merchant: str, total_minor: int, date: dt.date, category: str, **extra) -> Expense:
    return Expense(
        owner_id=owner,
        merchant=merchant,
        expense_date=date,
        currency="TRY",
        total_minor=total_minor,
        category=category,
        source=extra.pop("source", "manual"),
        **extra,
    )


def _house_bill(
    house: House,
    payer: str,
    members: list[str],
    merchant: str,
    total_minor: int,
    date: dt.date,
    category: str,
) -> Expense:
    share, rest = divmod(total_minor, len(members))
    assert rest == 0, "seeded house bills split evenly"
    expense = _expense(payer, merchant, total_minor, date, category, split_type="equal")
    expense.house_id = house.id
    expense.shares = [ExpenseShare(user_id=m, amount_minor=share) for m in members]
    return expense


def seed_demo_data(user_id: str, *, today: dt.date | None = None, db: Session | None = None) -> dict:
    """Create the demo dataset for `user_id` (see the module docstring). Returns the ids
    the cases may need: house_id, flatmate user ids."""
    from app.db.session import init_db, session_for
    from app.services import clock

    today = today or clock.today()
    if db is None:
        init_db()
        with session_for(user_id) as session:
            return seed_demo_data(user_id, today=today, db=session)

    ali, ayse = f"{user_id}-ali", f"{user_id}-ayse"
    db.add_all(
        [
            User(id=user_id, display_name="Deniz"),
            User(id=ali, display_name="Ali", email=f"ali@{FLATMATE_EMAIL_DOMAIN}"),
            User(id=ayse, display_name="Ayşe", email=f"ayse@{FLATMATE_EMAIL_DOMAIN}"),
        ]
    )
    db.flush()

    netflix = Subscription(
        user_id=user_id,
        merchant_key="netflix",
        display_name="Netflix",
        amount_minor=22999,
        currency="TRY",
        period="monthly",
        last_charge_date=_day(today, 0, 7),
        next_expected_date=_day(today, -1, 7),
        status="active",
    )
    db.add(netflix)
    db.add_all(
        [
            Budget(user_id=user_id, category="groceries", limit_minor=300000, alert_threshold_pct=80),
            Budget(user_id=user_id, category=None, limit_minor=1500000, alert_threshold_pct=80),
        ]
    )
    db.flush()

    rows: list[Expense] = []
    for back in range(6):
        rows += [
            _expense(user_id, "Migros", 85040 + 2500 * back, _day(today, back, 3), "groceries"),
            _expense(user_id, "BİM", 31275, _day(today, back, 12), "groceries"),
            _expense(user_id, "Kahve Dünyası", 9500, _day(today, back, 5), "food"),
            _expense(user_id, "İstanbulkart", 40000, _day(today, back, 2), "transport"),
            _expense(
                user_id, "Netflix", 22999, _day(today, back, 7), "subscriptions", subscription_id=netflix.id
            ),
        ]
        if back % 2 == 0:
            rows.append(_expense(user_id, "Yemeksepeti", 24050, _day(today, back, 15), "food"))
    rows[0].items = [
        ExpenseItem(description="Süt", quantity=Decimal(2), amount_minor=7990),
        ExpenseItem(description="Peynir", quantity=Decimal(1), amount_minor=32050),
        ExpenseItem(description="Deterjan", quantity=Decimal(1), amount_minor=45000),
    ]
    rows += [
        _expense(user_id, "Cinemaximum", 36000, _day(today, 0, 9), "entertainment"),
        _expense(user_id, "Konser", 75000, _day(today, 2, 20), "entertainment"),
        _expense(user_id, "Trendyol", 129990, _day(today, 1, 18), "shopping", source="email"),
        _expense(
            user_id,
            "Amazon",
            164967,
            _day(today, 3, 10),
            "shopping",
            original_currency="USD",
            original_total_minor=4999,
            fx_rate=Decimal("33.000000"),
            fx_date=_day(today, 3, 10),
        ),
        _expense(ali, SECRET_MERCHANT, 77777, _day(today, 0, 4), "education"),
    ]
    db.add_all(rows)

    house = House(name="Moda evi", currency="TRY", created_by=user_id)
    house.members = [HouseMember(user_id=u) for u in (user_id, ali, ayse)]
    db.add(house)
    db.flush()
    members = [user_id, ali, ayse]
    db.add_all(
        [
            _house_bill(house, user_id, members, "Kira", 1500000, _day(today, 0, 1), "rent"),
            _house_bill(house, ali, members, "Elektrik faturası", 90000, _day(today, 0, 8), "utilities"),
            _house_bill(
                house, user_id, members, "Ev market alışverişi", 60000, _day(today, 0, 10), "groceries"
            ),
            _house_bill(house, ayse, members, "İnternet faturası", 45000, _day(today, 0, 11), "utilities"),
            _house_bill(house, user_id, members, "Kira", 1500000, _day(today, 1, 1), "rent"),
            _house_bill(house, ayse, members, "Doğalgaz faturası", 120000, _day(today, 1, 16), "utilities"),
        ]
    )
    db.commit()
    return {"house_id": house.id, "flatmates": [ali, ayse]}
