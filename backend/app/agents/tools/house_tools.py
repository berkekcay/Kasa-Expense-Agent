"""House agent tools (owner: track HOUSE): shared expenses, splits, balances, payments,
settle-up reminders, invite links.

The model passes who and how much exactly as the user said it; code computes every share.
People can be given as member user ids or display names ("Ayşe"); "me"/"ben" (or an empty
value where allowed) means the current user, who always comes from `tool_context`.
Splits by percent or exact amount take a list of {user, value} pairs rather than a free
JSON object, because Gemini function declarations cannot describe open-ended objects.
"""

from __future__ import annotations

import datetime as dt

from google.adk.tools import ToolContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.agents.tools._context import error, tool_db
from app.db.models import Expense, House
from app.services import clock
from app.services import houses as house_service
from app.services import invites as invite_service
from app.services import reminders as reminder_service
from app.services.errors import DomainError, InvalidInput
from app.services.expenses import ExpenseInput, ItemInput
from app.services.money import format_minor

SELF_WORDS = {"me", "myself", "i", "ben", "bana", "beni", "benim", "kendim"}


class _ToolArg(BaseModel):
    # Models sometimes send 50 instead of "50"; keep it exact as a string.
    model_config = ConfigDict(coerce_numbers_to_str=True)


class PercentShare(_ToolArg):
    user: str  # member user_id or name, "me" for the current user
    percent: str  # as the user said it, e.g. "50" or "33.33"


class AmountShare(_ToolArg):
    user: str  # member user_id or name, "me" for the current user
    amount: str  # e.g. "250.00"


class SplitItem(_ToolArg):
    description: str
    amount: str  # line total as printed, e.g. "60.00"
    assignees: list[str] = []  # who shares this line; empty = everyone in the split
    quantity: str = "1"


def _fold(text: str) -> str:
    return text.strip().replace("İ", "i").casefold()


def _resolve(house: House, ref: str, user_id: str) -> str:
    """Member user id for a model-supplied reference (id, display name or "me")."""
    ref = (ref or "").strip()
    if not ref or _fold(ref) in SELF_WORDS:
        return user_id
    ids = house_service.member_ids(house)
    if ref in ids:
        return ref
    folded = _fold(ref)
    by_id = [m.user_id for m in house.members if _fold(m.user_id) == folded]
    by_name = [m.user_id for m in house.members if _fold(m.user.display_name) == folded]
    matches = list(dict.fromkeys(by_id + by_name))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise InvalidInput(f"{ref!r} is not a member of {house.name}; call list_my_houses for member ids")
    raise InvalidInput(f"{ref!r} matches several members ({', '.join(matches)}); use the user id")


def _resolve_all(house: House, refs: list[str] | None, user_id: str) -> list[str] | None:
    if not refs:
        return None
    return [_resolve(house, r, user_id) for r in refs]


def _unique_map(pairs: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for user, value in pairs:
        if user in result:
            raise InvalidInput(f"{user} appears twice in the split")
        result[user] = value
    return result


def _text(value: object) -> str:
    """Amounts arrive as strings, but a model may send a JSON number; keep it exact."""
    return value if isinstance(value, str) else str(value)


def _date(expense_date: str) -> dt.date | None:
    return dt.date.fromisoformat(expense_date) if expense_date else None


def _saved(expense: Expense, warnings: list[str]) -> dict:
    result = {
        "status": "saved",
        "expense_id": expense.id,
        "merchant": expense.merchant,
        "split_type": expense.split_type,
        "total": format_minor(expense.total_minor),
        "currency": expense.currency,
        "paid_by": expense.owner_id,
        "shares": {s.user_id: format_minor(s.amount_minor) for s in expense.shares},
        "warnings": warnings,
    }
    if expense.split_type == "items":
        result["items"] = [
            {
                "description": i.description,
                "amount": format_minor(i.amount_minor),
                "shared_by": [a.user_id for a in i.assignees],
            }
            for i in expense.items
        ]
    return result


def _pick_house(db: Session, user_id: str, house_id: int) -> int:
    """The house the tool should act on. Models sometimes pass 0 or a guess instead of an id
    from list_my_houses; when the user is in exactly one house, that house is meant."""
    houses = house_service.list_houses(db, user_id)
    if any(h.id == house_id for h in houses):
        return house_id
    if len(houses) == 1:
        return houses[0].id
    if not houses:
        raise InvalidInput("you are not in any house yet; create one on the House page")
    names = ", ".join(f"{h.id}: {h.name}" for h in houses)
    raise InvalidInput(f"which house? use one of these ids: {names}")


def _transfers(db: Session, user_id: str, house_id: int) -> list[dict]:
    result = house_service.house_balances(db, user_id, house_id)
    return [
        {"from": t.from_user, "to": t.to_user, "amount": format_minor(t.amount_minor)}
        for t in result.transfers
    ]


def list_my_houses(tool_context: ToolContext) -> dict:
    """List the houses (shared flats) the current user belongs to, with member ids and names.

    `current_user_id` is the person you are talking to ("me", "ben").
    """
    with tool_db(tool_context) as (db, user_id):
        return {
            "current_user_id": user_id,
            "houses": [
                {
                    "id": h.id,
                    "name": h.name,
                    "currency": h.currency,
                    "members": [{"user_id": m.user_id, "name": m.user.display_name} for m in h.members],
                }
                for h in house_service.list_houses(db, user_id)
            ],
        }


def add_house_expense_equal_split(
    house_id: int,
    merchant: str,
    total: str,
    tool_context: ToolContext,
    expense_date: str = "",
    paid_by: str = "",
    split_between: list[str] | None = None,
) -> dict:
    """Record a shared house expense and split it equally. The split is computed by code.

    Args:
      house_id: Id from list_my_houses.
      merchant: What/where was bought, e.g. "Electricity bill".
      total: Amount as a string with '.' decimal separator, e.g. "640.00".
      expense_date: YYYY-MM-DD, empty for today.
      paid_by: Member user_id or name who paid; empty means the current user.
      split_between: Member user_ids or names sharing the cost; empty means all members.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house = house_service.get_house(db, user_id, house_id)
            expense, warnings = house_service.add_split_expense(
                db,
                user_id,
                house_id,
                ExpenseInput(
                    merchant=merchant, total=_text(total), expense_date=_date(expense_date), currency=None
                ),
                split_type="equal",
                paid_by=_resolve(house, paid_by, user_id),
                participants=_resolve_all(house, split_between, user_id),
            )
            return _saved(expense, warnings)
    except (DomainError, ValueError) as exc:
        return error(exc)


def add_house_expense_percent_split(
    house_id: int,
    merchant: str,
    total: str,
    percents: list[PercentShare],
    tool_context: ToolContext,
    expense_date: str = "",
    paid_by: str = "",
) -> dict:
    """Record a shared house expense split by percentages. Code computes every amount.

    Pass the percentages exactly as the user said them; never turn them into amounts.
    Example: "600 TL, 50% Ali, 30% Ayşe, 20% me" ->
      total="600", percents=[{"user": "ali", "percent": "50"},
                             {"user": "ayse", "percent": "30"},
                             {"user": "me", "percent": "20"}]

    Args:
      house_id: Id from list_my_houses.
      merchant: What/where was bought, e.g. "Electricity bill".
      total: Amount as a string with '.' decimal separator, e.g. "600.00".
      percents: One entry per person: user (member user_id or name, "me" for the current
        user) and percent as a string, e.g. "33.33". They must add up to 100. Only these
        people share the cost.
      expense_date: YYYY-MM-DD, empty for today.
      paid_by: Member user_id or name who paid; empty means the current user.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house = house_service.get_house(db, user_id, house_id)
            mapping = _unique_map([(_resolve(house, p.user, user_id), p.percent) for p in percents])
            expense, warnings = house_service.add_split_expense(
                db,
                user_id,
                house_id,
                ExpenseInput(
                    merchant=merchant, total=_text(total), expense_date=_date(expense_date), currency=None
                ),
                split_type="percent",
                paid_by=_resolve(house, paid_by, user_id),
                percents=mapping,
            )
            return _saved(expense, warnings)
    except (DomainError, ValueError) as exc:
        return error(exc)


def add_house_expense_exact_split(
    house_id: int,
    merchant: str,
    total: str,
    amounts: list[AmountShare],
    tool_context: ToolContext,
    expense_date: str = "",
    paid_by: str = "",
) -> dict:
    """Record a shared house expense where each person's amount is given exactly.

    Use only when the user states every person's amount. Copy the amounts as said; the
    tool checks that they add up to the total and reports any difference.

    Args:
      house_id: Id from list_my_houses.
      merchant: What/where was bought.
      total: Grand total as a string with '.' decimal separator, e.g. "300.00".
      amounts: One entry per person: user (member user_id or name, "me" for the current
        user) and amount as a string, e.g. "120.00".
      expense_date: YYYY-MM-DD, empty for today.
      paid_by: Member user_id or name who paid; empty means the current user.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house = house_service.get_house(db, user_id, house_id)
            mapping = _unique_map([(_resolve(house, a.user, user_id), a.amount) for a in amounts])
            expense, warnings = house_service.add_split_expense(
                db,
                user_id,
                house_id,
                ExpenseInput(
                    merchant=merchant, total=_text(total), expense_date=_date(expense_date), currency=None
                ),
                split_type="exact",
                paid_by=_resolve(house, paid_by, user_id),
                exact_amounts=mapping,
            )
            return _saved(expense, warnings)
    except (DomainError, ValueError) as exc:
        return error(exc)


def add_house_expense_item_split(
    house_id: int,
    merchant: str,
    total: str,
    items: list[SplitItem],
    tool_context: ToolContext,
    expense_date: str = "",
    paid_by: str = "",
    participants: list[str] | None = None,
) -> dict:
    """Record a shared house expense split per item (who had what). Code computes shares.

    Each line is shared equally by its assignees; a line with no assignees is shared by
    everyone in `participants`. If the lines do not add up to the total (tax, tip,
    discount), the tool spreads the difference fairly. Example: "cheese 60 for Ali, bread
    40 for everyone, total 110" -> items=[{"description": "cheese", "amount": "60",
    "assignees": ["ali"]}, {"description": "bread", "amount": "40", "assignees": []}].

    Args:
      house_id: Id from list_my_houses.
      merchant: Store or what was bought.
      total: Grand total as a string with '.' decimal separator.
      items: Lines with description, amount (string, as printed) and assignees (member
        user_ids or names, "me" for the current user).
      expense_date: YYYY-MM-DD, empty for today.
      paid_by: Member user_id or name who paid; empty means the current user.
      participants: Who shares unassigned lines; empty means all members.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house = house_service.get_house(db, user_id, house_id)
            assignees = [_resolve_all(house, i.assignees, user_id) or [] for i in items]
            expense, warnings = house_service.add_split_expense(
                db,
                user_id,
                house_id,
                ExpenseInput(
                    merchant=merchant,
                    total=_text(total),
                    expense_date=_date(expense_date),
                    currency=None,
                    items=[ItemInput(i.description, i.amount, i.quantity or "1") for i in items],
                ),
                split_type="items",
                paid_by=_resolve(house, paid_by, user_id),
                participants=_resolve_all(house, participants, user_id),
                item_assignees=assignees,
            )
            return _saved(expense, warnings)
    except (DomainError, ValueError) as exc:
        return error(exc)


def get_house_balances(house_id: int, tool_context: ToolContext) -> dict:
    """Net balance per member (positive = is owed money) and the transfers that settle up.
    Recorded payments are already included.

    Args:
      house_id: Id from list_my_houses.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            result = house_service.house_balances(db, user_id, house_id)
    except DomainError as exc:
        return error(exc)
    return {
        "currency": result.house.currency,
        "balances": {u: format_minor(b) for u, b in result.balances.items()},
        "settle_up": [
            {"from": t.from_user, "to": t.to_user, "amount": format_minor(t.amount_minor)}
            for t in result.transfers
        ],
    }


def record_payment(
    house_id: int,
    from_user: str,
    to_user: str,
    amount: str,
    tool_context: ToolContext,
    note: str = "",
) -> dict:
    """Record that one flatmate paid another back, which reduces what they owe.

    "Ayşe paid me 200" -> from_user="ayse", to_user="me", amount="200". A payment larger
    than the open debt is refused; tell the user the limit from the error and ask.

    Args:
      house_id: Id from list_my_houses.
      from_user: Member user_id or name who paid the money back ("me" for the current user).
      to_user: Member user_id or name who received it ("me" for the current user).
      amount: Amount as a string with '.' decimal separator, e.g. "43.33".
      note: Optional note, e.g. "IBAN transfer".
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house = house_service.get_house(db, user_id, house_id)
            row = house_service.record_settlement(
                db,
                user_id,
                house_id,
                from_user=_resolve(house, from_user, user_id),
                to_user=_resolve(house, to_user, user_id),
                amount=_text(amount),
                note=note or None,
            )
            return {
                "status": "saved",
                "payment_id": row.id,
                "from": row.from_user,
                "to": row.to_user,
                "amount": format_minor(row.amount_minor),
                "currency": row.currency,
                "settle_up_now": _transfers(db, user_id, house_id),
            }
    except (DomainError, ValueError) as exc:
        return error(exc)


def undo_payment(house_id: int, payment_id: int, tool_context: ToolContext) -> dict:
    """Delete a payment recorded by mistake. Only the person who recorded it can do this.

    Args:
      house_id: Id from list_my_houses.
      payment_id: payment_id returned by record_payment.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            house_service.delete_settlement(db, user_id, house_id, payment_id)
            return {
                "status": "deleted",
                "payment_id": payment_id,
                "settle_up_now": _transfers(db, user_id, house_id),
            }
    except DomainError as exc:
        return error(exc)


def create_settle_up_reminders(
    house_id: int,
    tool_context: ToolContext,
    due_date: str = "",
    add_to_calendar: bool = True,
) -> dict:
    """Create one reminder per settle-up transfer of the house ("remind them to pay by
    Friday"). With a connected Google account each becomes a Google Calendar event and the
    flatmates get an invitation email.

    Args:
      house_id: Id from list_my_houses.
      due_date: YYYY-MM-DD; empty means one week from today.
      add_to_calendar: False to keep the reminders in Kasa only.
    """
    try:
        due = dt.date.fromisoformat(due_date) if due_date else clock.today() + dt.timedelta(days=7)
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            result = reminder_service.create_settle_up_reminders(
                db, user_id, house_id, due_date=due, add_to_calendar=add_to_calendar
            )
            return {
                "status": "saved" if result.reminders else "nothing_to_remind",
                "due_date": due.isoformat(),
                "calendar_connected": result.calendar_connected,
                "reminders": [
                    {
                        "reminder_id": r.id,
                        "from": r.from_user,
                        "to": r.to_user,
                        "amount": format_minor(r.amount_minor),
                        "currency": r.currency,
                        "on_calendar": r.calendar_event_id is not None,
                    }
                    for r in result.reminders
                ],
                "outdated_reminders_cancelled": len(result.cancelled),
                "warnings": result.warnings,
            }
    except (DomainError, ValueError) as exc:
        return error(exc)


def create_house_invite(house_id: int, tool_context: ToolContext) -> dict:
    """Create an invite link for the house ("ev için davet linki", "Ali'yi eve davet et").
    Whoever opens the link and accepts joins the house. Valid 7 days, for up to 10 people.

    Args:
      house_id: Id from list_my_houses.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            house_id = _pick_house(db, user_id, house_id)
            invite = invite_service.create_invite(db, user_id, house_id)
            return {
                "status": "created",
                "house": invite.house_name,
                "url": invite_service.invite_url(invite.code),
                "code": invite.code,
                "expires_at": invite.expires_at.replace(tzinfo=dt.UTC)
                .astimezone(clock.KASA_TZ)
                .isoformat(timespec="minutes"),
                "max_uses": invite.max_uses,
            }
    except DomainError as exc:
        return error(exc)
