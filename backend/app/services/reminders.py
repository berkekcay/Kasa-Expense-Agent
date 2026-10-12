"""Settle-up reminders, optionally mirrored to Google Calendar (owner: track HOUSE).

A reminder is "from_user should pay to_user amount by due_date". They are created from the
current settle-up transfers of a house. When the acting user has connected Google
(`integrations.google_oauth.credentials_for_user`), an all-day event is added to their
calendar with the debtor invited by email (if `users.email` is known).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.db.models import Reminder


def create_settle_up_reminders(
    db: Session, user_id: str, house_id: int, *, due_date: dt.date, add_to_calendar: bool = True
) -> list[Reminder]:
    """One reminder per current settle-up transfer (`houses.house_balances`). Members only.
    Calendar failures must not lose the reminder: save it with calendar_event_id=None."""
    raise NotImplementedError("create_settle_up_reminders: track HOUSE")


def list_reminders(db: Session, user_id: str, house_id: int) -> list[Reminder]:
    raise NotImplementedError("list_reminders: track HOUSE")


def set_reminder_status(db: Session, user_id: str, reminder_id: int, status: str) -> Reminder:
    """status in models.REMINDER_STATUSES. Cancelling also deletes the calendar event."""
    raise NotImplementedError("set_reminder_status: track HOUSE")
