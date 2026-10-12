"""TCMB (Central Bank of the Republic of Türkiye) daily exchange rates (owner: track MONEY).

Endpoints (settings.tcmb_base_url, default https://www.tcmb.gov.tr/kurlar):
  today:  {base}/today.xml                (the latest publication, not always today's date)
  a day:  {base}/YYYYMM/DDMMYYYY.xml      (404 on weekends / holidays / before 15:30)

Each <Currency Kod="USD"> has <Unit> (100 for JPY) and four prices. The rate we use is TRY
per 1 unit:

  1. ForexSelling / Unit
  2. else BanknoteSelling / Unit
  3. else derived from the USD cross rates of the same bulletin:
       CrossRateOther = USD per 1 unit of the currency (EUR, GBP, KWD, XDR...)
       CrossRateUSD   = units of the currency per 1 USD (AUD, JPY, CHF...)
     so TRY per unit = USD rate * CrossRateOther, or USD rate / CrossRateUSD.
     (Cross rates are already per single unit; Unit does not apply to them.)
  4. else the currency is skipped.

Empty elements (`<ForexSelling/>`, `<BanknoteSelling></BanknoteSelling>`) are "missing".
Rates are quantized to 6 decimals (ROUND_HALF_EVEN), the precision of `fx_rates`, so a
fresh rate and a cached one are always the same number. Parsing uses the standard library
XML parser on bytes we downloaded; no DTDs or entities are expanded by it.
"""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

import httpx

from app.services.errors import UpstreamError

RATE_PLACES = Decimal("0.000001")


class TcmbParseError(ValueError):
    """The document is not a TCMB rates bulletin."""


def _decimal(text: str | None) -> Decimal | None:
    if text is None or not text.strip():
        return None
    try:
        value = Decimal(text.strip().replace(",", "."))
    except InvalidOperation:
        return None
    return value if value.is_finite() and value > 0 else None


def _parse_day(text: str, order: str, sep: str) -> dt.date | None:
    """'09.10.2026' with order 'dmy' and sep '.', or '10/09/2026' with 'mdy' and '/'."""
    parts = text.strip().split(sep)
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    values = dict(zip(order, (int(p) for p in parts), strict=True))
    try:
        return dt.date(values["y"], values["m"], values["d"])
    except ValueError:
        return None


def _publication_date(root: ET.Element) -> dt.date:
    tarih = root.get("Tarih") or ""  # DD.MM.YYYY
    date = root.get("Date") or ""  # MM/DD/YYYY
    day = _parse_day(tarih, "dmy", ".") or _parse_day(date, "mdy", "/")
    if day is None:
        raise TcmbParseError(f"no publication date in TCMB bulletin (Tarih={tarih!r}, Date={date!r})")
    return day


def _q(value: Decimal) -> Decimal:
    return value.quantize(RATE_PLACES, rounding=ROUND_HALF_EVEN)


def parse_rates_xml(xml: bytes) -> tuple[dt.date, dict[str, Decimal]]:
    """Return (publication date from Tarih_Date/@Tarih, {currency: TRY per 1 unit})."""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise TcmbParseError(f"TCMB response is not XML: {exc}") from exc
    if root.tag != "Tarih_Date":
        raise TcmbParseError(f"unexpected TCMB root element <{root.tag}>")
    day = _publication_date(root)

    direct: dict[str, Decimal] = {}
    cross_other: dict[str, Decimal] = {}  # USD per 1 unit
    cross_usd: dict[str, Decimal] = {}  # units per 1 USD
    for node in root.iter("Currency"):
        code = (node.get("CurrencyCode") or node.get("Kod") or "").strip().upper()
        if len(code) != 3 or not code.isalpha():
            continue
        unit = _decimal(node.findtext("Unit")) or Decimal(1)
        price = _decimal(node.findtext("ForexSelling")) or _decimal(node.findtext("BanknoteSelling"))
        if price is not None:
            direct[code] = price / unit
            continue
        other = _decimal(node.findtext("CrossRateOther"))
        per_usd = _decimal(node.findtext("CrossRateUSD"))
        if other is not None:
            cross_other[code] = other
        elif per_usd is not None:
            cross_usd[code] = per_usd

    rates = dict(direct)
    usd = direct.get("USD")
    if usd is not None:
        for code, other in cross_other.items():
            rates[code] = usd * other
        for code, per_usd in cross_usd.items():
            rates[code] = usd / per_usd
    rates.pop("TRY", None)
    return day, {code: _q(rate) for code, rate in rates.items() if _q(rate) > 0}


def day_url(base_url: str, day: dt.date) -> str:
    return f"{base_url.rstrip('/')}/{day:%Y%m}/{day:%d%m%Y}.xml"


def _http_get(url: str, timeout: float) -> httpx.Response:
    """The single network call of this module (tests replace it)."""
    return httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "kasa/0.2"})


def fetch_rates(
    day: dt.date | None = None, *, base_url: str | None = None, timeout: float = 10.0
) -> tuple[dt.date, dict[str, Decimal]] | None:
    """Download and parse one day's rates (None = today.xml). Returns None when TCMB has no
    file for that day (weekend/holiday 404). Raises UpstreamError on other failures."""
    if base_url is None:
        from app.config import get_settings

        base_url = get_settings().tcmb_base_url
    url = f"{base_url.rstrip('/')}/today.xml" if day is None else day_url(base_url, day)
    try:
        response = _http_get(url, timeout)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"TCMB is unreachable ({type(exc).__name__})") from exc
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise UpstreamError(f"TCMB answered HTTP {response.status_code} for {url}")
    try:
        return parse_rates_xml(response.content)
    except TcmbParseError as exc:
        # An HTML error page instead of a bulletin: treat it like "no file for that day".
        if b"<html" in response.content[:500].lower():
            return None
        raise UpstreamError(str(exc)) from exc
