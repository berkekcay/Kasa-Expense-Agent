"""Demo data for presentations. Run it from backend/:

    python -m scripts.seed_demo --user demo            # seed the user "demo"
    python -m scripts.seed_demo --user demo --reset    # delete that user's data, then seed again
    python -m scripts.seed_demo --user demo --login-only   # new passwords and 2FA keys only

It writes into the database in DATABASE_URL (backend/.env or the environment) and needs no
network and no LLM. Everything goes through the same services the API uses, so FX
conversion, shares, balances, budgets, subscription detection and the statement import
behave exactly as they do in the app.

What it creates for the user (default display name "Deniz"):

- about 3 months of personal expenses from Turkish merchants in 8 categories;
- one USD expense (a Udemy course) converted with a cached exchange rate. The script stores
  demo rates (source "DEMO") for that day and the 7 days before today, so a USD expense
  added live during the demo still converts when TCMB cannot be reached;
- monthly Netflix and Spotify charges, then subscription detection on them;
- budgets: groceries, entertainment (already near its limit) and overall;
- the house "Moda evi" with two flatmates, `<user>-ali` (Ali) and `<user>-ayse` (Ayşe),
  bills with equal, percent, exact and per-item splits, and one recorded payment;
- 3 pending inbox items from a small bank statement (CSV) import.

Sign-in: when TOKEN_ENCRYPTION_KEY is set, the three demo people also get real accounts
(`<user>@kasa.demo`, `ali.<user>@kasa.demo`, `ayse.<user>@kasa.demo`) with a fresh random
password and a fresh Google Authenticator key each run. They are printed once, to this
terminal only, with a QR code for the main account; nothing is written to a file. Scan it
with Google Authenticator on the phone that runs the demo.

The script refuses to touch a user who already has data, unless `--reset` is given. Reset
deletes the user's and the two flatmates' expenses, budgets, subscriptions, inbox items and
every house they are in (with all of that house's bills, payments and reminders). Use it on
a demo or dev database only.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import secrets
import sys
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    Budget,
    Expense,
    FxRate,
    House,
    HouseMember,
    InboxItem,
    Reminder,
    Settlement,
    Subscription,
)
from app.services import budgets, clock, houses, statements, subscriptions
from app.services.expenses import ExpenseInput, ItemInput, add_expense, ensure_user
from app.services.money import format_minor

HOUSE_NAME = "Moda evi"
STATEMENT_FILE = "ekstre_demo.csv"
# Demo exchange rates (TRY per 1 unit), close to the TCMB bulletin in tests/fixtures.
DEMO_RATES = {"USD": Decimal("49.2160"), "EUR": Decimal("55.2105"), "GBP": Decimal("65.1520")}
FX_FALLBACK_DAYS = 7


@dataclass
class People:
    me: str
    ali: str
    ayse: str

    @property
    def all(self) -> list[str]:
        return [self.me, self.ali, self.ayse]


def people_for(user_id: str) -> People:
    return People(me=user_id, ali=f"{user_id}-ali", ayse=f"{user_id}-ayse")


# --- dates ----------------------------------------------------------------------------------


def month_day(today: dt.date, back: int, day: int) -> dt.date:
    """Day `day` of the month `back` months ago. In the current month it never goes past
    today, so a seed early in the month still has spending "this month"."""
    first = subscriptions.add_months(today.replace(day=1), -back)
    date = first.replace(day=min(day, 28))
    return min(date, today)


def weekday_on_or_before(day: dt.date) -> dt.date:
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


# --- guard and reset --------------------------------------------------------------------------


def existing_data(db: Session, people: People) -> dict[str, int]:
    """Rows that belong to the user or the two demo flatmates (empty dict = nothing yet)."""
    ids = people.all
    counts = {
        "expenses": db.scalar(select(func.count()).select_from(Expense).where(Expense.owner_id.in_(ids))),
        "house memberships": db.scalar(
            select(func.count()).select_from(HouseMember).where(HouseMember.user_id.in_(ids))
        ),
        "budgets": db.scalar(select(func.count()).select_from(Budget).where(Budget.user_id.in_(ids))),
        "subscriptions": db.scalar(
            select(func.count()).select_from(Subscription).where(Subscription.user_id.in_(ids))
        ),
        "inbox items": db.scalar(
            select(func.count()).select_from(InboxItem).where(InboxItem.user_id.in_(ids))
        ),
    }
    return {name: int(n) for name, n in counts.items() if n}


def outside_members(db: Session, people: People) -> list[str]:
    """Members of the demo people's houses who are not demo people. `--reset` would delete
    those houses with their bills, so it refuses while anyone else is in them."""
    ids = people.all
    house_ids = select(HouseMember.house_id).where(HouseMember.user_id.in_(ids))
    stmt = select(HouseMember.user_id).where(
        HouseMember.house_id.in_(house_ids), HouseMember.user_id.not_in(ids)
    )
    return sorted(set(db.scalars(stmt)))


def reset(db: Session, people: People) -> None:
    """Delete what `existing_data` counts, children first (SQLite enforces foreign keys)."""
    ids = people.all
    house_ids = list(db.scalars(select(HouseMember.house_id).where(HouseMember.user_id.in_(ids)).distinct()))
    for row in db.scalars(select(InboxItem).where(InboxItem.user_id.in_(ids))):
        db.delete(row)
    if house_ids:
        for model in (Reminder, Settlement):
            for row in db.scalars(select(model).where(model.house_id.in_(house_ids))):
                db.delete(row)
    expenses = select(Expense).where(Expense.owner_id.in_(ids))
    if house_ids:
        expenses = select(Expense).where(Expense.owner_id.in_(ids) | Expense.house_id.in_(house_ids))
    for row in db.scalars(expenses):
        db.delete(row)  # the ORM cascade removes items, item assignees and shares
    db.flush()
    for model in (Subscription, Budget):
        for row in db.scalars(select(model).where(model.user_id.in_(ids))):
            db.delete(row)
    if house_ids:
        for row in db.scalars(select(HouseMember).where(HouseMember.house_id.in_(house_ids))):
            db.delete(row)
        db.flush()
        for row in db.scalars(select(House).where(House.id.in_(house_ids))):
            db.delete(row)
    db.commit()


# --- seeding ----------------------------------------------------------------------------------


def seed_fx_rates(db: Session, days: list[dt.date]) -> int:
    """Store demo rates for `days` where no rate is cached yet. Real TCMB rows are kept."""
    written = 0
    for day in sorted(set(days)):
        have = set(db.scalars(select(FxRate.currency).where(FxRate.rate_date == day)))
        for code, rate in DEMO_RATES.items():
            if code not in have:
                db.add(FxRate(rate_date=day, currency=code, try_per_unit=rate, source="DEMO"))
                written += 1
    db.commit()
    return written


# (merchant, amount in TL, day of month, category) per month, `back` months ago.
PERSONAL: dict[int, list[tuple[str, str, int, str]]] = {
    2: [
        ("Migros", "812.40", 3, "groceries"),
        ("BİM", "296.75", 12, "groceries"),
        ("A101", "158.90", 22, "groceries"),
        ("Kahve Dünyası", "92.00", 5, "food"),
        ("Yemeksepeti", "268.50", 16, "food"),
        ("İstanbulkart", "400.00", 2, "transport"),
        ("LC Waikiki", "749.99", 19, "shopping"),
        ("Cinemaximum", "320.00", 25, "entertainment"),
    ],
    1: [
        ("Migros", "865.20", 4, "groceries"),
        ("Şok Market", "214.35", 13, "groceries"),
        ("Simit Sarayı", "65.00", 8, "food"),
        ("Yemeksepeti", "312.90", 20, "food"),
        ("İstanbulkart", "400.00", 1, "transport"),
        ("BiTaksi", "185.00", 23, "transport"),
        ("Trendyol", "1299.90", 17, "shopping"),
        ("Eczane Şifa", "164.30", 11, "health"),
        ("Biletix konser", "550.00", 26, "entertainment"),
    ],
    0: [
        ("Migros", "842.50", 3, "groceries"),
        ("BİM", "312.75", 12, "groceries"),
        ("A101", "186.40", 21, "groceries"),
        ("Kahve Dünyası", "95.00", 5, "food"),
        ("Yemeksepeti", "240.50", 15, "food"),
        ("İstanbulkart", "400.00", 2, "transport"),
        ("D&R kitap", "420.00", 6, "education"),
        ("Cinemaximum", "360.00", 9, "entertainment"),
        ("Biletix tiyatro", "650.00", 14, "entertainment"),
    ],
}

# Monthly subscriptions: (merchant, amount, days before today of the latest charge).
SUBSCRIPTIONS = [("Netflix", "229.99", 3), ("Spotify", "99.99", 12)]


def seed_personal(db: Session, user_id: str, today: dt.date) -> tuple[int, Expense]:
    count = 0
    for back, rows in PERSONAL.items():
        for merchant, amount, day, category in rows:
            data = ExpenseInput(merchant, amount, month_day(today, back, day), "TRY", category)
            add_expense(db, user_id, data)
            count += 1
    for merchant, amount, days_ago in SUBSCRIPTIONS:
        latest = today - dt.timedelta(days=days_ago)
        for months_back in range(3):
            day = subscriptions.add_months(latest, -months_back)
            add_expense(db, user_id, ExpenseInput(merchant, amount, day, "TRY", "subscriptions"))
            count += 1
    usd_day = weekday_on_or_before(today - dt.timedelta(days=20))
    usd = add_expense(
        db,
        user_id,
        ExpenseInput("Udemy", "14.99", usd_day, "USD", "education", note="Python kursu"),
    ).expense
    return count + 1, usd


def seed_house(db: Session, p: People, today: dt.date) -> House:
    house = houses.create_house(db, p.me, HOUSE_NAME, "TRY")
    houses.add_member(db, p.me, house.id, p.ali, "Ali")
    houses.add_member(db, p.me, house.id, p.ayse, "Ayşe")

    def bill(merchant: str, total: str, back: int, day: int, category: str, **split) -> None:
        data = ExpenseInput(merchant, total, month_day(today, back, day), "TRY", category)
        lines = split.pop("lines", None)  # per-item split: (description, amount, who shares it)
        if lines:
            data.items = [ItemInput(desc, amount) for desc, amount, _ in lines]
            split["item_assignees"] = [who for _, _, who in lines]
        houses.add_split_expense(db, p.me, house.id, data, **split)

    # Last month
    bill("Kira", "18000.00", 1, 1, "rent", split_type="equal", paid_by=p.me)
    bill("Doğalgaz faturası", "1200.00", 1, 18, "utilities", split_type="equal", paid_by=p.ayse)
    # This month
    bill("Kira", "18000.00", 0, 1, "rent", split_type="equal", paid_by=p.me)
    bill(
        "Elektrik faturası",
        "900.00",
        0,
        8,
        "utilities",
        split_type="percent",
        paid_by=p.ali,
        percents={p.me: "40", p.ali: "30", p.ayse: "30"},
    )
    bill(
        "İnternet faturası",
        "450.00",
        0,
        10,
        "utilities",
        split_type="exact",
        paid_by=p.ayse,
        exact_amounts={p.me: "200.00", p.ali: "125.00", p.ayse: "125.00"},
    )
    lines = [("Deterjan", "250.00", []), ("Kahve", "240.00", [p.me, p.ayse]), ("Peynir", "150.00", [p.ali])]
    bill(
        "Migros ev alışverişi",
        "640.00",
        0,
        11,
        "groceries",
        split_type="items",
        paid_by=p.me,
        lines=lines,
    )
    houses.record_settlement(
        db,
        p.me,
        house.id,
        from_user=p.ali,
        to_user=p.me,
        amount="6000.00",
        note="Geçen ayın kira payı, havale",
    )
    return house


def seed_budgets(db: Session, user_id: str) -> None:
    budgets.set_budget(db, user_id, category="groceries", limit="4000.00")
    budgets.set_budget(db, user_id, category="entertainment", limit="1200.00")  # about 84% used
    budgets.set_budget(db, user_id, category=None, limit="15000.00")


def statement_csv(today: dt.date) -> bytes:
    rows = [
        (today - dt.timedelta(days=1), "MIGROS MODA ISTANBUL TR", "-318,45"),
        (today - dt.timedelta(days=2), "UBER *TRIP HELP.UBER.COM", "-142,80"),
        (today - dt.timedelta(days=4), "STARBUCKS KADIKOY", "-135,00"),
    ]
    lines = ["Tarih;Açıklama;Tutar"] + [f"{d:%d.%m.%Y};{text};{amount}" for d, text, amount in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def seed(db: Session, user_id: str, *, name: str = "Deniz", today: dt.date | None = None) -> dict:
    """Create the whole demo dataset; returns what was made (see the module docstring)."""
    today = today or clock.today()
    p = people_for(user_id)
    ensure_user(db, p.me, name)
    db.commit()

    usd_day = weekday_on_or_before(today - dt.timedelta(days=20))
    fallback = [today - dt.timedelta(days=k) for k in range(1, FX_FALLBACK_DAYS + 1)]
    rates = seed_fx_rates(db, [usd_day] + [d for d in fallback if d.weekday() < 5])

    expense_count, usd = seed_personal(db, p.me, today)
    house = seed_house(db, p, today)
    seed_budgets(db, p.me)
    subs = subscriptions.detect_subscriptions(db, p.me, today=today)
    result = asyncio.run(
        statements.import_statement(
            db, p.me, filename=STATEMENT_FILE, content_type="text/csv", data=statement_csv(today)
        )
    )
    balances = houses.house_balances(db, p.me, house.id)
    return {
        "user_id": p.me,
        "flatmates": [p.ali, p.ayse],
        "house_id": house.id,
        "personal_expenses": expense_count,
        "house_expenses": len(houses.list_house_expenses(db, p.me, house.id)),
        "payments": len(houses.list_settlements(db, p.me, house.id)),
        "budgets": len(budgets.list_budgets(db, p.me)),
        "subscriptions": sorted(s.display_name for s in subs),
        "inbox_items": result.created,
        "fx_rates_written": rates,
        "usd_expense_id": usd.id,
        "balances": balances.balances,
        "transfers": [(t.from_user, t.to_user, t.amount_minor) for t in balances.transfers],
    }


# --- sign-in for the demo people -------------------------------------------------------------


@dataclass
class DemoLogin:
    user_id: str
    email: str
    password: str
    totp_secret: str


def make_login(db: Session, user_id: str, email: str) -> DemoLogin:
    """Give an existing demo user a real account: email, random password, 2FA already on."""
    from app.db.models import User
    from app.services import accounts, crypto, security

    user = db.get(User, user_id)
    taken = accounts.find_by_email(db, email)
    if taken is not None and taken.id != user_id:
        raise SystemExit(f"{email} already belongs to another account ({taken.id}); use another --user")
    password = "kasa-" + secrets.token_urlsafe(9)
    secret = security.new_totp_secret()
    user.login_email = email
    user.email = user.email or email
    user.password_hash = security.hash_password(password)
    user.totp_secret_enc = crypto.encrypt(secret)
    user.totp_enabled_at = accounts._now()
    user.totp_last_step = None
    user.failed_logins = 0
    user.locked_until = None
    accounts.replace_recovery_codes(db, user_id)
    db.commit()
    return DemoLogin(user_id, email, password, secret)


def make_logins(db: Session, p: People) -> list[DemoLogin]:
    return [
        make_login(db, p.me, f"{p.me}@kasa.demo"),
        make_login(db, p.ali, f"ali.{p.me}@kasa.demo"),
        make_login(db, p.ayse, f"ayse.{p.me}@kasa.demo"),
    ]


def print_logins(logins: list[DemoLogin]) -> None:
    from app.services import security

    print("Sign-in (shown once; run again with --login-only for new ones):")
    for login in logins:
        print(f"  {login.user_id}: {login.email}  password {login.password}  2FA key {login.totp_secret}")
    main_login = logins[0]
    uri = security.otpauth_uri(main_login.totp_secret, main_login.email)
    print(f"Scan this with Google Authenticator for {main_login.email}:")
    try:
        import segno

        segno.make(uri, error="m").terminal(compact=True)
    except (ImportError, UnicodeEncodeError):
        print(f"  {uri}")


# --- command line -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    from app.db.session import init_db, session_for

    parser = argparse.ArgumentParser(prog="python -m scripts.seed_demo", description=__doc__.split("\n")[0])
    parser.add_argument("--user", default="demo", help="dev user id to seed (default: demo)")
    parser.add_argument("--name", default="Deniz", help="display name for that user (default: Deniz)")
    parser.add_argument("--reset", action="store_true", help="delete the user's demo data first")
    parser.add_argument("--today", type=dt.date.fromisoformat, help="pretend today is YYYY-MM-DD")
    parser.add_argument(
        "--login-only", action="store_true", help="only make new passwords and 2FA keys for the demo people"
    )
    args = parser.parse_args(argv)

    user_id = args.user.strip()
    if not user_id:
        parser.error("--user must not be empty")
    target = make_url(get_settings().database_url).render_as_string(hide_password=True)
    print(f"Database: {target}")
    init_db()
    can_login = bool(get_settings().token_encryption_key)
    if args.login_only:
        if not can_login:
            print(
                "TOKEN_ENCRYPTION_KEY is not set; generate one with python -m app.services.crypto",
                file=sys.stderr,
            )
            return 1
        with session_for(user_id, system=True) as db:
            people = people_for(user_id)
            for uid, name in ((people.me, args.name), (people.ali, "Ali"), (people.ayse, "Ayşe")):
                ensure_user(db, uid, name)
            db.commit()
            print_logins(make_logins(db, people))
        return 0
    with session_for(user_id) as db:
        people = people_for(user_id)
        found = existing_data(db, people)
        if found and not args.reset:
            what = ", ".join(f"{n} {name}" for name, n in found.items())
            print(f"User {user_id!r} already has data ({what}). Nothing was changed.", file=sys.stderr)
            print("Run again with --reset to delete it and seed from scratch.", file=sys.stderr)
            return 1
        if found:
            others = outside_members(db, people)
            if others:
                print(
                    f"A house of {user_id!r} also has {', '.join(others)}, so --reset would delete "
                    "their bills too. Nothing was changed. Use another --user.",
                    file=sys.stderr,
                )
                return 1
            reset(db, people)
            print(f"Deleted the old demo data of {user_id!r}.")
        summary = seed(db, user_id, name=args.name, today=args.today)
    logins = []
    if can_login:
        with session_for(user_id, system=True) as db:
            logins = make_logins(db, people)

    print(f"Seeded demo data for {user_id!r} ({args.name}):")
    print(f"  personal expenses: {summary['personal_expenses']} (one in USD)")
    print(f"  house {HOUSE_NAME!r} (id {summary['house_id']}) with {', '.join(summary['flatmates'])}")
    print(f"  house bills: {summary['house_expenses']}, recorded payments: {summary['payments']}")
    print(f"  budgets: {summary['budgets']}, subscriptions: {', '.join(summary['subscriptions'])}")
    print(f"  pending inbox items: {summary['inbox_items']}")
    for from_user, to_user, minor in summary["transfers"]:
        print(f"  settle up: {from_user} pays {to_user} {format_minor(minor)} TRY")
    if logins:
        print_logins(logins)
        print("Open the web app and sign in with the email, password and the code from the app.")
    else:
        print("No sign-in made: TOKEN_ENCRYPTION_KEY is not set (python -m app.services.crypto).")
    print(f"In dev mode you can also type {user_id} in the Dev user box and press Switch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
