"""TCMB (Central Bank of the Republic of Türkiye) daily exchange rates (owner: track MONEY).

Endpoints (settings.tcmb_base_url, default https://www.tcmb.gov.tr/kurlar):
  today:  {base}/today.xml
  a day:  {base}/YYYYMM/DDMMYYYY.xml   (404 on weekends / holidays)
Each <Currency Kod="USD"> has <Unit> (e.g. 100 for JPY) and <ForexSelling>; the rate per
1 unit is ForexSelling / Unit. Parse with the standard library XML parser; never eval.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal


def parse_rates_xml(xml: bytes) -> tuple[dt.date, dict[str, Decimal]]:
    """Return (publication date from Tarih_Date/@Date, {currency: TRY per 1 unit})."""
    raise NotImplementedError("parse_rates_xml: track MONEY")


def fetch_rates(
    day: dt.date | None = None, *, base_url: str | None = None, timeout: float = 10.0
) -> tuple[dt.date, dict[str, Decimal]] | None:
    """Download and parse one day's rates (None = today.xml). Returns None when TCMB has no
    file for that day (weekend/holiday 404). Raises UpstreamError on other failures."""
    raise NotImplementedError("fetch_rates: track MONEY")
