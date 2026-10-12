"""Google Calendar API v3 client for settle-up reminders (owner: track HOUSE).

Uses the user's OAuth credentials from `google_oauth.credentials_for_user` (scope
calendar.events) and plain REST calls through `google.auth.transport.requests.AuthorizedSession`.
Raise `services.errors.UpstreamError` on API failures.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from google.oauth2.credentials import Credentials

CALENDAR_API = "https://www.googleapis.com/calendar/v3"


def create_event(
    creds: Credentials,
    *,
    summary: str,
    description: str,
    day: dt.date,
    attendee_emails: Sequence[str] = (),
    calendar_id: str = "primary",
) -> str:
    """Create an all-day event on `day` (with a popup reminder) and return its event id."""
    raise NotImplementedError("create_event: track HOUSE")


def delete_event(creds: Credentials, event_id: str, *, calendar_id: str = "primary") -> None:
    """Delete an event; a 404/410 (already gone) is not an error."""
    raise NotImplementedError("delete_event: track HOUSE")
