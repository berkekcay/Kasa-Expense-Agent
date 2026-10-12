"""House agent tools (owner: track HOUSE): shared expenses, splits, balances, settle-up.

Track HOUSE adds: a tool for percent / exact / per-item splits (services.houses.add_split_expense)
and one for settle-up reminders (services.reminders), then lists them in house_agent.py.
"""

from __future__ import annotations

import datetime as dt

from google.adk.tools import ToolContext

from app.agents.tools._context import error, tool_db
from app.services import houses as house_service
from app.services.errors import DomainError
from app.services.expenses import ExpenseInput
from app.services.money import format_minor


def list_my_houses(tool_context: ToolContext) -> dict:
    """List the houses (shared flats) the current user belongs to, with member ids."""
    with tool_db(tool_context) as (db, user_id):
        return {
            "houses": [
                {
                    "id": h.id,
                    "name": h.name,
                    "currency": h.currency,
                    "members": [{"user_id": m.user_id, "name": m.user.display_name} for m in h.members],
                }
                for h in house_service.list_houses(db, user_id)
            ]
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
      paid_by: Member user_id who paid; empty means the current user.
      split_between: Member user_ids sharing the cost; empty means all members.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            expense = house_service.add_equal_split_expense(
                db,
                user_id,
                house_id,
                ExpenseInput(
                    merchant=merchant,
                    total=total,
                    expense_date=dt.date.fromisoformat(expense_date) if expense_date else None,
                    currency=None,
                ),
                paid_by=paid_by or None,
                split_between=split_between or None,
            )
            return {
                "status": "saved",
                "expense_id": expense.id,
                "total": format_minor(expense.total_minor),
                "currency": expense.currency,
                "paid_by": expense.owner_id,
                "shares": {s.user_id: format_minor(s.amount_minor) for s in expense.shares},
            }
    except (DomainError, ValueError) as exc:
        return error(exc)


def get_house_balances(house_id: int, tool_context: ToolContext) -> dict:
    """Net balance per member (positive = is owed money) and the transfers that settle up.

    Args:
      house_id: Id from list_my_houses.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
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

    Args:
      house_id: Id from list_my_houses.
      from_user: Member user_id who paid the money back.
      to_user: Member user_id who received it.
      amount: Amount as a string with '.' decimal separator, e.g. "43.33".
      note: Optional note, e.g. "IBAN transfer".
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            row = house_service.record_settlement(
                db, user_id, house_id, from_user=from_user, to_user=to_user, amount=amount, note=note or None
            )
            balances = house_service.house_balances(db, user_id, house_id)
            return {
                "status": "saved",
                "payment_id": row.id,
                "from": row.from_user,
                "to": row.to_user,
                "amount": format_minor(row.amount_minor),
                "currency": row.currency,
                "settle_up_now": [
                    {"from": t.from_user, "to": t.to_user, "amount": format_minor(t.amount_minor)}
                    for t in balances.transfers
                ],
            }
    except (DomainError, ValueError) as exc:
        return error(exc)
