"""GET /expenses/export.csv: filters, exact money, Turkish text, formula escaping, isolation."""

import csv
import datetime as dt
import io
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import FxRate
from app.integrations import tcmb
from app.services import expenses as expense_service

COLUMNS = [
    "id",
    "date",
    "merchant",
    "category",
    "source",
    "amount",
    "amount_minor",
    "currency",
    "original_amount",
    "original_currency",
    "fx_rate",
    "house_id",
    "my_share",
    "note",
]


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


@pytest.fixture
def user() -> str:
    return f"csv-{uuid.uuid4().hex[:8]}"


def add(client, user: str, merchant: str, total: str, date: str, **extra) -> dict:
    r = client.post(
        "/expenses",
        json={"merchant": merchant, "total": total, "expense_date": date, **extra},
        headers=as_user(user),
    )
    assert r.status_code == 201, r.text
    return r.json()


def export(client, user: str, query: str = "", status: int = 200):
    r = client.get(f"/expenses/export.csv{query}", headers=as_user(user))
    assert r.status_code == status, r.text
    return r


def rows(client, user: str, query: str = "") -> list[dict[str, str]]:
    r = export(client, user, query)
    assert r.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    reader = csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
    assert reader.fieldnames == COLUMNS
    return list(reader)


def house_bill(client, payer: str, other: str, total: str = "90", date: str = "2026-10-05") -> dict:
    house_id = client.post("/houses", json={"name": "Kadıköy evi"}, headers=as_user(payer)).json()["id"]
    r = client.post(f"/houses/{house_id}/members", json={"user_id": other}, headers=as_user(payer))
    assert r.status_code == 201, r.text
    r = client.post(
        f"/houses/{house_id}/expenses",
        json={"merchant": "Elektrik", "total": total, "expense_date": date, "category": "utilities"},
        headers=as_user(payer),
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_headers_columns_and_exact_amounts(client, user):
    e = add(client, user, "Migros", "1234.5", "2026-10-03", category="groceries", note="haftalık")
    r = export(client, user)
    assert r.headers["content-type"] == "text/csv; charset=utf-8"
    assert r.headers["content-disposition"] == 'attachment; filename="kasa-expenses.csv"'
    assert export(client, user, "?month=2026-10").headers["content-disposition"] == (
        'attachment; filename="kasa-expenses-2026-10.csv"'
    )
    assert rows(client, user) == [
        {
            "id": str(e["id"]),
            "date": "2026-10-03",
            "merchant": "Migros",
            "category": "groceries",
            "source": "manual",
            "amount": "1234.50",
            "amount_minor": "123450",
            "currency": "TRY",
            "original_amount": "",
            "original_currency": "",
            "fx_rate": "",
            "house_id": "",
            "my_share": "",
            "note": "haftalık",
        }
    ]


def test_small_amounts_keep_two_decimals(client, user):
    add(client, user, "Simit", "0.05", "2026-10-01")
    add(client, user, "Çay", "7", "2026-10-02")
    assert [(r["amount"], r["amount_minor"]) for r in rows(client, user)] == [("7.00", "700"), ("0.05", "5")]


def test_turkish_text_round_trips(client, user):
    add(client, user, "Şok Market", "12", "2026-10-01", note="İçecek, ılık su ve çiğköfte")
    add(client, user, "Öğrenci İşleri", "300", "2026-10-02", category="eğitim")
    raw = export(client, user).content.decode("utf-8")
    assert "Şok Market" in raw and "Öğrenci İşleri" in raw
    by_merchant = {r["merchant"]: r for r in rows(client, user)}
    assert by_merchant["Şok Market"]["note"] == "İçecek, ılık su ve çiğköfte"  # comma is quoted
    assert by_merchant["Öğrenci İşleri"]["category"] == "education"


def test_empty_export_is_just_the_header(client, user):
    assert rows(client, user) == []


@pytest.mark.parametrize(
    "merchant",
    ['=HYPERLINK("http://evil.example","tıkla")', "+90 555", "-2+3", "@SUM(A1:A9)", "\t=1+1", "\r=1"],
)
def test_formula_like_text_is_escaped(client, user, merchant):
    add(client, user, merchant, "10", "2026-10-01", note=merchant)
    [row] = rows(client, user)
    assert row["merchant"] == f"'{merchant.strip()}"  # merchants are stripped when saved
    assert row["note"] == f"'{merchant}"
    assert row["amount"] == "10.00"  # numbers are never prefixed


def test_plain_text_is_not_escaped():
    assert expense_service._csv_text("Migros = ucuz") == "Migros = ucuz"
    assert expense_service._csv_text("a-101") == "a-101"
    assert expense_service._csv_text(None) == ""


def test_filters_match_the_expense_list(client, user):
    add(client, user, "Migros", "100", "2026-10-03", category="groceries")
    add(client, user, "BIM", "50", "2026-10-12", category="groceries")
    add(client, user, "Metro", "20", "2026-09-30", category="transport")
    add(client, user, "Kitap", "70", "2026-09-02")  # no category
    house_bill(client, user, f"{user}-flatmate")

    def merchants(query: str = "") -> list[str]:
        return [r["merchant"] for r in rows(client, user, query)]

    assert merchants() == ["BIM", "Elektrik", "Migros", "Metro", "Kitap"]
    assert merchants("?month=2026-10") == ["BIM", "Elektrik", "Migros"]
    assert merchants("?category=groceries") == ["BIM", "Migros"]
    assert merchants("?category=none") == ["Kitap"]
    assert merchants("?source=manual&scope=personal") == ["BIM", "Migros", "Metro", "Kitap"]
    assert merchants("?scope=house") == ["Elektrik"]
    assert merchants("?month=2026-09&category=transport") == ["Metro"]
    # Same rows, same order as GET /expenses.
    listed = client.get("/expenses?month=2026-10", headers=as_user(user)).json()
    assert [r["id"] for r in rows(client, user, "?month=2026-10")] == [str(e["id"]) for e in listed]


@pytest.mark.parametrize(
    "query", ["?month=2026-13", "?month=oct", "?category=pizza", "?source=fax", "?scope=everyone"]
)
def test_invalid_filters_answer_422(client, user, query):
    export(client, user, query, status=422)


def test_users_only_export_their_own_expenses(client, user):
    other = f"{user}-other"
    add(client, user, "Benim", "10", "2026-10-01")
    add(client, other, "Onun", "20", "2026-10-01")
    assert [r["merchant"] for r in rows(client, user)] == ["Benim"]
    assert [r["merchant"] for r in rows(client, other)] == ["Onun"]
    assert rows(client, f"{user}-nobody") == []


def test_house_bill_is_exported_by_its_payer_only_with_their_share(client, user):
    flatmate = f"{user}-flatmate"
    bill = house_bill(client, user, flatmate, total="90.01")
    [row] = rows(client, user)
    assert row["id"] == str(bill["id"]) and row["house_id"] == str(bill["house_id"])
    assert row["amount"] == "90.01"
    shares = {s["user_id"]: s["amount"] for s in bill["shares"]}
    assert row["my_share"] == shares[user]
    assert Decimal(shares[user]) + Decimal(shares[flatmate]) == Decimal("90.01")
    # The flatmate sees the bill on the House page, but it is not one of their own expenses.
    assert rows(client, flatmate) == []
    assert rows(client, flatmate, "?scope=house") == []


def test_converted_expense_keeps_original_amount_and_rate(client, user, db, monkeypatch):
    day = dt.date(2023, 3, 7)
    if db.scalars(select(FxRate).where(FxRate.rate_date == day, FxRate.currency == "USD")).first() is None:
        db.add(FxRate(rate_date=day, currency="USD", try_per_unit=Decimal("18.9734"), source="TCMB"))
        db.commit()

    def offline(*_args, **_kwargs):
        raise AssertionError("the cached rate should be used")

    monkeypatch.setattr(tcmb, "_http_get", offline)
    e = add(client, user, "Steam", "10.00", day.isoformat(), currency="USD")
    [row] = rows(client, user)
    assert row["currency"] == "TRY" and row["original_currency"] == "USD"
    assert row["original_amount"] == "10.00"
    assert row["amount"] == e["total"] and row["amount_minor"] == str(e["total_minor"])
    assert row["fx_rate"] == e["fx_rate"]
    assert Decimal(row["fx_rate"]) == Decimal("18.9734")


def test_too_many_rows_answers_422(client, user, monkeypatch):
    monkeypatch.setattr(expense_service, "MAX_EXPORT_ROWS", 2)
    for day in ("2026-09-30", "2026-10-01", "2026-10-02"):
        add(client, user, "Kahve", "5", day)
    assert "narrow the filters" in export(client, user, status=422).json()["detail"]
    assert len(rows(client, user, "?month=2026-10")) == 2  # a narrower filter still exports
