"""Guarded read-only SQL for the Report agent (text-to-SQL) + chart specs.

The model writes one SELECT against virtual relations (`my_expenses`, `my_expense_items`,
`my_house_shares`, `my_budgets`, `my_subscriptions`). We parse it with sqlglot and reject
anything that is not a single, plain SELECT over those relations. Then the relations are
injected as CTEs filtered to the current user, so even a "valid" query can only ever see
that user's rows. On SQL Server, RLS filters a third time.

The model always writes SQLite-flavoured standard SQL (LIMIT, ||). Month columns are
precomputed, so it never needs dialect date functions; sqlglot transpiles the checked query
to T-SQL when the database is SQL Server.
"""

from __future__ import annotations

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlglot
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlglot import exp
from sqlglot.errors import ParseError, SqlglotError

from app.db.models import Base
from app.services.categories import CATEGORIES
from app.services.money import to_major


class UnsafeQuery(ValueError):
    pass


CHART_TYPES = ("bar", "line", "pie")
# The dialect the model writes in. Final SQL is generated for the database's dialect.
MODEL_DIALECT = "sqlite"

# --- Relations ------------------------------------------------------------------------------
# Each relation is written once with two placeholders: {t} is the schema prefix and
# {month} turns a date column into 'YYYY-MM'. `:kasa_user_id` is bound, never interpolated.
_DIALECTS: dict[str, dict[str, str]] = {
    "sqlite": {"t": "", "month": "strftime('%Y-%m', {col})"},
    "tsql": {"t": "dbo.", "month": "CONVERT(CHAR(7), {col}, 126)"},
}

_RELATION_TEMPLATES: dict[str, str] = {
    "my_expenses": (
        "SELECT e.id, e.merchant, e.expense_date, {month_e} AS expense_month, e.category, "
        "e.currency, e.total_minor, e.source, e.house_id, e.split_type, e.original_currency, "
        "e.original_total_minor, "
        "CASE WHEN e.subscription_id IS NULL THEN 0 ELSE 1 END AS is_subscription, "
        "s.display_name AS subscription_name "
        "FROM {t}expenses AS e "
        "LEFT JOIN {t}subscriptions AS s ON s.id = e.subscription_id AND s.user_id = :kasa_user_id "
        "WHERE e.owner_id = :kasa_user_id"
    ),
    "my_expense_items": (
        "SELECT i.id, i.expense_id, i.description, i.quantity, i.amount_minor, "
        "{month_e} AS expense_month, e.category, e.merchant "
        "FROM {t}expense_items AS i JOIN {t}expenses AS e ON e.id = i.expense_id "
        "WHERE e.owner_id = :kasa_user_id"
    ),
    "my_house_shares": (
        "SELECT e.id AS expense_id, e.house_id, h.name AS house_name, e.expense_date, "
        "{month_e} AS expense_month, e.merchant, e.category, e.split_type, e.currency, "
        "e.total_minor AS bill_total_minor, sh.amount_minor AS my_share_minor, "
        "CASE WHEN e.owner_id = :kasa_user_id THEN 1 ELSE 0 END AS paid_by_me "
        "FROM {t}expense_shares AS sh "
        "JOIN {t}expenses AS e ON e.id = sh.expense_id "
        "JOIN {t}houses AS h ON h.id = e.house_id "
        "WHERE sh.user_id = :kasa_user_id"
    ),
    "my_budgets": (
        "SELECT b.id, b.category, b.limit_minor, b.currency, b.alert_threshold_pct "
        "FROM {t}budgets AS b WHERE b.user_id = :kasa_user_id"
    ),
    "my_subscriptions": (
        "SELECT s.id, s.display_name AS name, s.amount_minor, s.currency, s.period, "
        "s.last_charge_date, s.next_expected_date, s.status "
        "FROM {t}subscriptions AS s WHERE s.user_id = :kasa_user_id"
    ),
}


def relation_sql(name: str, dialect: str) -> str:
    """The user-scoped definition of one virtual relation in `dialect` (sqlite or tsql)."""
    d = _DIALECTS[dialect]
    return _RELATION_TEMPLATES[name].format(t=d["t"], month_e=d["month"].format(col="e.expense_date"))


ALLOWED_RELATIONS = frozenset(_RELATION_TEMPLATES)
# User CTEs may not reuse these names: a CTE called `expenses` would otherwise be picked
# up by our own relation definitions on SQLite.
_RESERVED_NAMES = ALLOWED_RELATIONS | frozenset(Base.metadata.tables)


def relations_doc(this_month: str = "YYYY-MM", first_month: str = "YYYY-MM") -> str:
    """Relation reference for the report and checker prompts. Pass real months to make the
    examples concrete (first_month = five months before this_month)."""
    return f"""\
All money columns end in _minor and hold INTEGER minor units (kuruş): 12345 means 123.45.
Keep the _minor suffix on money aliases (SUM(total_minor) AS total_minor); the tool converts
them to TL. Dates are 'YYYY-MM-DD', months are 'YYYY-MM' text (compare with =, >=, BETWEEN;
no date functions needed). Flags are 1 or 0.
category is always one of: {", ".join(CATEGORIES)} (market = groceries, kira = rent,
fatura = utilities, ulaşım = transport, yemek/kafe = food).

my_expenses: every purchase the user paid, one row each.
  id, merchant, expense_date, expense_month, category, currency, total_minor,
  source (manual|receipt|statement|email), house_id (NULL = personal purchase),
  split_type (NULL = personal, else equal|percent|exact|items),
  original_currency, original_total_minor (amount before conversion to TRY; NULL if TRY),
  is_subscription (1/0), subscription_name
my_expense_items: receipt lines of my_expenses.
  id, expense_id (= my_expenses.id), description, quantity, amount_minor,
  expense_month, category, merchant
my_house_shares: the user's part of each shared-flat bill, whoever paid it.
  expense_id, house_id, house_name, expense_date, expense_month, merchant, category,
  split_type, currency, bill_total_minor (the whole bill), my_share_minor (the user's part),
  paid_by_me (1/0)
my_budgets: monthly limits. id, category (NULL = overall budget), limit_minor, currency,
  alert_threshold_pct
my_subscriptions: recurring charges. id, name, amount_minor, currency,
  period (weekly|monthly|yearly), last_charge_date, next_expected_date, status (active|dismissed)

Which relation:
- "How much did I spend", per category, merchant or month: my_expenses WHERE house_id IS NULL.
  House bills the user paid for everyone are also in my_expenses; leave them out.
- The flat, house, rent or shared bills (ev, kira, ev faturası): SUM(my_share_minor) from
  my_house_shares, never the whole bill.
- Everything including the user's house shares: example 4.

Examples:
1. SELECT category, SUM(total_minor) AS total_minor FROM my_expenses
   WHERE house_id IS NULL AND expense_month = '{this_month}' GROUP BY category ORDER BY total_minor DESC
2. SELECT expense_month, SUM(total_minor) AS total_minor FROM my_expenses
   WHERE house_id IS NULL AND expense_month BETWEEN '{first_month}' AND '{this_month}'
   GROUP BY expense_month ORDER BY expense_month
3. SELECT SUM(my_share_minor) AS my_share_minor FROM my_house_shares WHERE expense_month = '{this_month}'
4. SELECT SUM(amount_minor) AS amount_minor FROM (
     SELECT total_minor AS amount_minor FROM my_expenses WHERE house_id IS NULL AND expense_month = '{this_month}'
     UNION ALL
     SELECT my_share_minor FROM my_house_shares WHERE expense_month = '{this_month}') AS t"""


RELATIONS_DOC = relations_doc()

# --- Guard ----------------------------------------------------------------------------------

_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.Command, exp.Into, exp.Placeholder, exp.Parameter, exp.Pragma, exp.Transaction,
    exp.Commit, exp.Rollback, exp.Use, exp.Set, exp.Lock, exp.Attach, exp.Detach,
)  # fmt: skip
# Defence in depth: these would be blocked by the relation allowlist or permissions anyway.
_FORBIDDEN_FUNCTIONS = frozenset(
    {"openrowset", "opendatasource", "openquery", "openxml", "load_extension", "readfile",
     "writefile", "edit", "fts3_tokenizer", "session_context", "randomblob", "zeroblob",
     "user_name", "suser_name", "suser_sname", "host_name", "db_name", "original_login",
     "current_user", "current_version", "current_schema", "current_database", "current_role",
     "system_user", "object_id", "object_name"}
)  # fmt: skip
_FORBIDDEN_FUNCTION_PREFIXES = ("sqlite_", "pragma_", "sp_", "xp_", "fn_", "sys")


def sql_dialect(db: Session) -> str:
    return "tsql" if db.get_bind().dialect.name == "mssql" else "sqlite"


def validate_report_sql(sql: str, dialect: str = MODEL_DIALECT) -> exp.Query:
    """Return the parsed query if it is a single safe SELECT over allowed relations."""
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except (ParseError, SqlglotError) as exc:
        raise UnsafeQuery(f"could not parse SQL: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeQuery("exactly one SQL statement is allowed")
    query = statements[0]
    if not isinstance(query, (exp.Select, exp.SetOperation)):
        raise UnsafeQuery("only SELECT queries are allowed")

    for node in query.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise UnsafeQuery(f"{node.key.upper()} is not allowed")
        name = _func_name(node)
        if name and (name in _FORBIDDEN_FUNCTIONS or name.startswith(_FORBIDDEN_FUNCTION_PREFIXES)):
            raise UnsafeQuery(f"function {name} is not allowed")
        if isinstance(node, exp.Limit):
            _check_limit(node)

    ctes = list(query.find_all(exp.CTE))
    cte_names = {cte.alias_or_name.lower() for cte in ctes}
    if cte_names & _RESERVED_NAMES:
        raise UnsafeQuery(f"CTE names may not shadow {', '.join(sorted(ALLOWED_RELATIONS))} or base tables")
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


def _check_limit(limit: exp.Limit) -> None:
    value = limit.expression
    if not (isinstance(value, exp.Literal) and not value.is_string and value.this.isdigit()):
        raise UnsafeQuery("LIMIT must be a plain number")


def _clamp_limit(query: exp.Query, row_limit: int) -> exp.Query:
    """Add LIMIT row_limit when there is none; lower a bigger one to row_limit."""
    limit = query.args.get("limit")
    if limit is None:
        return query.limit(row_limit)
    value = limit.expression
    if isinstance(value, exp.Literal) and int(value.this) > row_limit:
        limit.set("expression", exp.Literal.number(row_limit))
    return query


def build_scoped_sql(query: exp.Query, dialect: str, row_limit: int) -> str:
    """Prepend the user-scoped CTEs for the relations the query uses, cap the row count and
    render for `dialect`. Comments are dropped so nothing can hide in them."""
    used = sorted({t.name.lower() for t in query.find_all(exp.Table)} & ALLOWED_RELATIONS)
    scoped = query.copy()
    for select in _output_selects(scoped):
        _keep_minor_suffix(select)
    scoped = _clamp_limit(scoped, row_limit)
    existing = scoped.args.get("with_")
    user_ctes = list(existing.expressions) if existing else []
    if existing:
        scoped.set("with_", None)
    ours = [
        exp.CTE(
            this=sqlglot.parse_one(relation_sql(name, dialect), read=dialect),
            alias=exp.TableAlias(this=exp.to_identifier(name)),
        )
        for name in used
    ]
    if ours or user_ctes:
        scoped.set("with_", exp.With(expressions=ours + user_ctes))
    return scoped.sql(dialect=dialect, comments=False)


def _output_selects(query: exp.Expression):
    """The SELECTs whose columns become the result columns (both sides of a UNION)."""
    if isinstance(query, exp.SetOperation):
        yield from _output_selects(query.left)
        yield from _output_selects(query.right)
    elif isinstance(query, exp.Select):
        yield query
    elif isinstance(query, exp.Subquery):
        yield from _output_selects(query.this)


def _money_column(node: exp.Expression) -> str | None:
    """Name of the *_minor column behind a money expression, else None.

    Money: a *_minor column, or SUM/MIN/MAX/AVG/ROUND/ABS/COALESCE of one, a CASE whose
    branches are money, or the sum/difference of two money expressions. COUNT is not money.
    """
    if isinstance(node, exp.Column):
        return node.name if node.name.lower().endswith("_minor") else None
    if isinstance(node, exp.Window):
        return _money_column(node.this)
    if isinstance(node, (exp.Sum, exp.Min, exp.Max, exp.Avg, exp.Paren, exp.Coalesce, exp.Round, exp.Abs)):
        return _money_column(node.this)
    if isinstance(node, (exp.Add, exp.Sub)):
        left, right = _money_column(node.left), _money_column(node.right)
        return left if left and right else None
    if isinstance(node, exp.Case):
        branches = [i.args.get("true") for i in node.args.get("ifs") or []] + [node.args.get("default")]
        names = [_money_column(b) for b in branches if b is not None and not _is_zero(b)]
        return names[0] if names and all(names) else None
    return None


def _is_zero(node: exp.Expression) -> bool:
    return isinstance(node, exp.Null) or (isinstance(node, exp.Literal) and node.this in ("0", "0.0"))


def _keep_minor_suffix(select: exp.Select) -> None:
    """Models often write `SUM(total_minor) AS total`, which would hide that the value is in
    minor units and skip the conversion to major units. Rename such aliases to `total_minor`
    (and ORDER BY / HAVING references to them); results still show the column as `total`.
    An unnamed money expression like `SUM(total_minor)` gets its column's name as alias."""
    renamed: dict[str, str] = {}
    taken = {p.alias_or_name.lower() for p in select.expressions}
    for i, projection in enumerate(list(select.expressions)):
        if isinstance(projection, exp.Alias):
            source = _money_column(projection.this)
            alias = projection.alias
            if source and not alias.lower().endswith("_minor"):
                renamed[alias.lower()] = f"{alias}_minor"
                projection.set("alias", exp.to_identifier(f"{alias}_minor"))
        elif not isinstance(projection, exp.Column) and (source := _money_column(projection)):
            alias = source if source.lower() not in taken else f"value{i}_minor"
            taken.add(alias.lower())
            projection.replace(exp.alias_(projection.copy(), alias))
    if not renamed:
        return
    for key in ("order", "having"):
        clause = select.args.get(key)
        for column in clause.find_all(exp.Column) if clause else ():
            if not column.table and column.name.lower() in renamed:
                column.set("this", exp.to_identifier(renamed[column.name.lower()]))


# --- Execution ------------------------------------------------------------------------------


def run_report_query(db: Session, user_id: str, sql: str, row_limit: int = 200) -> dict[str, Any]:
    """Validate, scope and execute. Returns JSON-safe rows; `*_minor` columns are converted
    to exact major-unit strings (e.g. total_minor 12345 -> total "123.45")."""
    query = validate_report_sql(sql, MODEL_DIALECT)
    final_sql = build_scoped_sql(query, sql_dialect(db), row_limit + 1)  # +1 detects truncation
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
    if column.lower().endswith("_minor"):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, Decimal)) and Decimal(value) == int(value):
            return str(to_major(int(value)))
        if isinstance(value, (float, Decimal)):  # AVG of minor units: round half up to kuruş
            minor = Decimal(repr(value) if isinstance(value, float) else value)
            return str((minor / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
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
        try:
            number = float(Decimal(str(value))) if value is not None else 0
        except ArithmeticError as exc:
            raise ValueError(f"column {y!r} is not numeric") from exc
        data.append({x: row[x], y: number})
    return {"type": chart_type, "title": title, "x": x, "y": y, "data": data}
