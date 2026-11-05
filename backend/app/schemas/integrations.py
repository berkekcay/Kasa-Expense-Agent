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


class MailStatusOut(BaseModel):
    """The IMAP mailbox (app password), the Google-free way to bring purchase emails in."""

    ready: bool  # the server can store passwords (TOKEN_ENCRYPTION_KEY) and a model is set
    connected: bool
    address: str | None = None
    host: str | None = None
    folder: str | None = None
    last_sync_at: dt.datetime | None = None  # UTC
    last_error: str | None = None


class MailConnectIn(BaseModel):
    address: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)  # an app password, not the main one
    host: str | None = Field(default=None, max_length=255)  # empty: guessed from the address
    folder: str = Field(default="INBOX", max_length=200)
