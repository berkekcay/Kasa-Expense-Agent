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


def calendar_credentials(db: Session, user_id: str) -> Credentials | None:
    """The user's Google credentials, or None when Google is not connected (or the
    Google integration is not available on this server)."""
    try:
        return google_oauth.credentials_for_user(db, user_id)
    except NotImplementedError:
        return None
    except DomainError as exc:  # e.g. NotConfigured: no OAuth client or encryption key
        log.info("calendar credentials unavailable for %s: %s", user_id, exc)
        return None


def create_settle_up_reminders(
    db: Session, user_id: str, house_id: int, *, due_date: dt.date, add_to_calendar: bool = True
) -> CreatedReminders:
    """One reminder per current settle-up transfer (`houses.house_balances`). Members only.

    Returns the reminders (existing matching ones included, in transfer order), whether a
    Google account was used, and warnings. Calendar failures do not lose the reminder: it
    is saved with calendar_event_id=None.
    """
    if due_date < clock.today():
        raise InvalidInput("due date is in the past")
    result = houses.house_balances(db, user_id, house_id)
    house = result.house
    if not result.transfers:
        return CreatedReminders(reminders=[], calendar_connected=False, warnings=["everyone is settled up"])

    open_rows = list(
        db.scalars(select(Reminder).where(Reminder.house_id == house.id, Reminder.status == "scheduled"))
    )
    existing = {(r.from_user, r.to_user, r.amount_minor): r for r in open_rows}
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

    warnings: list[str] = []
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
    return CreatedReminders(reminders=reminders, calendar_connected=creds is not None, warnings=warnings)


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
        if row.calendar_event_id:
            creds = calendar_credentials(db, user_id)
            if creds is not None:
                google_calendar.delete_event(creds, row.calendar_event_id)
            row.calendar_event_id = None
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
