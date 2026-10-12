"""Google Calendar API v3 client for settle-up reminders (owner: track HOUSE).

Uses the user's OAuth credentials from `google_oauth.credentials_for_user` (scope
calendar.events). Calls are plain REST through httpx with the credentials' access token;
an expired token is refreshed first by google-auth. API failures raise
`services.errors.UpstreamError`.

Tests swap `_new_client` (or pass `http=`) for an httpx client with a MockTransport.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from urllib.parse import quote

import httpx
from google.oauth2.credentials import Credentials

from app.services.errors import UpstreamError

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
TIMEOUT_SECONDS = 15
# Popup at 09:00 the day before (all-day events start at midnight).
REMINDER_MINUTES_BEFORE = 15 * 60


def _new_client() -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT_SECONDS)


def _access_token(creds: Credentials) -> str:
    if not creds.valid:
        try:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
        except Exception as exc:  # google-auth raises several types (RefreshError, TransportError)
            raise UpstreamError(f"could not refresh the Google token: {exc}") from exc
    if not creds.token:
        raise UpstreamError("Google credentials have no access token")
    return creds.token


def _events_url(calendar_id: str) -> str:
    return f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='@.')}/events"


def _error_message(response: httpx.Response) -> str:
    try:
        return response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        return response.text[:200] or response.reason_phrase


def _send(http: httpx.Client | None, method: str, url: str, **kwargs) -> httpx.Response:
    client = http or _new_client()
    try:
        return client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"Google Calendar request failed: {exc}") from exc
    finally:
        if http is None:
            client.close()


def create_event(
    creds: Credentials,
    *,
    summary: str,
    description: str,
    day: dt.date,
    attendee_emails: Sequence[str] = (),
    calendar_id: str = "primary",
    http: httpx.Client | None = None,
) -> str:
    """Create an all-day event on `day` (with a popup reminder) and return its event id.

    Attendees get Google's invitation email (sendUpdates=all).
    """
    attendees = list(dict.fromkeys(e.strip() for e in attendee_emails if e and e.strip()))
    body = {
        "summary": summary,
        "description": description,
        "start": {"date": day.isoformat()},
        "end": {"date": (day + dt.timedelta(days=1)).isoformat()},
        "attendees": [{"email": e} for e in attendees],
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": REMINDER_MINUTES_BEFORE}],
        },
        "transparency": "transparent",  # a reminder should not block the day
    }
    response = _send(
        http,
        "POST",
        _events_url(calendar_id),
        params={"sendUpdates": "all" if attendees else "none"},
        json=body,
        headers={"Authorization": f"Bearer {_access_token(creds)}"},
    )
    if response.status_code >= 400:
        raise UpstreamError(f"Google Calendar error {response.status_code}: {_error_message(response)}")
    try:
        return str(response.json()["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise UpstreamError("Google Calendar returned no event id") from exc


def delete_event(
    creds: Credentials,
    event_id: str,
    *,
    calendar_id: str = "primary",
    http: httpx.Client | None = None,
) -> None:
    """Delete an event (attendees are told); a 404/410 (already gone) is not an error."""
    response = _send(
        http,
        "DELETE",
        f"{_events_url(calendar_id)}/{quote(event_id, safe='')}",
        params={"sendUpdates": "all"},
        headers={"Authorization": f"Bearer {_access_token(creds)}"},
    )
    if response.status_code in (404, 410) or response.status_code < 400:
        return
    raise UpstreamError(f"Google Calendar error {response.status_code}: {_error_message(response)}")
