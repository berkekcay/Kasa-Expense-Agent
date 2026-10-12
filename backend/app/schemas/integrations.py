"""Google integration schemas (owner: track INGEST)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class GoogleConnectOut(BaseModel):
    url: str  # send the browser here


class GoogleStatusOut(BaseModel):
    configured: bool  # OAuth client + encryption key are set on the server
    connected: bool
    google_email: str | None = None
    scopes: list[str] = []
    gmail_watch_expires_at: dt.datetime | None = None


class SyncResultOut(BaseModel):
    fetched: int
    created: int
    ignored: int
    duplicates: int
    failed: int
    error: str | None = None
