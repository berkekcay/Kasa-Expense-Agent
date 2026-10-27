"""Chat file analysis: parsing Excel/CSV, describing, querying safely, preparing an import."""

from __future__ import annotations

import datetime as dt
import io

import pytest
from openpyxl import Workbook

from app.services import sheets
from app.services.errors import InvalidInput, NotFound

CSV = (
    "Hesap Özeti;;;\n"
    "Tarih;Açıklama;Tutar;Kategori\n"
    "01.10.2026;MİGROS KADIKÖY;-245,90;market\n"
    "02.10.2026;MAAŞ;15.000,00;gelir\n"
    "03.10.2026;Starbucks;-89,50;kahve\n"
    "03.10.2026;Starbucks;-89,50;kahve\n"
    "05.10.2026;İADE TRENDYOL;120,00;iade\n"
).encode("cp1254")


def _xlsx() -> bytes:
    book = Workbook()
    ws = book.active
    ws.title = "Ekim"
    ws.append(["Kart ekstresi"])
    ws.append(["Date", "Merchant", "Amount"])
    ws.append([dt.date(2026, 10, 1), "Migros", 245.9])
    ws.append([dt.date(2026, 10, 2), "Metro", 15.0])
    ws.append([dt.date(2026, 11, 3), "Migros", 100.1])
    other = book.create_sheet("Notes")
    other.append(["a", "b"])
    other.append(["x", "y"])
    buf = io.BytesIO()
    book.save(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clean_store():
    sheets.uploads.clear()
    sheets.drafts.clear()
    yield
    sheets.uploads.clear()
    sheets.drafts.clear()


def test_csv_finds_the_header_under_a_title_and_infers_types():
    upload = sheets.store_upload("u1", "ekstre.csv", CSV)
    [sheet] = upload.sheets
    assert sheet.columns == ["Tarih", "Açıklama", "Tutar", "Kategori"]
    assert sheet.types == ["date", "text", "number", "text"]
    assert len(sheet.rows) == 5
    info = sheets.describe(upload)
    tutar = next(c for c in info["columns"] if c["name"] == "Tutar")
    assert (tutar["min"], tutar["max"]) == ("-245.90", "15000.00")
    tarih = next(c for c in info["columns"] if c["name"] == "Tarih")
    assert (tarih["first"], tarih["last"]) == ("2026-10-01", "2026-10-05")
    assert "Ekim" not in sheets.summary_line(upload) and upload.id in sheets.summary_line(upload)


def test_xlsx_reads_every_sheet_with_real_dates_and_numbers():
    upload = sheets.store_upload("u1", "kart.xlsx", _xlsx())
    assert [s.name for s in upload.sheets] == ["Ekim", "Notes"]
    ekim = upload.sheet("ekim")
    assert ekim.columns == ["Date", "Merchant", "Amount"]
    assert ekim.rows[0] == ["2026-10-01", "Migros", "245.9"]
    assert ekim.types == ["date", "text", "number"]
    page = sheets.rows(upload, "Ekim", offset=1, limit=1)
    assert page["rows"] == [{"Date": "2026-10-02", "Merchant": "Metro", "Amount": "15"}]
    assert page["next_offset"] == 2


def test_query_groups_and_sums_over_the_data_table():
    upload = sheets.store_upload("u1", "kart.xlsx", _xlsx())
    result = sheets.query(
        upload,
        "SELECT strftime('%Y-%m', Date) AS month, SUM(Amount) AS total FROM data GROUP BY month ORDER BY month",
    )
    assert result["rows"] == [{"month": "2026-10", "total": 260.9}, {"month": "2026-11", "total": 100.1}]
    csv_upload = sheets.store_upload("u1", "e.csv", CSV)
    top = sheets.query(
        csv_upload, 'SELECT "Açıklama", COUNT(*) AS n FROM data GROUP BY 1 ORDER BY n DESC LIMIT 1'
    )
    assert top["rows"] == [{"Açıklama": "Starbucks", "n": 2}]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM data",
        "SELECT * FROM data; SELECT 1",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM expenses",
        "ATTACH DATABASE 'x.db' AS x",
        "SELECT load_extension('evil')",
        "PRAGMA table_info(data)",
    ],
)
def test_query_rejects_anything_but_one_select_over_data(sql):
    upload = sheets.store_upload("u1", "e.csv", CSV)
    with pytest.raises(InvalidInput):
        sheets.query(upload, sql)


def test_files_are_private_to_their_user():
    upload = sheets.store_upload("owner", "e.csv", CSV)
    with pytest.raises(NotFound):
        sheets.get_upload("someone-else", upload.id)


def test_prepare_import_keeps_spending_only_with_exact_amounts():
    upload = sheets.store_upload("u1", "e.csv", CSV)
    draft, preview = sheets.prepare_import(
        upload, date_column="tarih", description_column="Açıklama", amount_column="Tutar"
    )
    # Bank style: spending is negative; the salary and the refund are skipped.
    assert [(x.description, x.amount) for x in draft.lines] == [
        ("MİGROS KADIKÖY", "245.90"),
        ("Starbucks", "89.50"),
        ("Starbucks", "89.50"),
    ]
    assert preview["count"] == 3 and preview["totals"] == [{"currency": "TRY", "total": "424.90"}]
    assert preview["skipped"] == 2
    assert sheets.get_draft("u1", draft.id) is draft
    with pytest.raises(NotFound):
        sheets.get_draft("u2", draft.id)


def test_prepare_import_names_a_missing_column():
    upload = sheets.store_upload("u1", "e.csv", CSV)
    with pytest.raises(InvalidInput, match="no column 'Amount'"):
        sheets.prepare_import(
            upload, date_column="Tarih", description_column="Açıklama", amount_column="Amount"
        )


def test_broken_and_old_excel_files_get_a_clear_error():
    with pytest.raises(InvalidInput, match="xlsx"):
        sheets.parse_file("x.xlsx", b"PK\x03\x04 not really a zip")
    with pytest.raises(InvalidInput, match=".xls files are not supported"):
        sheets.parse_file("old.xls", b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
    with pytest.raises(InvalidInput, match="empty"):
        sheets.parse_file("e.csv", b"")
