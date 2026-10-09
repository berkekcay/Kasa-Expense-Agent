"""Guarded read-only SQL for the Report agent (text-to-SQL) + chart specs.

The model writes a SELECT against virtual relations (`my_expenses`, `my_expense_items`).
We parse it with sqlglot and reject anything that is not a single, plain SELECT over those
relations. Then the relations are injected as CTEs filtered to the current user, so even a
"valid" query can only ever see that user's rows. On SQL Server, RLS filters a third time.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlglot import exp
from sqlglot.errors import ParseError

from app.services.money import to_major


class UnsafeQuery(ValueError):
    pass


CHART_TYPES = ("bar", "line", "pie")

# Virtual relation -> per-dialect definition. `:kasa_user_id` is bound, never interpolated.
# `expense_month` ('YYYY-MM') is precomputed so the model never needs dialect date functions.
_RELATIONS: dict[str, dict[str, str]] = {
    "my_expenses": {
        "sqlite": (
            "SELECT id, merchant, expense_date, strftime('%Y-%m', expense_date) AS expense_month, "
            "currency, total_minor, category, source, house_id "
            "FROM expenses WHERE owner_id = :kasa_user_id"
        ),
        "tsql": (
            "SELECT id, merchant, expense_date, CONVERT(CHAR(7), expense_date, 126) AS expense_month, "
            "currency, total_minor, category, source, house_id "
            "FROM dbo.expenses WHERE owner_id = :kasa_user_id"
        ),
    },
    "my_expense_items": {
        "sqlite": (
            "SELECT i.id, i.expense_id, i.description, i.quantity, i.amount_minor "
            "FROM expense_items AS i JOIN expenses AS e ON e.id = i.expense_id "
            "WHERE e.owner_id = :kasa_user_id"
        ),
        "tsql": (
            "SELECT i.id, i.expense_id, i.description, i.quantity, i.amount_minor "
            "FROM dbo.expense_items AS i JOIN dbo.expenses AS e ON e.id = i.expense_id "
            "WHERE e.owner_id = :kasa_user_id"
        ),
    },
}
ALLOWED_RELATIONS = frozenset(_RELATIONS)

RELATIONS_DOC = """\
my_expenses(id, merchant, expense_date DATE, expense_month TEXT 'YYYY-MM', currency,
            total_minor INTEGER  -- amount in kuruş/cents, category, source, house_id)
my_expense_items(id, expense_id -> my_expenses.id, description, quantity,
                 amount_minor INTEGER  -- amount in kuruş/cents)"""

_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Into, exp.Placeholder, exp.Parameter, exp.Pragma, exp.Transaction,
    exp.Commit, exp.Rollback, exp.Use, exp.Set, exp.Lock,
)  # fmt: skip
# Defence in depth: these would be blocked by the relation allowlist or permissions anyway.
_FORBIDDEN_FUNCTIONS = frozenset(
    {"openrowset", "opendatasource", "openquery", "openxml", "load_extension", "readfile",
     "writefile", "fts3_tokenizer", "session_context"}
)  # fmt: skip


def sql_dialect(db: Session) -> str:
    return "tsql" if db.get_bind().dialect.name == "mssql" else "sqlite"


def validate_report_sql(sql: str, dialect: str = "sqlite") -> exp.Query:
    """Return the parsed query if it is a single safe SELECT over allowed relations."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except ParseError as exc:
        raise UnsafeQuery(f"could not parse SQL: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeQuery("exactly one SQL statement is allowed")
    query = statements[0]
    if not isinstance(query, (exp.Select, exp.SetOperation)):
        raise UnsafeQuery("only SELECT queries are allowed")

    for node in query.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise UnsafeQuery(f"{node.key.upper()} is not allowed")
        if isinstance(node, (exp.Anonymous, exp.Func)) and _func_name(node) in _FORBIDDEN_FUNCTIONS:
            raise UnsafeQuery(f"function {_func_name(node)} is not allowed")

    ctes = list(query.find_all(exp.CTE))
    cte_names = {cte.alias_or_name.lower() for cte in ctes}
    if cte_names & ALLOWED_RELATIONS:
        raise UnsafeQuery("CTE names may not shadow my_expenses / my_expense_items")
    for cte in ctes:  # recursive CTEs can run unbounded; reports never need them
        if any(t.name.lower() == cte.alias_or_name.lower() for t in cte.this.find_all(exp.Table)):
            raise UnsafeQuery("recursive CTEs are not allowed")
    for table in query.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise UnsafeQuery("table functions are not allowed")
        if table.args.get("db") or table.args.get("catalog"):
            raise UnsafeQuery("schema-qualified names are not allowed")
        name = table.name.lower()
        if name not in ALLOWED_RELATIONS and name not in cte_names:
            raise UnsafeQuery(f"unknown relation {table.name!r}; use {', '.join(sorted(ALLOWED_RELATIONS))}")
    return query


def _func_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    return node.sql_name().lower() if isinstance(node, exp.Func) else ""


def build_scoped_sql(query: exp.Query, dialect: str, row_limit: int) -> str:
    """Prepend the user-scoped CTEs for the relations the query uses and cap the row count."""
    used = sorted({t.name.lower() for t in query.find_all(exp.Table)} & ALLOWED_RELATIONS)
    scoped = query.copy()
    if isinstance(scoped, exp.Select) and scoped.args.get("limit") is None and not scoped.args.get("top"):
        scoped = scoped.limit(row_limit)
    existing = scoped.args.get("with_")
    user_ctes = list(existing.expressions) if existing else []
    if existing:
        scoped.set("with_", None)
    ours = [
        exp.CTE(
            this=sqlglot.parse_one(_RELATIONS[name][dialect], read=dialect),
            alias=exp.TableAlias(this=exp.to_identifier(name)),
        )
        for name in used
    ]
    if ours or user_ctes:
        scoped.set("with_", exp.With(expressions=ours + user_ctes))
    return scoped.sql(dialect=dialect)


def run_report_query(db: Session, user_id: str, sql: str, row_limit: int = 200) -> dict[str, Any]:
    """Validate, scope and execute. Returns JSON-safe rows; `*_minor` columns are converted
    to exact major-unit strings (e.g. total_minor 12345 -> total "123.45")."""
    dialect = sql_dialect(db)
    query = validate_report_sql(sql, dialect)
    final_sql = build_scoped_sql(query, dialect, row_limit + 1)  # +1 detects truncation
    result = db.execute(text(final_sql), {"kasa_user_id": user_id})
    raw_columns = list(result.keys())
    fetched = result.fetchmany(row_limit + 1)
    db.rollback()  # read-only: never leave a transaction open
    columns = [_display_name(c) for c in raw_columns]
    rows = [
        {_display_name(c): _jsonable(c, v) for c, v in zip(raw_columns, row, strict=True)}
        for row in fetched[:row_limit]
    ]
    return {"columns": columns, "rows": rows, "row_count": len(rows), "truncated": len(fetched) > row_limit}


def _display_name(column: str) -> str:
    return column[: -len("_minor")] if column.lower().endswith("_minor") else column


def _jsonable(column: str, value: Any) -> Any:
    if value is None:
        return None
    if column.lower().endswith("_minor") and isinstance(value, (int, Decimal)):
        return str(to_major(int(value)))
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def build_chart(report: dict[str, Any], chart_type: str, x: str, y: str, title: str = "") -> dict[str, Any]:
    """Chart spec the frontend renders with recharts: {type, title, x, y, data}."""
    if chart_type not in CHART_TYPES:
        raise ValueError("chart_type must be bar, line or pie")
    x, y = _display_name(x), _display_name(y)
    for col in (x, y):
        if col not in report["columns"]:
            raise ValueError(f"column {col!r} not in result columns {report['columns']}")
    data = []
    for row in report["rows"]:
        value = row[y]
        # Charts need numbers; Decimal -> float happens only here, for drawing.
        data.append({x: row[x], y: float(Decimal(str(value))) if value is not None else 0})
    return {"type": chart_type, "title": title, "x": x, "y": y, "data": data}
