"""File agent tools (owner: track REPORT): read, analyse and chart an Excel/CSV file the user
attached in the chat, and prepare its rows as expenses for the user to confirm.

The file stays in `services.sheets` memory for this user; tools look it up by `file_id`
with the acting user from `tool_context`, so another user's file id is simply not found.
Nothing here writes to the database: `prepare_expense_import` only returns a preview and a
draft id, and the user confirms it in the chat UI (it then lands in the inbox).
"""

from __future__ import annotations

from google.adk.tools import ToolContext

from app.agents.tools._context import error
from app.services import reports, sheets
from app.services.errors import DomainError

NO_CHART = ("", "none")


def describe_file(file_id: str, tool_context: ToolContext, sheet: str = "") -> dict:
    """Columns of one sheet with their type (number, date, text), how many cells are
    filled, examples, and min/max/sum or first/last date or the most common values.
    Call this first for a new file.

    Args:
      file_id: The id from the attached files list.
      sheet: Sheet name; empty for the first sheet.
    """
    try:
        upload = sheets.get_upload(tool_context.user_id, file_id)
        return {"status": "ok", **sheets.describe(upload, sheet)}
    except DomainError as exc:
        return error(exc)


def read_rows(
    file_id: str, tool_context: ToolContext, sheet: str = "", offset: int = 0, limit: int = 20
) -> dict:
    """A page of rows as they are in the file (at most 50). Use `query_file` for totals,
    counts and rankings instead of reading every row.

    Args:
      file_id: The id from the attached files list.
      sheet: Sheet name; empty for the first sheet.
      offset: First row to return (0 based).
      limit: How many rows (1 to 50).
    """
    try:
        upload = sheets.get_upload(tool_context.user_id, file_id)
        return {"status": "ok", **sheets.rows(upload, sheet, offset, limit)}
    except DomainError as exc:
        return error(exc)


def query_file(
    file_id: str,
    sql: str,
    tool_context: ToolContext,
    sheet: str = "",
    chart_type: str = "",
    x: str = "",
    y: str = "",
    title: str = "",
) -> dict:
    """Run ONE SQLite SELECT over the sheet, which is the table `data`, and optionally chart
    the result. Column names are exactly the header names; wrap them in double quotes
    ("Açıklama", "Islem Tarihi"). Date columns are ISO text (use strftime('%Y-%m', "Tarih")
    for months); number columns are REAL (SUM, AVG, MIN, MAX, ROUND work). Aggregate in SQL;
    never add numbers yourself.

    Args:
      file_id: The id from the attached files list.
      sql: One SELECT over `data`, e.g. SELECT "Kategori", SUM("Tutar") AS total FROM data
        GROUP BY 1 ORDER BY total DESC.
      sheet: Sheet name; empty for the first sheet.
      chart_type: "bar", "line" or "pie" for a chart, "table" to show rows as a table, empty
        for none.
      x: Result column for the x axis or pie labels.
      y: Numeric result column for the values.
      title: Short chart title in the user's language.
    """
    chart_type = (chart_type or "").strip().lower()
    try:
        upload = sheets.get_upload(tool_context.user_id, file_id)
        result = sheets.query(upload, sql, sheet)
    except DomainError as exc:
        return error(exc)
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
        "rows": result["rows"][:50],
        "row_count": result["row_count"],
        "truncated": result["truncated"],
        "chart": chart,
    }
    if chart_error:
        response["chart_error"] = chart_error
    return response


def prepare_expense_import(
    file_id: str,
    date_column: str,
    description_column: str,
    amount_column: str,
    tool_context: ToolContext,
    sheet: str = "",
    currency_column: str = "",
    currency: str = "TRY",
    spending_sign: str = "auto",
) -> dict:
    """Prepare the file's spending rows as expenses WITHOUT saving them. The user sees a
    preview card with a button and confirms there; confirmed rows go to their inbox.
    Call it when the user asks to add, import or save the file's expenses. Pick the columns
    from `describe_file`.

    Args:
      file_id: The id from the attached files list.
      date_column: Column with the transaction date.
      description_column: Column with the merchant or description.
      amount_column: Column with the amount.
      sheet: Sheet name; empty for the first sheet.
      currency_column: Column with a currency code, if the file has one.
      currency: Currency when there is no currency column (TRY for TL).
      spending_sign: "negative" when spending is written as negative amounts (bank style),
        "positive" when spending is positive (card statements, own lists), "auto" to pick
        the sign most rows have.
    """
    try:
        upload = sheets.get_upload(tool_context.user_id, file_id)
        _draft, preview = sheets.prepare_import(
            upload,
            date_column=date_column,
            description_column=description_column,
            amount_column=amount_column,
            sheet_name=sheet,
            currency_column=currency_column,
            currency=currency,
            spending_sign=spending_sign,
        )
        return preview
    except DomainError as exc:
        return error(exc)
