"""Gmail API v1 client (owner: track INGEST). Read-only scope; REST via
`google.auth.transport.requests.AuthorizedSession`. Raise UpstreamError on API failures.

Email content is untrusted DATA: it is shown to the email-parse agent as text, never as
instructions, and never rendered as HTML anywhere.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from google.oauth2.credentials import Credentials

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    history_id: str
    received_at: dt.datetime  # internalDate, UTC
    subject: str
    sender: str
    snippet: str
    body_text: str  # text/plain part, or HTML converted to plain text; trimmed to ~20k chars
    attachment_names: list[str] = field(default_factory=list)


def list_message_ids(creds: Credentials, query: str, *, max_results: int = 50) -> list[str]:
    raise NotImplementedError("list_message_ids: track INGEST")


def get_message(creds: Credentials, message_id: str) -> GmailMessage:
    raise NotImplementedError("get_message: track INGEST")


def list_history(creds: Credentials, start_history_id: str) -> tuple[list[str], str]:
    """Message ids added since `start_history_id` and the new latest history id.
    Raise NotFound when Google says the start id is too old (caller falls back to a query)."""
    raise NotImplementedError("list_history: track INGEST")


def watch(creds: Credentials, topic: str) -> tuple[str, dt.datetime]:
    """users.watch on INBOX to the Pub/Sub topic; returns (history_id, expiration UTC)."""
    raise NotImplementedError("watch: track INGEST")


def stop_watch(creds: Credentials) -> None:
    raise NotImplementedError("stop_watch: track INGEST")
