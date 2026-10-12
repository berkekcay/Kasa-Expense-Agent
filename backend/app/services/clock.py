"""What "today" means for Kasa users.

Cloud Run runs in UTC, but a purchase at 01:00 in Istanbul belongs to that Turkish day.
Türkiye has used UTC+3 all year since 2016, so a fixed offset is enough (and needs no
tz database, which Windows lacks).
"""

from __future__ import annotations

import datetime as dt

KASA_TZ = dt.timezone(dt.timedelta(hours=3), "Europe/Istanbul")


def now() -> dt.datetime:
    return dt.datetime.now(KASA_TZ)


def today() -> dt.date:
    return now().date()
