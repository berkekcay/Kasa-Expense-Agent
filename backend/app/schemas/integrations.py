"""Google integration schemas (owner: track INGEST)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field


class GoogleConnectOut(BaseModel):
    url: str  # send the browser here


class GoogleExchangeIn(BaseModel):
    """For a frontend-hosted OAuth redirect page: it posts what Google sent it."""

    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=2048)


class GoogleStatusOut(BaseModel):
    configured: bool  # OAuth client + encryption key are set on the server
    connected: bool
    google_email: str | None = None
    scopes: list[str] = []
    gmail_access: bool = False
    calendar_access: bool = False
    gmail_watch_expires_at: dt.datetime | None = None  # UTC; None = no push, hourly sync only


class SyncResultOut(BaseModel):
    fetched: int
    created: int
    ignored: int
    duplicates: int
    failed: int
    error: str | None = None
