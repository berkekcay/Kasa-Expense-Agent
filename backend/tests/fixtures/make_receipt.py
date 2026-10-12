"""Draw the synthetic Turkish market receipt used by the live receipt test.

    python tests/fixtures/make_receipt.py      # writes tests/fixtures/receipt_market.png

Needs Pillow (requirements-dev.txt) and a monospace font with Turkish letters (Consolas on
Windows, DejaVu Sans Mono on Linux). The shop is made up. The expected values live in
RECEIPT below, and tests/test_live.py imports them.
"""

from __future__ import annotations

import random
from pathlib import Path

RECEIPT = {
    "merchant": "ÖZDEMİR MARKET",
    "date": "2026-10-05",
    "total": "239.35",
    "items": [
        ("EKMEK", "1", "10,00"),
        ("SÜT 1 LT", "1", "32,50"),
        ("YUMURTA 10'LU", "1", "64,90"),
        ("DOMATES KG", "1,250", "42,00"),
        ("ÇAY 500 GR", "1", "89,95"),
    ],
}

FONT_CANDIDATES = [
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/Library/Fonts/Menlo.ttc",
]

OUT = Path(__file__).with_name("receipt_market.png")


def main() -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    font_path = next(p for p in FONT_CANDIDATES if Path(p).exists())
    body = ImageFont.truetype(font_path, 26)
    big = ImageFont.truetype(font_path, 34)
    width = 620
    lines: list[tuple[str, ImageFont.FreeTypeFont, str]] = [
        ("ÖZDEMİR MARKET", big, "center"),
        ("ÖZDEMİR GIDA SAN. VE TİC. LTD. ŞTİ.", body, "center"),
        ("CAFERAĞA MAH. MODA CAD. NO:41", body, "center"),
        ("KADIKÖY / İSTANBUL", body, "center"),
        ("KADIKÖY V.D. 6540012345", body, "center"),
        ("", body, "left"),
        ("TARİH: 05.10.2026      SAAT: 18:42", body, "left"),
        ("FİŞ NO: 0087", body, "left"),
        ("-" * 38, body, "left"),
    ]
    for name, qty, price in RECEIPT["items"]:
        label = name if qty == "1" else f"{name} x{qty}"
        lines.append((f"{label:<24}%01  *{price:>7}", body, "left"))
    lines += [
        ("-" * 38, body, "left"),
        (f"{'TOPKDV':<26}{'*2,37':>12}", body, "left"),
        ("TOPLAM|*239,35", big, "split"),
        ("-" * 38, body, "left"),
        (f"{'NAKİT':<26}{'*250,00':>12}", body, "left"),
        (f"{'PARA ÜSTÜ':<26}{'*10,65':>12}", body, "left"),
        ("", body, "left"),
        ("TEŞEKKÜR EDERİZ", body, "center"),
        ("EKÜ NO:0001   Z NO:0214", body, "center"),
        ("MF YAB 20012345", body, "center"),
    ]
    line_h = 40
    height = 60 + line_h * len(lines) + 40
    img = Image.new("L", (width, height), 250)
    draw = ImageDraw.Draw(img)
    y = 40
    for text, font, align in lines:
        if align == "split":  # label on the left, amount right-aligned
            left, right = text.split("|")
            draw.text((30, y), left, fill=25, font=font)
            draw.text((width - 40 - draw.textlength(right, font=font), y), right, fill=25, font=font)
        else:
            w = draw.textlength(text, font=font)
            x = (width - w) / 2 if align == "center" else 30
            draw.text((x, y), text, fill=25, font=font)
        y += line_h
    # A little thermal-paper noise and a slight tilt, like a phone photo.
    rng = random.Random(7)
    for _ in range(1500):
        img.putpixel((rng.randrange(width), rng.randrange(height)), rng.randrange(170, 235))
    img = img.rotate(1.2, expand=True, fillcolor=210).filter(ImageFilter.GaussianBlur(0.6))
    img.convert("RGB").save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
