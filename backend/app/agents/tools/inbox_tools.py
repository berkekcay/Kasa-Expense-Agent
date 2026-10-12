"""Inbox and parser tools (owner: track INGEST).

Chat tools (inbox agent) act on the review queue. Parser tools (email-parse and
statement-parse runners) do not touch the DB: they validate what the model extracted and
return it, and the caller (`gmail_sync`, `statements`) reads it with
`AgentRun.last_tool_result("submit_parsed_expense" | "mark_not_expense" | "submit_statement_lines")`.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict

from google.adk.tools import ToolContext
from pydantic import BaseModel

from app.agents.tools._context import not_available
from app.services.inbox import ParsedExpense, ParsedItem
from app.services.money import MoneyError, format_minor, normalize_currency, to_minor
from app.services.statements import StatementLine


class ParsedLine(BaseModel):
    description: str
    amount: str
    quantity: str = "1"


class StatementLineArg(BaseModel):
    posted_on: str
    description: str
    amount: str
    currency: str = "TRY"


# --- chat tools (inbox agent) --------------------------------------------------------------


def list_inbox(tool_context: ToolContext, status: str = "pending") -> dict:
    """Possible expenses found in Gmail or statements, waiting for review.

    Args:
      status: pending (default), approved, rejected, failed or ignored.
    """
    return not_available("the inbox")


def approve_inbox_item(item_id: int, tool_context: ToolContext) -> dict:
    """Save an inbox item as an expense. Only when the user asked for this item.

    Args:
      item_id: Id from list_inbox.
    """
    return not_available("the inbox")


def reject_inbox_item(item_id: int, tool_context: ToolContext) -> dict:
    """Mark an inbox item as not an expense. Only when the user asked for this item.

    Args:
      item_id: Id from list_inbox.
    """
    return not_available("the inbox")


def gmail_connection_status(tool_context: ToolContext) -> dict:
    """Whether the user's Gmail is connected and when it was last synced."""
    return not_available("Gmail connection")


# --- parser tools (email-parse / statement-parse runners) -----------------------------------


def submit_parsed_expense(
    merchant: str,
    total: str,
    tool_context: ToolContext,
    currency: str = "TRY",
    expense_date: str = "",
    category: str = "",
    items: list[ParsedLine] | None = None,
) -> dict:
    """Submit the one purchase found in this email. Copy amounts exactly as printed.

    Args:
      merchant: Seller name, e.g. "Trendyol" or "Turkcell".
      total: Grand total, digits with '.' as decimal separator, e.g. "349.90".
      currency: ISO 4217 code; TRY for "TL" or "₺".
      expense_date: Purchase date as YYYY-MM-DD; empty if not shown.
      category: One category name from the instructions.
      items: Line items if listed (description, amount, quantity).
    """
    try:
        to_minor(total)
        lines = [ParsedItem(i.description.strip()[:200], i.amount, i.quantity or "1") for i in items or []]
        for line in lines:
            to_minor(line.amount)
        parsed = ParsedExpense(
            merchant=merchant.strip()[:200],
            total=format_minor(to_minor(total)),
            currency=normalize_currency(currency),
            expense_date=dt.date.fromisoformat(expense_date) if expense_date else None,
            category=category or None,
            items=lines,
        )
        if not parsed.merchant:
            raise ValueError("merchant is required")
    except (MoneyError, ValueError) as exc:
        return {"status": "error", "error": str(exc)}
    return {"status": "parsed", "expense": json_safe(parsed)}


def mark_not_expense(reason: str, tool_context: ToolContext) -> dict:
    """Say this email is not a purchase (newsletter, promotion, shipping update, refund).

    Args:
      reason: A few words, e.g. "newsletter".
    """
    return {"status": "not_expense", "reason": reason.strip()[:200]}


def submit_statement_lines(lines: list[StatementLineArg], tool_context: ToolContext) -> dict:
    """Submit every spending line of the statement.

    Args:
      lines: Each with posted_on (YYYY-MM-DD), description, amount (positive, '.' decimal
        separator) and currency (default TRY).
    """
    accepted: list[dict] = []
    rejected: list[str] = []
    for i, line in enumerate(lines):
        try:
            minor = to_minor(line.amount)
            if minor <= 0:
                raise ValueError("amount must be positive")
            parsed = StatementLine(
                posted_on=dt.date.fromisoformat(line.posted_on),
                description=" ".join(line.description.split())[:300],
                amount=format_minor(minor),
                currency=normalize_currency(line.currency),
            )
        except (MoneyError, ValueError) as exc:
            rejected.append(f"line {i + 1}: {exc}")
            continue
        accepted.append({**asdict(parsed), "posted_on": parsed.posted_on.isoformat()})
    return {"status": "parsed", "lines": accepted, "rejected": rejected}


def json_safe(parsed: ParsedExpense) -> dict:
    data = asdict(parsed)
    data["expense_date"] = parsed.expense_date.isoformat() if parsed.expense_date else None
    return data
