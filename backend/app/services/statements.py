"""Bank / card statement import, CSV and PDF (owner: track INGEST).

CSV: detect delimiter (; or ,), header row and the date / description / amount columns of
common Turkish bank exports (dates like 05.10.2026, amounts like "1.234,56" or "-89,90").
PDF: extract text with pypdf, then run the "statement-parse" agent runner on it.
Each spending line becomes an InboxItem (source "statement") with external_ref =
`line_ref(...)`, so importing the same file twice creates nothing new.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class StatementLine:
    posted_on: dt.date
    description: str
    amount: str  # major units, positive = money spent; refunds/payments are skipped
    currency: str = "TRY"


@dataclass
class ImportResult:
    lines: int = 0
    created: int = 0
    duplicates: int = 0
    skipped: int = 0  # credits, payments, unparseable rows
    errors: list[str] = field(default_factory=list)


def line_ref(line: StatementLine, ordinal: int) -> str:
    """Stable dedupe key for a statement line. `ordinal` counts identical lines (same day,
    text and amount) within one file, so two real identical coffees stay two items."""
    raw = f"{line.posted_on.isoformat()}|{' '.join(line.description.lower().split())}|{line.amount}|{line.currency}|{ordinal}"
    return "stmt:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def parse_csv(data: bytes) -> list[StatementLine]:
    raise NotImplementedError("parse_csv: track INGEST")


async def parse_pdf(user_id: str, data: bytes) -> list[StatementLine]:
    raise NotImplementedError("parse_pdf: track INGEST")


async def import_statement(
    db: Session, user_id: str, *, filename: str, content_type: str, data: bytes
) -> ImportResult:
    """Dispatch on content type / extension (text/csv, application/pdf), create inbox items."""
    raise NotImplementedError("import_statement: track INGEST")
