"""Report agent tool (owner: track REPORT): checked, guarded read-only SQL + chart spec.

`run_report` flow:
1. Static guard (`reports.validate_report_sql`). Unsafe SQL comes back as "rejected".
2. LLM checker (`checker_agent.review_sql`) with the question and the SQL. "revise" comes
   back with the reason so the report agent can fix the query. After MAX_CHECKER_REVISIONS
   revisions in one turn, the next query runs on the static guard alone (`checker` says
   "skipped"). If the checker model fails, it approves with an error (fail-open).
3. Execute with the user-scoped CTEs and build the chart.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext
from sqlalchemy.exc import SQLAlchemyError

from app.agents import checker_agent
from app.agents.tools._context import error, tool_db
from app.config import get_settings
from app.services import reports

# Rows echoed back to the model; the chart still uses every fetched row.
_ROWS_FOR_MODEL = 50
MAX_CHECKER_REVISIONS = 2
# Per-turn bookkeeping. "temp:" state is dropped when the turn ends; the invocation id
# guards against it ever leaking into the next turn.
_STATE_KEY = "temp:report_checker"
NO_CHART = ("", "none", "table")


def _user_message(tool_context: ToolContext) -> str:
    content = getattr(tool_context, "user_content", None)
    parts = content.parts if content and content.parts else []
    return "\n".join(p.text for p in parts if getattr(p, "text", None))


async def _check(question: str, sql: str, canonical: str, tool_context: ToolContext) -> dict[str, Any]:
    state = tool_context.state.get(_STATE_KEY) or {}
    if state.get("invocation") != tool_context.invocation_id:
        state = {"invocation": tool_context.invocation_id, "revisions": 0, "approved": []}
    if canonical in state["approved"]:
        return {"verdict": "approve", "reason": "approved earlier in this turn"}
    if state["revisions"] >= MAX_CHECKER_REVISIONS:
        return {
            "verdict": "skipped",
            "reason": f"checker asked for {state['revisions']} revisions; ran on the static guard only",
        }
    verdict = await checker_agent.review_sql(
        question, sql, user_message=_user_message(tool_context), user_id=tool_context.user_id
    )
    if verdict.verdict == "revise":
        state = {**state, "revisions": state["revisions"] + 1}
    else:
        state = {**state, "approved": [*state["approved"], canonical]}
    tool_context.state[_STATE_KEY] = state
    result = verdict.as_dict()
    result["retries_left"] = MAX_CHECKER_REVISIONS - state["revisions"]
    return result


async def run_report(
    sql: str,
    tool_context: ToolContext,
    question: str = "",
    chart_type: str = "",
    x: str = "",
    y: str = "",
    title: str = "",
) -> dict:
    """Run ONE read-only SELECT over the my_* relations, after a reviewer checks it, and
    optionally chart it.

    Columns ending in _minor are returned converted to decimal strings without the suffix
    (total_minor -> total). Use SUM/COUNT/AVG in SQL; never compute totals yourself.
    status "revise" means the reviewer found a mistake: fix the SQL as it says and call again.
    status "rejected" means the SQL broke a safety rule: rewrite it.

    Args:
      sql: A single SELECT statement over my_expenses, my_expense_items, my_house_shares,
        my_budgets or my_subscriptions.
      question: The user's question in their words, with the time range, e.g.
        "how much did I spend per category this month (2026-10)".
      chart_type: "bar", "line" or "pie"; "table" or empty for no chart.
      x: Result column for the x axis / pie labels (e.g. "category" or "expense_month").
      y: Numeric result column for values (e.g. "total_minor" or "total").
      title: Short chart title.
    """
    chart_type = (chart_type or "").strip().lower()
    try:
        query = reports.validate_report_sql(sql)
    except reports.UnsafeQuery as exc:
        return {"status": "rejected", "error": str(exc)}

    checker = await _check(question, sql, query.sql(comments=False), tool_context)
    if checker["verdict"] == "revise":
        return {
            "status": "revise",
            "reason": checker.get("reason", ""),
            "suggested_fix": checker.get("suggested_fix", ""),
            "retries_left": checker["retries_left"],
        }

    try:
        with tool_db(tool_context) as (db, user_id):
            result = reports.run_report_query(db, user_id, sql, get_settings().report_row_limit)
    except reports.UnsafeQuery as exc:
        return {"status": "rejected", "error": str(exc)}
    except ValueError as exc:
        return error(exc)
    except SQLAlchemyError:  # e.g. a misspelled column; let the model fix the query and retry
        return {"status": "error", "error": "the query failed to execute; check column names"}

    chart = None
    chart_error = None
    if chart_type not in NO_CHART:
        try:
            chart = reports.build_chart(result, chart_type, x, y, title)
        except ValueError as exc:
            chart_error = str(exc)
    response = {
        "status": "ok",
        "columns": result["columns"],
        "rows": result["rows"][:_ROWS_FOR_MODEL],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
        "chart": chart,
        "checker": checker,
    }
    if chart_error:
        response["chart_error"] = chart_error
    return response
