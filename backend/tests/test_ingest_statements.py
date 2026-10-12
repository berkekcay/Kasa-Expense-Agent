"""Bank statement import (track INGEST): CSV dialects, Turkish numbers and dates, keyword
categories, dedupe, and the PDF path with a faked statement parser runner."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from app.agents import runtime
from app.agents.tools.inbox_tools import StatementLineArg, submit_statement_lines
from app.config import get_settings
from app.db.session import init_db, session_for
from app.services import inbox, statements
from app.services.errors import InvalidInput
from app.services.statements import StatementLine, categorize, parse_amount, parse_csv, parse_date
from tests.fixtures.make_statements import PDF_LINES, build_blank_pdf, build_pdf

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _schema():
    init_db()


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def upload(client, user: str, name: str, data: bytes, content_type: str = "text/csv"):
    return client.post(
        "/imports/statement", files={"file": (name, data, content_type)}, headers=as_user(user)
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", ("1234.56", None)),
        ("-45,00 TL", ("-45.00", "TRY")),
        ("1,234.56", ("1234.56", None)),
        ("(45.00)", ("-45.00", None)),
        ("45,00-", ("-45.00", None)),
        ("+8.500,00", ("8500.00", None)),
        ("₺ 89,9", ("89.9", "TRY")),
        ("12.500", ("12500", None)),
        ("1.234.567", ("1234567", None)),
        ("10.99 USD", ("10.99", "USD")),
        ("€12,5", ("12.5", "EUR")),
        ("0,00", ("0.00", None)),
    ],
)
def test_parse_amount(raw, expected):
    value, currency = parse_amount(raw)
    assert (value, currency) == (Decimal(expected[0]), expected[1])


@pytest.mark.parametrize("raw", ["", "  ", "abc", "1,2,3x", "--"])
def test_parse_amount_rejects_garbage(raw):
    assert parse_amount(raw) is None


def test_parse_date():
    assert parse_date("05.10.2026") == dt.date(2026, 10, 5)
    assert parse_date("05/10/2026 14:32") == dt.date(2026, 10, 5)
    assert parse_date("2026-10-05") == dt.date(2026, 10, 5)
    assert parse_date("5-10-26") == dt.date(2026, 10, 5)
    assert parse_date("31.02.2026") is None
    assert parse_date("Toplam") is None


@pytest.mark.parametrize(
    ("description", "category"),
    [
        ("MİGROS KADIKÖY İSTANBUL TR", "groceries"),
        ("A101 YENI MAGAZACILIK", "groceries"),
        ("BİM BİRLEŞİK MAĞAZALAR", "groceries"),
        ("ŞOK MARKETLER KADIKÖY", "groceries"),
        ("CAFERAĞA SOKAK ESNAF", "other"),  # "SOKAK" is not ŞOK
        ("YEMEKSEPETI*BURGER ISTANBUL", "food"),
        ("GETIR BUYUK ISTANBUL", "food"),
        ("İSTANBULKART DOLUM BELBİM", "transport"),
        ("UBER *TRIP HELP.UBER.COM", "transport"),
        ("BITAKSI MOBIL", "transport"),
        ("NETFLIX.COM", "subscriptions"),
        ("SPOTIFY P1234ABCD STOCKHOLM", "subscriptions"),
        ("GOOGLE *YouTubePremium", "subscriptions"),
        ("AMAZON PRIME UYELIK", "subscriptions"),
        ("TURKCELL FATURA ÖDEME", "utilities"),
        ("VODAFONE NET", "utilities"),
        ("ENERJİSA ELEKTRİK FATURA", "utilities"),
        ("IGDAŞ DOĞALGAZ", "utilities"),
        ("İSKİ SU FATURASI", "utilities"),
        ("TRENDYOL.COM", "shopping"),
        ("ECZANE ŞİFA", "health"),
        ("D&R KADIKÖY KİTAP", "education"),
        ("CINEMAXIMUM KADIKÖY", "entertainment"),
        ("PEGASUS HAVA YOLLARI", "travel"),
        ("KİRA ÖDEMESİ EV SAHİBİ", "rent"),
        ("UNKNOWN SHOP 42", "other"),
    ],
)
def test_categorize(description, category):
    assert categorize(description) == category


def test_garanti_like_cp1254_semicolon_export():
    data = (FIXTURES / "statement_garanti_like.csv").read_bytes()
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")  # really Windows-1254
    parsed = statements._parse_csv(data)
    assert parsed.rows == 14 and parsed.skipped == 3  # salary, incoming FAST, totals footer
    lines = parsed.lines
    assert len(lines) == 12
    assert lines[0] == StatementLine(dt.date(2026, 9, 2), "MİGROS KADIKÖY İSTANBUL TR", "245.90", "TRY")
    assert [x.amount for x in lines if x.description.startswith("KİRA")] == ["9000.00"]
    assert all("MAAŞ" not in x.description and "GELEN" not in x.description for x in lines)


def test_english_debit_credit_export():
    lines = parse_csv((FIXTURES / "statement_card_en.csv").read_bytes())
    assert [(x.description, x.amount, x.currency) for x in lines] == [
        ("UBER *TRIP HELP.UBER.COM", "145.20", "TRY"),
        ("SPOTIFY P1234ABCD STOCKHOLM", "59.99", "TRY"),
        ("AMAZON.COM.TR", "1249.00", "TRY"),
        ("STEAM PURCHASE", "10.99", "USD"),
        ("UNKNOWN SHOP 42", "75.00", "TRY"),
    ]
    assert lines[0].posted_on == dt.date(2026, 9, 2)  # transaction date, not posting date


def test_tab_delimited_borc_alacak_with_bom():
    text = (
        "İşlem Tarihi\tAçıklama\tBorç\tAlacak\tBakiye\n"
        "03/10/2026\tA101 KADIKÖY\t54,50\t\t1.000,00\n"
        "04/10/2026\tFAST GELEN\t\t500,00\t1.500,00\n"
        "05/10/2026\tSPOTIFY\t59,99\t0,00\t1.440,01\n"
    )
    lines = parse_csv(text.encode("utf-8-sig"))
    assert [(x.description, x.amount) for x in lines] == [("A101 KADIKÖY", "54.50"), ("SPOTIFY", "59.99")]


def test_card_statement_with_positive_spending():
    text = (
        "Tarih,İşlem,Tutar\n"
        '01.10.2026,MIGROS,"120,00"\n'
        '02.10.2026,YEMEKSEPETI,"89,90"\n'
        '03.10.2026,HESAPTAN ÖDEME,"-1.000,00"\n'
        '04.10.2026,TRENDYOL IADE,"-49,90"\n'
        '05.10.2026,NETFLIX,"229,99 TL"\n'
    )
    lines = parse_csv(text.encode("utf-8"))
    assert [x.amount for x in lines] == ["120.00", "89.90", "229.99"]


def test_csv_without_headers_is_rejected():
    with pytest.raises(InvalidInput, match="column headers"):
        parse_csv(b"a;b;c\n1;2;3\n")


def test_line_ref_is_stable_and_counts_identical_lines():
    line = StatementLine(dt.date(2026, 9, 21), "STARBUCKS  Moda", "135.00")
    same = StatementLine(dt.date(2026, 9, 21), "starbucks moda", "135.00")
    assert statements.line_ref(line, 0) == statements.line_ref(same, 0)
    assert statements.line_ref(line, 0) != statements.line_ref(line, 1)


def test_csv_upload_creates_pending_items_and_dedupes(client):
    user = "stmt-csv"
    data = (FIXTURES / "statement_garanti_like.csv").read_bytes()
    r = upload(client, user, "hesap_hareketleri.csv", data, "application/vnd.ms-excel")
    assert r.status_code == 201, r.text
    assert r.json() == {"lines": 14, "created": 12, "duplicates": 0, "skipped": 3, "errors": []}

    items = client.get("/inbox", headers=as_user(user)).json()
    assert len(items) == 12 and {i["status"] for i in items} == {"pending"}
    starbucks = [i for i in items if i["title"] == "STARBUCKS MODA"]
    assert len(starbucks) == 2  # two real coffees on the same day stay two items
    migros = next(i for i in items if i["title"].startswith("MİGROS"))
    assert migros["source"] == "statement" and migros["sender"] == "hesap_hareketleri.csv"
    assert migros["parsed"]["category"] == "groceries" and migros["parsed"]["expense_date"] == "2026-09-02"
    assert migros["excerpt"].startswith("02.09.2026 | MİGROS")

    again = upload(client, user, "copy.csv", data)
    assert again.json()["created"] == 0 and again.json()["duplicates"] == 12

    r = client.post(f"/inbox/{migros['id']}/approve", json={}, headers=as_user(user))
    assert r.status_code == 200
    expense = r.json()["expense"]
    assert (
        expense["source"] == "statement"
        and expense["total"] == "245.90"
        and expense["category"] == "groceries"
    )


def test_upload_limits_and_types(client, monkeypatch):
    user = "stmt-limits"
    assert upload(client, user, "photo.png", b"\x89PNG", "image/png").status_code == 415
    assert upload(client, user, "empty.csv", b"").status_code == 422
    assert upload(client, user, "junk.csv", b"hello;world;x\n").status_code == 422
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    big = (FIXTURES / "statement_garanti_like.csv").read_bytes()
    assert upload(client, user, "big.csv", big).status_code == 413
    # Some browsers send CSV as application/octet-stream; the extension decides.
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 10_000)
    r = upload(
        client,
        user,
        "card.csv",
        (FIXTURES / "statement_card_en.csv").read_bytes(),
        "application/octet-stream",
    )
    assert r.status_code == 201 and r.json()["created"] == 5


# --- PDF -----------------------------------------------------------------------------------------


def test_pdf_fixture_has_turkish_text():
    text = statements.pdf_text((FIXTURES / "statement_card.pdf").read_bytes())
    assert "MİGROS ATAŞEHİR İSTANBUL" in text and "Dönem Borcu" in text
    assert (FIXTURES / "statement_card.pdf").read_bytes() == build_pdf(PDF_LINES)  # fixture is current


def test_scanned_or_broken_pdf_is_a_clear_422(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    r = upload(client, "stmt-scan", "scan.pdf", build_blank_pdf(), "application/pdf")
    assert r.status_code == 422 and "no text layer" in r.json()["detail"]
    r = upload(client, "stmt-scan", "broken.pdf", b"%PDF-1.4 garbage", "application/pdf")
    assert r.status_code == 422


def test_pdf_needs_an_llm_provider(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_api_key", "")
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    r = upload(
        client, "stmt-nollm", "card.pdf", (FIXTURES / "statement_card.pdf").read_bytes(), "application/pdf"
    )
    assert r.status_code == 503 and "CSV files work without it" in r.json()["detail"]


def test_pdf_upload_goes_through_the_statement_parser(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    prompts = []

    async def fake_run(kind, user_id, parts, session_id=None):
        prompts.append((kind, user_id, parts[0].text))
        # What the real tool returns for what a model would extract from the fixture.
        result = submit_statement_lines(
            [
                StatementLineArg(
                    posted_on="2026-09-02", description="MİGROS ATAŞEHİR İSTANBUL", amount="412.35"
                ),
                StatementLineArg(posted_on="2026-09-04", description="YEMEKSEPETİ İSTANBUL", amount="189.90"),
                StatementLineArg(
                    posted_on="2026-09-13", description="ENERJİSA ELEKTRİK FATURA", amount="684.75"
                ),
                StatementLineArg(posted_on="2026-09-17", description="TRENDYOL.COM", amount="1249.99"),
                StatementLineArg(posted_on="2026-09-26", description="CINEMAXIMUM KADIKÖY", amount="260,00"),
                StatementLineArg(posted_on="2026-09-31", description="BAD DATE", amount="1"),
            ],
            None,
        )
        return runtime.AgentRun(session_id="s", text="", tool_results=[("submit_statement_lines", result)])

    monkeypatch.setattr(runtime, "run_agent", fake_run)
    data = (FIXTURES / "statement_card.pdf").read_bytes()
    r = upload(client, "stmt-pdf", "ekstre_eylul.pdf", data, "application/pdf")
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["lines"], body["created"], body["duplicates"]) == (5, 5, 0)
    assert len(body["errors"]) == 1 and "line 6" in body["errors"][0]

    kind, user_id, prompt = prompts[0]
    assert kind == "statement-parse" and user_id == "stmt-pdf"
    assert "untrusted document text" in prompt and "MİGROS ATAŞEHİR İSTANBUL" in prompt

    items = {i["title"]: i for i in client.get("/inbox", headers=as_user("stmt-pdf")).json()}
    assert items["ENERJİSA ELEKTRİK FATURA"]["parsed"]["category"] == "utilities"
    assert items["CINEMAXIMUM KADIKÖY"]["parsed"]["total"] == "260.00"
    again = upload(client, "stmt-pdf", "ekstre_eylul.pdf", data, "application/pdf")
    assert again.json()["duplicates"] == 5 and again.json()["created"] == 0


def test_long_pdf_text_is_chunked():
    text = "\n".join(f"0{i % 9 + 1}.09.2026 SHOP {i} 10,00" for i in range(3000))
    chunks = statements._chunks(text, size=5000)
    assert len(chunks) > 1 and all(len(c) <= 5100 for c in chunks)
    assert "".join(chunks).count("SHOP") == 3000


def test_import_statement_service_directly(db):
    user = "stmt-service"
    import asyncio

    data = b"Date,Description,Amount\n2026-10-01,MIGROS,-10.00\n2026-10-02,SALARY,500.00\n"
    result = asyncio.run(
        statements.import_statement(db, user, filename="x.csv", content_type="text/csv", data=data)
    )
    assert (result.lines, result.created, result.skipped) == (2, 1, 1)
    with session_for(user) as other:
        assert [i.title for i in inbox.list_items(other, user)] == ["MIGROS"]
