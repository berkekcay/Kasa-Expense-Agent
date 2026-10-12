"""Statement import schemas (owner: track INGEST)."""

from __future__ import annotations

from pydantic import BaseModel


class ImportResultOut(BaseModel):
    lines: int
    created: int
    duplicates: int
    skipped: int
    errors: list[str] = []
