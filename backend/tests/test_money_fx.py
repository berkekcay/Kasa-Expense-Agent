"""Track MONEY: TCMB parsing, the rate cache, exact conversion and the FX pipeline hook.

No real network: `tcmb._http_get` is replaced by a fake TCMB that serves saved or
synthetic bulletins and fails the test on any unexpected URL. Each test uses its own
dates because the test database (and its fx_rates) is shared by the whole session.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.db.models import Expense, ExpenseItem, FxRate
from app.integrations import tcmb
from app.services import clock, fx
from app.services.errors import InvalidInput, UpstreamError
from app.services.expenses import ExpenseInput, ItemInput, add_expense, build_expense

FIXTURE = Path(__file__).parent / "fixtures" / "tcmb_20261009.xml"


def bulletin(day: dt.date, rates: dict[str, str], unit: dict[str, int] | None = None) -> bytes:
    """A minimal TCMB bulletin in the real format."""
    nodes = []
    for code, selling in rates.items():
        nodes.append(
            f'<Currency CrossOrder="0" Kod="{code}" CurrencyCode="{code}">'
            f"<Unit>{(unit or {}).get(code, 1)}</Unit><Isim>X</Isim><CurrencyName>X</CurrencyName>"
            f"<ForexBuying>{selling}</ForexBuying><ForexSelling>{selling}</ForexSelling>"
            f"<BanknoteBuying/><BanknoteSelling/><CrossRateUSD/><CrossRateOther/></Currency>"
        )
    head = f'<Tarih_Date Tarih="{day:%d.%m.%Y}" Date="{day:%m/%d/%Y}" Bulten_No="2026/1">'
    return f'<?xml version="1.0" encoding="UTF-8"?>{head}{"".join(nodes)}</Tarih_Date>'.encode()


class FakeTcmb:
    def __init__(self) -> None:
        self.pages: dict[str, tuple[int, bytes]] = {}
        self.calls: list[str] = []
        self.down = False

    def serve(self, day: dt.date, body: bytes, status: int = 200) -> None:
        self.pages[tcmb.day_url(get_settings().tcmb_base_url, day)] = (status, body)

    def missing(self, day: dt.date) -> None:
        self.serve(day, b"<html>not found</html>", 404)

    def get(self, url: str, timeout: float) -> httpx.Response:
        self.calls.append(url)
        if self.down:
            raise httpx.ConnectError("offline")
        if url not in self.pages:
            raise AssertionError(f"unexpected TCMB request {url}")
        status, body = self.pages[url]
        return httpx.Response(status, content=body)


@pytest.fixture
def fake_tcmb(monkeypatch):
    fake = FakeTcmb()
    monkeypatch.setattr(tcmb, "_http_get", fake.get)
    fx._no_bulletin.clear()
    yield fake
    fx._no_bulletin.clear()


@pytest.fixture
def frozen_today(monkeypatch):
    def freeze(day: dt.date) -> None:
        monkeypatch.setattr(clock, "today", lambda: day)

    return freeze


# --- parser -------------------------------------------------------------------------------


def test_parses_the_real_bulletin_format():
    day, rates = tcmb.parse_rates_xml(FIXTURE.read_bytes())
    assert day == dt.date(2026, 10, 9)
    assert rates["USD"] == Decimal("49.216000")
    assert rates["EUR"] == Decimal("55.210500")
    assert rates["AUD"] == Decimal("34.429300")
    assert rates["JPY"] == Decimal("0.311727")  # ForexSelling 31.1727 per Unit 100
    assert rates["RON"] == Decimal("10.391900")  # no banknote prices, forex is enough
    # XDR has neither selling price: USD rate * CrossRateOther (USD per 1 XDR).
    assert rates["XDR"] == (Decimal("49.2160") * Decimal("1.35371")).quantize(Decimal("0.000001"))
    assert "TRY" not in rates


def test_parser_fallbacks_and_quirks():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Date="03/14/2025">
  <Currency Kod="USD" CurrencyCode="USD"><Unit>1</Unit><ForexSelling>40.0000</ForexSelling></Currency>
  <Currency Kod="BNK" CurrencyCode="BNK"><Unit>10</Unit><ForexSelling/>
    <BanknoteSelling>12,5</BanknoteSelling></Currency>
  <Currency Kod="CRU" CurrencyCode="CRU"><Unit>1</Unit><ForexSelling></ForexSelling>
    <CrossRateUSD>8</CrossRateUSD><CrossRateOther/></Currency>
  <Currency Kod="NON" CurrencyCode="NON"><Unit>1</Unit><ForexSelling>abc</ForexSelling></Currency>
  <Currency Kod="ZER" CurrencyCode="ZER"><Unit>1</Unit><ForexSelling>0</ForexSelling></Currency>
</Tarih_Date>"""
    day, rates = tcmb.parse_rates_xml(xml)
    assert day == dt.date(2025, 3, 14)  # from Date (MM/DD/YYYY) when Tarih is missing
    assert rates == {
        "USD": Decimal("40.000000"),
        "BNK": Decimal("1.250000"),  # BanknoteSelling 12,5 / Unit 10
        "CRU": Decimal("5.000000"),  # 40 TRY per USD / 8 CRU per USD
    }


@pytest.mark.parametrize("body", [b"not xml", b"<html><body>hata</body></html>", b"<Tarih_Date/>"])
def test_parser_rejects_other_documents(body):
    with pytest.raises(tcmb.TcmbParseError):
        tcmb.parse_rates_xml(body)


def test_fetch_rates_urls_and_errors(fake_tcmb):
    day = dt.date(2025, 2, 3)
    assert tcmb.day_url("https://x/kurlar/", day) == "https://x/kurlar/202502/03022025.xml"
    fake_tcmb.serve(day, bulletin(day, {"USD": "36.1"}))
    assert tcmb.fetch_rates(day) == (day, {"USD": Decimal("36.100000")})
    fake_tcmb.missing(day + dt.timedelta(days=1))
    assert tcmb.fetch_rates(day + dt.timedelta(days=1)) is None
    fake_tcmb.serve(day + dt.timedelta(days=2), b"oops", 500)
    with pytest.raises(UpstreamError):
        tcmb.fetch_rates(day + dt.timedelta(days=2))
    fake_tcmb.serve(day + dt.timedelta(days=3), b"<html>hata</html>")  # HTML with 200
    assert tcmb.fetch_rates(day + dt.timedelta(days=3)) is None
    fake_tcmb.down = True
    with pytest.raises(UpstreamError):
        tcmb.fetch_rates(day)


# --- rate lookup and cache ----------------------------------------------------------------


def test_weekend_uses_friday_without_asking_tcmb_for_the_weekend(db, fake_tcmb, frozen_today):
    friday, sunday = dt.date(2025, 3, 7), dt.date(2025, 3, 9)
    assert friday.weekday() == 4 and sunday.weekday() == 6
    frozen_today(dt.date(2025, 3, 20))
    fake_tcmb.serve(friday, bulletin(friday, {"USD": "36.5", "EUR": "39.25"}))

    rate = fx.get_rate(db, "usd", sunday)
    assert rate == fx.Rate("USD", friday, Decimal("36.500000"))
    assert fake_tcmb.calls == [tcmb.day_url(get_settings().tcmb_base_url, friday)]
    # The whole bulletin was cached: EUR for Saturday needs no request.
    assert fx.get_rate(db, "EUR", dt.date(2025, 3, 8)).try_per_unit == Decimal("39.250000")
    assert len(fake_tcmb.calls) == 1
    db.commit()
    stored = db.query(FxRate).filter(FxRate.rate_date == friday).count()
    assert stored == 2


def test_holiday_walks_back_and_remembers_the_missing_day(db, fake_tcmb, frozen_today):
    holiday, before = dt.date(2025, 4, 23), dt.date(2025, 4, 22)  # a Wednesday, a Tuesday
    frozen_today(dt.date(2025, 5, 1))
    fake_tcmb.missing(holiday)
    fake_tcmb.serve(before, bulletin(before, {"GBP": "49.0001"}))
    assert fx.get_rate(db, "GBP", holiday).rate_date == before
    assert len(fake_tcmb.calls) == 2
    assert fx.get_rate(db, "GBP", holiday).rate_date == before
    assert len(fake_tcmb.calls) == 2  # the 404 and the cached Tuesday are both remembered


def test_future_dates_are_clamped_to_today(db, fake_tcmb, frozen_today):
    today = dt.date(2025, 6, 2)
    frozen_today(today)
    fake_tcmb.serve(today, bulletin(today, {"CHF": "45.5"}))
    assert fx.get_rate(db, "CHF", dt.date(2025, 7, 1)).rate_date == today


def test_try_unknown_currency_and_offline(db, fake_tcmb, frozen_today):
    day = dt.date(2025, 6, 10)
    frozen_today(day)
    assert fx.get_rate(db, "TL", day) == fx.Rate("TRY", day, Decimal(1))
    with pytest.raises(InvalidInput):
        fx.get_rate(db, "dollars", day)
    fake_tcmb.serve(day, bulletin(day, {"USD": "38"}))
    with pytest.raises(InvalidInput, match="does not publish"):
        fx.get_rate(db, "THB", day)

    # Offline: a cached older day still answers; with nothing cached it is UpstreamError.
    fake_tcmb.down = True
    assert fx.get_rate(db, "USD", day + dt.timedelta(days=1)).rate_date == day
    with pytest.raises(UpstreamError):
        fx.get_rate(db, "USD", dt.date(2025, 1, 15))


def test_no_bulletin_for_a_week_is_invalid_input(db, fake_tcmb, frozen_today):
    end = dt.date(2025, 7, 18)
    frozen_today(end)
    for back in range(8):
        fake_tcmb.missing(end - dt.timedelta(days=back))
    with pytest.raises(InvalidInput, match="no exchange rates"):
        fx.get_rate(db, "USD", end)


def test_refresh_rates_stores_today_xml(db, fake_tcmb):
    fake_tcmb.pages[f"{get_settings().tcmb_base_url}/today.xml"] = (200, FIXTURE.read_bytes())
    assert fx.refresh_rates(db) == 7
    assert fx.refresh_rates(db) == 7  # idempotent
    rows = db.query(FxRate).filter(FxRate.rate_date == dt.date(2026, 10, 9)).all()
    assert len(rows) == 7 and {r.source for r in rows} == {"TCMB"}


# --- exact conversion ---------------------------------------------------------------------


def test_convert_minor_rounds_half_even():
    assert fx.convert_minor(2500, Decimal(42)) == 105000
    assert fx.convert_minor(1, Decimal("0.5")) == 0  # 0.5 -> 0 (even)
    assert fx.convert_minor(3, Decimal("0.5")) == 2  # 1.5 -> 2 (even)
    assert fx.convert_minor(5, Decimal("0.5")) == 2  # 2.5 -> 2 (even)
    assert fx.convert_minor(1999, Decimal("49.2160")) == 98383  # 98382.784, not a tie


def test_convert_minor_cross_rate_is_exact():
    # 100.00 USD to EUR with USD 49.2160 and EUR 55.2105 TRY: 10000 * 49.216 / 55.2105
    assert fx.convert_minor(10000, Decimal("49.2160"), Decimal("55.2105")) == 8914
    with pytest.raises(InvalidInput):
        fx.convert_minor(100, Decimal(0))


@pytest.mark.parametrize(
    ("weights", "target", "expected"),
    [
        ([1000, 1500], 105000, [42000, 63000]),
        ([1, 1, 1], 100, [34, 33, 33]),
        ([333, 333, 334], 1001, [333, 333, 335]),
        ([500, -100, 600], 2000, [1000, -200, 1200]),
        ([7], 13, [13]),
    ],
)
def test_allocate_proportionally_always_sums(weights, target, expected):
    assert fx.allocate_proportionally(weights, target) == expected
    assert sum(fx.allocate_proportionally(weights, target)) == target


def test_format_helpers():
    assert fx.format_amount(105000) == "1,050.00"
    assert fx.format_amount(-12345) == "-123.45"
    assert fx.format_rate(Decimal(42)) == "42.0000"
    assert fx.format_rate(Decimal("0.311727")) == "0.311727"
    assert fx.format_rate(Decimal("49.21")) == "49.2100"


# --- the pipeline hook --------------------------------------------------------------------


def _seed(db, day: dt.date, **rates: str) -> None:
    for code, rate in rates.items():
        db.add(FxRate(rate_date=day, currency=code, try_per_unit=Decimal(rate)))
    db.commit()


def test_apply_base_currency_converts_total_and_items(db, fake_tcmb, frozen_today):
    rate_day = dt.date(2025, 8, 8)  # Friday; the purchase is on Saturday
    frozen_today(dt.date(2025, 8, 20))
    _seed(db, rate_day, USD="42.000000")
    data = ExpenseInput(
        "Amazon.com",
        "25.00",
        expense_date=dt.date(2025, 8, 9),
        currency="USD",
        items=[ItemInput("Book", "10.00"), ItemInput("Cable", "15.00")],
    )
    expense = build_expense("fx-user", data)
    warnings = fx.apply_base_currency(db, expense, "TRY")

    assert warnings == ["Converted 25.00 USD to 1,050.00 TRY at TCMB rate 42.0000 (2025-08-08)."]
    assert (expense.currency, expense.total_minor) == ("TRY", 105000)
    assert (expense.original_currency, expense.original_total_minor) == ("USD", 2500)
    assert expense.fx_rate == Decimal("42.000000") and expense.fx_date == rate_day
    assert [i.amount_minor for i in expense.items] == [42000, 63000]
    assert fake_tcmb.calls == []


def test_items_that_need_rounding_still_sum_to_the_total(db, frozen_today):
    day = dt.date(2025, 8, 11)
    frozen_today(day)
    _seed(db, day, EUR="37.123457")
    expense = Expense(
        owner_id="fx-user",
        merchant="Bakery",
        expense_date=day,
        currency="EUR",
        total_minor=1000,
        items=[ExpenseItem(description=n, amount_minor=a) for n, a in [("a", 333), ("b", 333), ("c", 334)]],
    )
    fx.apply_base_currency(db, expense, "TRY")
    assert expense.total_minor == 37123  # 37123.457 -> 37123
    assert sum(i.amount_minor for i in expense.items) == expense.total_minor

    # Items that did not match the total keep their own (converted) sum.
    other = Expense(
        owner_id="fx-user",
        merchant="Shop",
        expense_date=day,
        currency="EUR",
        total_minor=900,  # a 1.00 EUR discount not on the lines
        items=[
            ExpenseItem(description="x", amount_minor=600),
            ExpenseItem(description="y", amount_minor=400),
        ],
    )
    fx.apply_base_currency(db, other, "TRY")
    assert other.total_minor == fx.convert_minor(900, Decimal("37.123457"))
    assert sum(i.amount_minor for i in other.items) == fx.convert_minor(1000, Decimal("37.123457"))


def test_same_currency_is_untouched_and_missing_rate_is_invalid_input(db, fake_tcmb, frozen_today):
    frozen_today(dt.date(2025, 9, 3))
    expense = build_expense("fx-user", ExpenseInput("Simit", "15", currency="TL"))
    assert fx.apply_base_currency(db, expense, "TRY") == []
    assert expense.original_currency is None and expense.total_minor == 1500

    fake_tcmb.down = True
    foreign = build_expense(
        "fx-user", ExpenseInput("Cafe", "4", expense_date=dt.date(2025, 9, 2), currency="EUR")
    )
    with pytest.raises(InvalidInput, match="could not convert 4.00 EUR to TRY"):
        fx.apply_base_currency(db, foreign, "TRY")
    assert foreign.currency == "EUR" and foreign.original_currency is None


def test_add_expense_runs_the_hook(db, frozen_today):
    day = dt.date(2025, 9, 5)
    frozen_today(day)
    _seed(db, day, GBP="51.500000")
    saved = add_expense(db, "fx-pipeline", ExpenseInput("Boots", "10.00", expense_date=day, currency="GBP"))
    e = saved.expense
    assert (e.currency, e.total_minor, e.original_currency, e.original_total_minor) == (
        "TRY",
        51500,
        "GBP",
        1000,
    )
    assert saved.warnings == ["Converted 10.00 GBP to 515.00 TRY at TCMB rate 51.5000 (2025-09-05)."]


# --- API ----------------------------------------------------------------------------------


def test_fx_api(client, fake_tcmb, frozen_today):
    day = dt.date(2025, 10, 6)
    frozen_today(dt.date(2025, 10, 10))
    fake_tcmb.serve(day, bulletin(day, {"USD": "41.5", "EUR": "48.25", "JPY": "27.5"}, unit={"JPY": 100}))
    headers = {"X-User-Id": "fx-api"}

    r = client.get("/fx/rates/eur", params={"on": "2025-10-06"}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"currency": "EUR", "rate_date": "2025-10-06", "try_per_unit": "48.250000"}

    r = client.get("/fx/rates", params={"on": "2025-10-06"}, headers=headers)
    assert r.json()["rate_date"] == "2025-10-06"
    assert [x["currency"] for x in r.json()["rates"]] == ["EUR", "JPY", "USD"]
    assert r.json()["rates"][1]["try_per_unit"] == "0.275000"

    r = client.get("/fx/convert", params={"amount": "50", "from": "EUR", "on": "2025-10-06"}, headers=headers)
    assert r.json() == {
        "from_currency": "EUR",
        "to_currency": "TRY",
        "on": "2025-10-06",
        "rate": "48.250000",
        "amount": "50.00",
        "amount_minor": 5000,
        "converted": "2412.50",
        "converted_minor": 241250,
    }
    r = client.get("/fx/convert", params={"amount": "100", "from": "TRY", "to": "USD", "on": "2025-10-06"})
    assert r.json()["converted"] == "2.41" and r.json()["rate"] == "0.024096"

    assert client.get("/fx/rates/XYZ", params={"on": "2025-10-06"}).status_code == 422
    assert client.get("/fx/rates/EURO").status_code == 422
    fake_tcmb.down = True
    assert client.get("/fx/rates/USD", params={"on": "2024-12-02"}).status_code == 502


def test_foreign_expense_through_the_api_and_a_house_in_euros(client, frozen_today):
    day = dt.date(2025, 10, 14)
    frozen_today(day)
    from app.db.session import session_for

    with session_for(None) as db:
        _seed(db, day, USD="41.000000", EUR="48.000000")

    r = client.post(
        "/expenses",
        json={"merchant": "Steam", "total": "19.99", "currency": "USD", "expense_date": day.isoformat()},
        headers={"X-User-Id": "fx-api-user"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["currency"], body["total"], body["original_currency"], body["original_total"]) == (
        "TRY",
        "819.59",  # 19.99 * 41 = 819.59
        "USD",
        "19.99",
    )
    assert body["fx_rate"].startswith("41.0") and body["fx_date"] == day.isoformat()

    # A house in EUR: a USD bill is converted with the cross rate, then split.
    owner = {"X-User-Id": "fx-house-a"}
    house = client.post("/houses", json={"name": "Berlin flat", "currency": "EUR"}, headers=owner).json()
    client.post(f"/houses/{house['id']}/members", json={"user_id": "fx-house-b"}, headers=owner)
    r = client.post(
        f"/houses/{house['id']}/expenses",
        json={"merchant": "Netflix US", "total": "12.00", "currency": "USD", "expense_date": day.isoformat()},
        headers=owner,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    # 1200 * 41 / 48 = 1025 cents EUR
    assert (body["currency"], body["total_minor"], body["original_currency"]) == ("EUR", 1025, "USD")
    assert sum(s["amount_minor"] for s in body["shares"]) == 1025
