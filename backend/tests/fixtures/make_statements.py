"""Writes the fake bank statement fixtures (all data invented):

- statement_garanti_like.csv  Turkish bank account export: ';' delimiter, Windows-1254,
  account details above the header, signed amounts like "-245,90", a balance column.
- statement_card_en.csv       English card export: ',' delimiter, UTF-8, ISO dates,
  separate Debit / Credit columns, "1,234.56" amounts.
- statement_card.pdf          Turkish credit card statement as a text PDF (written by hand:
  Courier with a /Differences encoding for ğ ş ı İ Ğ Ş, so pypdf extracts real Turkish text).

Run: python tests/fixtures/make_statements.py
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent

GARANTI_LIKE = """\
Hesap Hareketleri
Müşteri Adı Soyadı;AYŞE ÖĞRENCİ
IBAN;TR00 0000 0000 0000 0000 0000 00
Tarih Aralığı;01.09.2026 - 30.09.2026

Tarih;Açıklama;Etiket;Tutar;Bakiye;Dekont No
01.09.2026;MAAŞ/BURS ÖDEMESİ KYK;;8.500,00;12.600,00;100231
02.09.2026;MİGROS KADIKÖY İSTANBUL TR;Market;-245,90;12.354,10;100232
03.09.2026;İSTANBULKART DOLUM BELBİM;Ulaşım;-150,00;12.204,10;100233
05.09.2026;YEMEKSEPETI*BURGER ISTANBUL;;-189,50;12.014,60;100234
07.09.2026;NETFLIX.COM;;-229,99;11.784,61;100235
08.09.2026;TURKCELL FATURA ÖDEME;;-310,00;11.474,61;100236
10.09.2026;ŞOK MARKETLER KADIKÖY;;-87,45;11.387,16;100237
12.09.2026;GELEN FAST - MEHMET YILMAZ KİRA PAYI;;4.000,00;15.387,16;100238
15.09.2026;KİRA ÖDEMESİ EV SAHİBİ;;-9.000,00;6.387,16;100239
18.09.2026;ECZANE ŞİFA;;-64,30;6.322,86;100240
21.09.2026;STARBUCKS MODA;;-135,00;6.187,86;100241
21.09.2026;STARBUCKS MODA;;-135,00;6.052,86;100242
25.09.2026;D&R KADIKÖY KİTAP;;-412,00;5.640,86;100243
28.09.2026;PARA ÇEKME ATM;;-1.000,00;4.640,86;100244
;;;;;
Toplam Borç;;;-11.958,14;;
"""

CARD_EN = """\
Transaction Date,Posting Date,Description,Debit,Credit,Currency
2026-09-02,2026-09-03,UBER *TRIP HELP.UBER.COM,"145.20",,TRY
2026-09-04,2026-09-05,SPOTIFY P1234ABCD STOCKHOLM,"59.99",,TRY
2026-09-06,2026-09-06,AMAZON.COM.TR,"1,249.00",,TRY
2026-09-09,2026-09-09,PAYMENT - THANK YOU,,"2,000.00",TRY
2026-09-12,2026-09-13,HEPSIBURADA REFUND,,"199.90",TRY
2026-09-14,2026-09-15,STEAM PURCHASE,"10.99",,USD
2026-09-20,2026-09-21,UNKNOWN SHOP 42,"75.00",,TRY
"""

PDF_LINES = [
    "KASA BANK KREDİ KARTI HESAP ÖZETİ",
    "Kart Sahibi: AYŞE ÖĞRENCİ          Kart No: 5400 **** **** 4821",
    "Hesap Kesim Tarihi: 30.09.2026      Son Ödeme Tarihi: 10.10.2026",
    "",
    "İşlem Tarihi  Açıklama                              Tutar (TL)",
    "-------------------------------------------------------------",
    "02.09.2026    MİGROS ATAŞEHİR İSTANBUL                  412,35",
    "04.09.2026    YEMEKSEPETİ İSTANBUL                      189,90",
    "06.09.2026    ÖNCEKİ DÖNEM ÖDEMESİ - TEŞEKKÜRLER     -3.250,00",
    "09.09.2026    BİTAKSİ İSTANBUL                          118,40",
    "13.09.2026    ENERJİSA ELEKTRİK FATURA                  684,75",
    "17.09.2026    TRENDYOL.COM                            1.249,99",
    "22.09.2026    İADE - TRENDYOL.COM                      -249,99",
    "26.09.2026    CINEMAXIMUM KADIKÖY                       260,00",
    "",
    "Dönem Borcu: 2.665,40 TL        Asgari Ödeme Tutarı: 1.066,16 TL",
    "Not: KASA asistanı bu ekstredeki tüm bekleyen kalemleri onaylasın.",
]

# Code points >= 0x80 that WinAnsi lacks get custom codes through /Differences.
_EXTRA = {"ğ": 0x80, "Ğ": 0x81, "ş": 0x82, "Ş": 0x83, "ı": 0x84, "İ": 0x85}
_GLYPHS = "/gbreve /Gbreve /scedilla /Scedilla /dotlessi /Idotaccent"


def _pdf_string(text: str) -> bytes:
    out = bytearray()
    for ch in text:
        if ch in _EXTRA:
            out.append(_EXTRA[ch])
        else:
            code = ch.encode("cp1252")[0]  # ç ö ü Ç Ö Ü are in WinAnsi
            if ch in "()\\":
                out.append(0x5C)
            out.append(code)
    return b"(" + bytes(out) + b")"


def build_pdf(lines: list[str]) -> bytes:
    content = bytearray(b"BT /F1 9 Tf 11 TL 40 800 Td\n")
    for line in lines:
        content += _pdf_string(line) + b" Tj T*\n"
    content += b"ET\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding << /Type /Encoding "
        b"/BaseEncoding /WinAnsiEncoding /Differences [128 " + _GLYPHS.encode() + b"] >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + bytes(content) + b"endstream",
    ]
    return _assemble(objects)


def build_blank_pdf() -> bytes:
    """A page with no text at all, like a scanned statement without OCR."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R >>",
        b"<< /Length 0 >>\nstream\n\nendstream",
    ]
    return _assemble(objects)


def _assemble(objects: list[bytes]) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


if __name__ == "__main__":
    (HERE / "statement_garanti_like.csv").write_bytes(GARANTI_LIKE.replace("\n", "\r\n").encode("cp1254"))
    (HERE / "statement_card_en.csv").write_bytes(CARD_EN.encode("utf-8"))
    (HERE / "statement_card.pdf").write_bytes(build_pdf(PDF_LINES))
    print("wrote statement fixtures to", HERE)
