"""Settle-up reminders, optionally mirrored to Google Calendar (owner: track HOUSE).

A reminder is "from_user should pay to_user amount by due_date". They are created from the
current settle-up transfers of a house. When the acting user has connected Google
(`integrations.google_oauth.credentials_for_user`), an all-day event is added to their
primary calendar with the debtor and creditor invited by email (when `users.email` is
known, never the caller's own address).

Rules:
- Only house members can create, list or update reminders.
- Running it again does not duplicate: a transfer that already has a scheduled reminder
  with the same people and amount keeps that reminder (and its event).
- Running it again also cleans up: a scheduled reminder whose (from, to, amount) is no
  longer a suggested transfer is cancelled with cancel_reason "outdated" (its calendar
  event is deleted the same way a manual cancel does). Problems become warnings; a
  reminder whose event could not be deleted stays scheduled so nothing is left orphaned.
  `outdated_reminder_ids` marks such reminders in lists before that happens.
- Calendar problems never lose a reminder: it is saved with calendar_event_id=None and a
  warning says why.
- Any member can mark a reminder done or scheduled again. Only its creator can cancel it,
  because the event lives on the creator's calendar; cancelling deletes that event.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import REMINDER_STATUSES, Reminder, User
from app.integrations import google_calendar, google_oauth
from app.services import clock, houses
from app.services.errors import DomainError, Forbidden, InvalidInput, NotFound, UpstreamError
from app.services.money import format_minor

log = logging.getLogger(__name__)

NOT_CONNECTED = "Google Calendar is not connected, so the reminders are saved in Kasa only"


@dataclass
class CreatedReminders:
    reminders: list[Reminder]
    calendar_connected: bool
    warnings: list[str] = field(default_factory=list)
    cancelled: list[Reminder] = field(default_factory=list)  # outdated ones this call cancelled


TransferKey = tuple[str, str, int]  # (from_user, to_user, amount_minor)


def calendar_credentials(db: Session, user_id: str) -> Credentials | None:
    """The user's Google credentials, or None when Google is not connected, the user did
    not grant Calendar access (Gmail-only), or the integration is not available here."""
    try:
        creds = google_oauth.credentials_for_user(db, user_id)
    except NotImplementedError:
        return None
    except DomainError as exc:  # e.g. NotConfigured: no OAuth client or encryption key
        log.info("calendar credentials unavailable for %s: %s", user_id, exc)
        return None
    if creds is None:
        return None
    granted = set(getattr(creds, "scopes", None) or ())
    if granted and google_oauth.CALENDAR_SCOPE not in granted:
        log.info("calendar scope not granted for %s", user_id)
        return None
    return creds


def create_settle_up_reminders(
    db: Session, user_id: str, house_id: int, *, due_date: dt.date, add_to_calendar: bool = True
) -> CreatedReminders:
    """One reminder per current settle-up transfer (`houses.house_balances`). Members only.

    Returns the reminders (existing matching ones included, in transfer order), whether a
    Google account was used, warnings, and the outdated reminders this call cancelled.
    Calendar failures do not lose a reminder: it is saved with calendar_event_id=None.
    """
    if due_date < clock.today():
        raise InvalidInput("due date is in the past")
    result = houses.house_balances(db, user_id, house_id)
    house = result.house
    current = {(t.from_user, t.to_user, t.amount_minor) for t in result.transfers}

    open_rows = list(
        db.scalars(
            select(Reminder)
            .where(Reminder.house_id == house.id, Reminder.status == "scheduled")
            .order_by(Reminder.id)
        )
    )
    warnings: list[str] = []
    cancelled = _cancel_outdated(db, user_id, [r for r in open_rows if _key(r) not in current], warnings)
    if not result.transfers:
        db.commit()
        return CreatedReminders(
            reminders=[],
            calendar_connected=False,
            warnings=["everyone is settled up", *warnings],
            cancelled=cancelled,
        )

    existing = {_key(r): r for r in open_rows if r.status == "scheduled"}
    reminders: list[Reminder] = []
    new_rows: list[Reminder] = []
    for t in result.transfers:
        row = existing.get((t.from_user, t.to_user, t.amount_minor))
        if row is None:
            row = Reminder(
                house_id=house.id,
                from_user=t.from_user,
                to_user=t.to_user,
                amount_minor=t.amount_minor,
                currency=house.currency,
                due_date=due_date,
                created_by=user_id,
                status="scheduled",
            )
            db.add(row)
            new_rows.append(row)
        reminders.append(row)

    creds = calendar_credentials(db, user_id) if add_to_calendar and new_rows else None
    if add_to_calendar and new_rows and creds is None:
        warnings.append(NOT_CONNECTED)
    if creds is not None:
        people = _people(db, {u for r in new_rows for u in (r.from_user, r.to_user)})
        for row in new_rows:
            try:
                row.calendar_event_id = google_calendar.create_event(
                    creds,
                    summary=_summary(row, people),
                    description=_description(row, people, house.name),
                    day=row.due_date,
                    attendee_emails=[
                        people[u].email
                        for u in (row.from_user, row.to_user)
                        if u != user_id and u in people and people[u].email
                    ],
                )
            except UpstreamError as exc:
                log.warning("calendar event for reminder failed: %s", exc)
                warnings.append(f"calendar event for {row.from_user} -> {row.to_user} failed: {exc}")
    db.commit()
    return CreatedReminders(
        reminders=reminders, calendar_connected=creds is not None, warnings=warnings, cancelled=cancelled
    )


def _key(row: Reminder) -> TransferKey:
    return (row.from_user, row.to_user, row.amount_minor)


def _cancel_outdated(db: Session, user_id: str, rows: list[Reminder], warnings: list[str]) -> list[Reminder]:
    """Cancel scheduled reminders that no longer match a suggested transfer. Collects
    warnings instead of raising; a row whose event could not be deleted stays scheduled."""
    cancelled: list[Reminder] = []
    for row in rows:
        try:
            note = _cancel(db, row, user_id, reason="outdated")
        except UpstreamError as exc:
            log.warning("could not delete the calendar event of outdated reminder %s: %s", row.id, exc)
            warnings.append(
                f"old reminder {row.from_user} -> {row.to_user} {format_minor(row.amount_minor)} "
                f"{row.currency} stays scheduled: its calendar event could not be deleted ({exc})"
            )
            continue
        if note:
            warnings.append(note)
        cancelled.append(row)
    return cancelled


def _cancel(db: Session, row: Reminder, user_id: str, *, reason: str) -> str | None:
    """Cancel one reminder and delete its calendar event (the shared cancel path).

    The event lives on the creator's calendar, so only the creator's Google account can
    delete it. If Google is no longer connected the event cannot be reached and the reminder
    is cancelled anyway. If the Calendar API fails, UpstreamError is raised and nothing
    changes. Returns a note when someone else's event had to stay.
    """
    note = None
    if row.calendar_event_id:
        if row.created_by == user_id:
            creds = calendar_credentials(db, user_id)
            if creds is not None:
                google_calendar.delete_event(creds, row.calendar_event_id)
            row.calendar_event_id = None
        else:
            note = (
                f"old reminder {row.from_user} -> {row.to_user} was cancelled; its event stays on "
                f"the Google Calendar of {row.created_by} until they delete it"
            )
    row.status = "cancelled"
    row.cancel_reason = reason
    return note


def outdated_reminder_ids(db: Session, user_id: str, house_id: int, rows: list[Reminder]) -> set[int]:
    """Ids of scheduled reminders whose (from, to, amount) is not a current suggested
    transfer, so a list can show them as out of date. Members only."""
    if not any(r.status == "scheduled" for r in rows):
        return set()
    transfers = houses.house_balances(db, user_id, house_id).transfers
    current = {(t.from_user, t.to_user, t.amount_minor) for t in transfers}
    return {r.id for r in rows if r.status == "scheduled" and _key(r) not in current}


def list_reminders(db: Session, user_id: str, house_id: int, status: str | None = None) -> list[Reminder]:
    houses.get_house(db, user_id, house_id)  # membership check
    if status is not None and status not in REMINDER_STATUSES:
        raise InvalidInput(f"status must be one of {', '.join(REMINDER_STATUSES)}")
    stmt = select(Reminder).where(Reminder.house_id == house_id)
    if status is not None:
        stmt = stmt.where(Reminder.status == status)
    return list(db.scalars(stmt.order_by(Reminder.due_date, Reminder.id)))


def set_reminder_status(
    db: Session, user_id: str, reminder_id: int, status: str, *, house_id: int | None = None
) -> Reminder:
    """status in models.REMINDER_STATUSES. Cancelling also deletes the calendar event.

    Cancelled is final. Only the creator may cancel. If Google is no longer connected the
    reminder is still cancelled (the event cannot be reached); if the Calendar API fails,
    UpstreamError is raised and nothing changes, so the user can retry.
    """
    if status not in REMINDER_STATUSES:
        raise InvalidInput(f"status must be one of {', '.join(REMINDER_STATUSES)}")
    row = db.get(Reminder, reminder_id)
    if row is None or (house_id is not None and row.house_id != house_id):
        raise NotFound(f"reminder {reminder_id} not found")
    try:
        houses.get_house(db, user_id, row.house_id)
    except NotFound:
        raise NotFound(f"reminder {reminder_id} not found") from None
    if row.status == status:
        return row
    if row.status == "cancelled":
        raise InvalidInput("a cancelled reminder cannot be changed; create a new one")
    if status == "cancelled":
        if row.created_by != user_id:
            raise Forbidden("only the person who created a reminder can cancel it")
        _cancel(db, row, user_id, reason="user")
    else:
        row.status = status
    db.commit()
    return row


def _people(db: Session, user_ids: set[str]) -> dict[str, User]:
    if not user_ids:
        return {}
    return {u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids)))}


def _name(people: dict[str, User], user_id: str) -> str:
    user = people.get(user_id)
    return user.display_name if user is not None else user_id


def _summary(row: Reminder, people: dict[str, User]) -> str:
    return (
        f"Kasa: {_name(people, row.from_user)} -> {_name(people, row.to_user)} "
        f"{format_minor(row.amount_minor)} {row.currency}"
    )


def _description(row: Reminder, people: dict[str, User], house_name: str) -> str:
    return (
        f"{_name(people, row.from_user)} pays {_name(people, row.to_user)} "
        f"{format_minor(row.amount_minor)} {row.currency} to settle up in {house_name}.\n"
        f"Ödeme hatırlatması ({house_name}): {_name(people, row.from_user)} -> "
        f"{_name(people, row.to_user)}, {format_minor(row.amount_minor)} {row.currency}.\n"
        "Created by Kasa."
    )
