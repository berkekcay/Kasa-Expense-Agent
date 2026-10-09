"""Report agent tool (owner: Agent dev #3): guarded read-only SQL + chart spec."""

from __future__ import annotations

from google.adk.tools import ToolContext
from sqlalchemy.exc import SQLAlchemyError

from app.agents.tools._context import error, tool_db
from app.config import get_settings
from app.services import reports

# Rows echoed back to the model; the chart still uses every fetched row.
_ROWS_FOR_MODEL = 50


def run_report(
    sql: str,
    tool_context: ToolContext,
    chart_type: str = "",
    x: str = "",
    y: str = "",
    title: str = "",
) -> dict:
    """Run ONE read-only SELECT over my_expenses / my_expense_items and optionally chart it.

    Columns ending in _minor are returned converted to decimal strings without the suffix
    (total_minor -> total). Use SUM/COUNT/AVG in SQL; never compute totals yourself.

    Args:
      sql: A single SELECT statement. Only my_expenses and my_expense_items may be used.
      chart_type: "bar", "line" or "pie"; empty for no chart.
      x: Result column for the x axis / pie labels (e.g. "category" or "expense_month").
      y: Numeric result column for values (e.g. "total_minor" or "total").
      title: Short chart title.
    """
    try:
        with tool_db(tool_context) as (db, user_id):
            result = reports.run_report_query(db, user_id, sql, get_settings().report_row_limit)
        chart = reports.build_chart(result, chart_type, x, y, title) if chart_type else None
    except reports.UnsafeQuery as exc:
        return {"status": "rejected", "error": str(exc)}
    except ValueError as exc:
        return error(exc)
    except SQLAlchemyError:  # e.g. a misspelled column; let the model fix the query and retry
        return {"status": "error", "error": "the query failed to execute; check column names"}
    return {
        "status": "ok",
        "columns": result["columns"],
        "rows": result["rows"][:_ROWS_FOR_MODEL],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
        "chart": chart,
    }
