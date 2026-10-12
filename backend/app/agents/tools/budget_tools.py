"""Budget agent tools (owner: track MONEY). Each tool calls a MONEY service and returns its
numbers as exact strings, plus a ready-made `summary` line, so the model never computes.
The user always comes from `tool_context.user_id`."""

from __future__ import annotations

import datetime as dt

from google.adk.tools import ToolContext

from app.agents.tools._context import error, tool_db
from app.services import budgets as budget_service
from app.services import clock, fx
from app.services import subscriptions as subscription_service
from app.services.errors import DomainError, InvalidInput
from app.services.money import MoneyError, format_minor, to_minor


def _date(value: str, name: str) -> dt.date | None:
    if not value or not value.strip():
        return None
    try:
        return dt.date.fromisoformat(value.strip())
    except ValueError as exc:
        raise InvalidInput(f"{name} must be YYYY-MM-DD, got {value!r}") from exc


def _status_dict(s: budget_service.BudgetStatus) -> dict:
    b = s.budget
    return {
        "category": b.category or "overall",
        "limit": format_minor(b.limit_minor),
        "spent": format_minor(s.spent_minor),
        "remaining": format_minor(s.remaining_minor),
        "pct_used": s.pct_used,
        "level": s.level,
        "currency": b.currency,
        "summary": (
            f"{b.category or 'overall'}: {fx.format_amount(s.spent_minor)} of "
            f"{fx.format_amount(b.limit_minor)} {b.currency} spent ({s.pct_used}%), "
            f"{fx.format_amount(s.remaining_minor)} {b.currency} left"
        ),
    }


def set_budget(
    limit: str, tool_context: ToolContext, category: str = "", alert_threshold_pct: int = 80
) -> dict:
    """Create or change a monthly budget for the current user.

    Args:
      limit: Monthly limit as a string with '.' decimal separator, e.g. "2500.00".
      category: Category name (e.g. groceries, food, transport, or Turkish like market,
        ulaşım, kira); empty for the overall budget.
      alert_threshold_pct: Warn when this percent of the limit is used (1-100).
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            budget = budget_service.set_budget(
                db,
                user_id,
                category=category or None,
                limit=limit,
                currency=budget_service.base_currency(),
                alert_threshold_pct=alert_threshold_pct,
            )
            statuses = budget_service.budget_status(db, user_id)
            db.commit()
            status = next(s for s in statuses if s.budget.id == budget.id)
            return {
                "status": "saved",
                "category": budget.category or "overall",
                "limit": format_minor(budget.limit_minor),
                "currency": budget.currency,
                "alert_threshold_pct": budget.alert_threshold_pct,
                "this_month": _status_dict(status),
            }
    except (DomainError, MoneyError) as exc:
        return error(exc)


def get_budget_status(tool_context: ToolContext, month: str = "") -> dict:
    """Spent, remaining and percent used for each budget.

    Args:
      month: Any date in the month as YYYY-MM-DD; empty for the current month.
    """
    try:
        day = _date(month, "month")
        with tool_db(tool_context) as (db, user_id):
            statuses = budget_service.budget_status(db, user_id, day)
            db.commit()
    except DomainError as exc:
        return error(exc)
    if not statuses:
        return {"status": "no_budgets", "message": "No budgets yet. Use set_budget to create one."}
    return {
        "status": "ok",
        "month": statuses[0].month.strftime("%Y-%m"),
        "budgets": [_status_dict(s) for s in statuses],
    }


def list_subscriptions(tool_context: ToolContext, refresh: bool = True) -> dict:
    """Recurring charges detected from the user's expenses, with the next expected date.

    Args:
      refresh: True scans the expenses again first (recommended); False lists what was
        found last time.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            if refresh:
                rows = subscription_service.detect_subscriptions(db, user_id)
            else:
                rows = subscription_service.list_subscriptions(db, user_id)
            subs = [
                {
                    "id": s.id,
                    "name": s.display_name,
                    "amount": format_minor(s.amount_minor),
                    "currency": s.currency,
                    "period": s.period,
                    "last_charge_date": s.last_charge_date.isoformat(),
                    "next_expected_date": s.next_expected_date.isoformat(),
                }
                for s in rows
            ]
    except DomainError as exc:
        return error(exc)
    if not subs:
        return {"status": "none", "message": "No recurring charges found in the expenses."}
    return {"status": "ok", "subscriptions": subs}


def convert_currency(
    amount: str, from_currency: str, tool_context: ToolContext, to_currency: str = "TRY", on_date: str = ""
) -> dict:
    """Convert an amount with the TCMB exchange rate (computed by code, exactly).

    Args:
      amount: Amount as a string with '.' decimal separator, e.g. "50".
      from_currency: ISO code, e.g. EUR, USD.
      to_currency: ISO code, default TRY.
      on_date: YYYY-MM-DD; empty for today.
    """
    try:
        amount_minor = to_minor(amount)
        if amount_minor <= 0:
            raise InvalidInput("amount must be positive")
        on = _date(on_date, "on_date") or clock.today()
        with tool_db(tool_context) as (db, _user_id):
            result = fx.conversion(db, amount_minor, from_currency, to_currency or "TRY", on)
            db.commit()
    except (DomainError, MoneyError) as exc:
        return error(exc)
    text = (
        f"{fx.format_amount(result.amount_minor)} {result.from_currency} = "
        f"{fx.format_amount(result.converted_minor)} {result.to_currency} "
        f"(TCMB rate {fx.format_rate(result.rate)}, {result.rate_date.isoformat()})"
    )
    return {
        "status": "ok",
        "amount": format_minor(result.amount_minor),
        "from_currency": result.from_currency,
        "converted": format_minor(result.converted_minor),
        "to_currency": result.to_currency,
        "rate": fx.format_rate(result.rate),
        "rate_date": result.rate_date.isoformat(),
        "summary": text,
    }
