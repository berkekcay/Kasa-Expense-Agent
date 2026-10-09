"""Receipt agent tools (owner: Agent dev #1). The model extracts fields; code does the math."""

from __future__ import annotations

import datetime as dt

from google.adk.tools import ToolContext
from pydantic import BaseModel

from app.agents.tools._context import error, tool_db
from app.services import expenses as expense_service
from app.services.errors import DomainError
from app.services.money import format_minor


class ReceiptLine(BaseModel):
    description: str
    amount: str
    quantity: str = "1"


def save_expense(
    merchant: str,
    total: str,
    tool_context: ToolContext,
    expense_date: str = "",
    currency: str = "TRY",
    category: str = "",
    items: list[ReceiptLine] | None = None,
    from_receipt: bool = True,
) -> dict:
    """Save one expense for the current user (from a receipt image or a typed description).

    Copy amounts exactly as printed; do not compute anything yourself.

    Args:
      merchant: Store or vendor name as printed.
      total: Grand total as printed, digits with '.' as decimal separator, e.g. "245.90".
      expense_date: Purchase date as YYYY-MM-DD. Empty if unknown (today is used).
      currency: ISO 4217 code, e.g. TRY, EUR, USD. Use TRY for "TL" or "₺".
      category: One of groceries, food, transport, bills, rent, health, entertainment, other.
      items: Line items as printed (description, amount as string, quantity as string).
      from_receipt: True when the data came from a receipt image.
    """
    try:
        parsed_date = dt.date.fromisoformat(expense_date) if expense_date else None
        data = expense_service.ExpenseInput(
            merchant=merchant,
            total=total,
            expense_date=parsed_date,
            currency=currency or "TRY",
            category=category or None,
            items=[expense_service.ItemInput(i.description, i.amount, i.quantity) for i in items or []],
        )
        with tool_db(tool_context) as (db, user_id):
            expense = expense_service.create_expense(
                db, user_id, data, source="receipt" if from_receipt else "manual"
            )
    except (DomainError, ValueError) as exc:
        return error(exc)

    warnings = []
    if expense.items:
        items_total = expense_service.items_sum_minor(expense)
        if items_total != expense.total_minor:
            warnings.append(
                f"line items add up to {format_minor(items_total)} but the total is "
                f"{format_minor(expense.total_minor)} (discounts, tax or a misread line?)"
            )
    return {
        "status": "saved",
        "expense_id": expense.id,
        "merchant": expense.merchant,
        "date": expense.expense_date.isoformat(),
        "total": format_minor(expense.total_minor),
        "currency": expense.currency,
        "item_count": len(expense.items),
        "warnings": warnings,
    }


def list_recent_expenses(tool_context: ToolContext, limit: int = 10) -> dict:
    """List the current user's most recent expenses (newest first).

    Args:
      limit: How many expenses to return (max 50).
    """
    with tool_db(tool_context) as (db, user_id):
        rows = expense_service.list_expenses(db, user_id, limit=max(1, min(limit, 50)))
        return {
            "expenses": [
                {
                    "id": e.id,
                    "merchant": e.merchant,
                    "date": e.expense_date.isoformat(),
                    "total": format_minor(e.total_minor),
                    "currency": e.currency,
                    "category": e.category,
                }
                for e in rows
            ]
        }
