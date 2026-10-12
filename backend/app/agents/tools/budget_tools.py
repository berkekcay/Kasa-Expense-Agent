"""Budget agent tools (owner: track MONEY). Each tool calls a MONEY service and formats the
result for the model. Until the services land they answer "not available yet"."""

from __future__ import annotations

from google.adk.tools import ToolContext

from app.agents.tools._context import not_available


def set_budget(
    limit: str, tool_context: ToolContext, category: str = "", alert_threshold_pct: int = 80
) -> dict:
    """Create or change a monthly budget for the current user.

    Args:
      limit: Monthly limit as a string with '.' decimal separator, e.g. "2500.00".
      category: Category name (e.g. groceries, food, transport); empty for the overall budget.
      alert_threshold_pct: Warn when this percent of the limit is used (1-100).
    """
    return not_available("budgets")


def get_budget_status(tool_context: ToolContext, month: str = "") -> dict:
    """Spent, remaining and percent used for each budget.

    Args:
      month: Any date in the month as YYYY-MM-DD; empty for the current month.
    """
    return not_available("budget status")


def list_subscriptions(tool_context: ToolContext) -> dict:
    """Recurring charges detected from the user's expenses, with the next expected date."""
    return not_available("subscriptions")


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
    return not_available("currency conversion")
