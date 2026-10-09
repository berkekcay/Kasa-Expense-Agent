import datetime as dt

import pytest

from app.services import reports
from app.services.expenses import ExpenseInput, ItemInput, create_expense
from app.services.reports import UnsafeQuery, build_chart, run_report_query, validate_report_sql


class TestSqlGuard:
    @pytest.mark.parametrize(
        "sql",
        [
            "SELECT category, SUM(total_minor) AS total_minor FROM my_expenses GROUP BY category",
            "SELECT e.merchant, i.description FROM my_expenses e JOIN my_expense_items i ON i.expense_id = e.id",
            "WITH m AS (SELECT expense_month, total_minor FROM my_expenses) SELECT expense_month, SUM(total_minor) FROM m GROUP BY expense_month",
            "SELECT merchant FROM my_expenses WHERE total_minor > (SELECT AVG(total_minor) FROM my_expenses)",
            "SELECT merchant FROM my_expenses UNION SELECT description FROM my_expense_items",
            "select count(*) from MY_EXPENSES;",
        ],
    )
    def test_accepts_safe_selects(self, sql):
        validate_report_sql(sql)

    @pytest.mark.parametrize(
        ("sql", "reason"),
        [
            ("INSERT INTO my_expenses (merchant) VALUES ('x')", "SELECT"),
            ("UPDATE my_expenses SET total_minor = 0", "SELECT"),
            ("DELETE FROM my_expenses", "SELECT"),
            ("DROP TABLE expenses", "SELECT"),
            ("SELECT 1; DROP TABLE expenses", "one SQL statement"),
            ("SELECT * FROM my_expenses; SELECT * FROM my_expense_items", "one SQL statement"),
            ("SELECT * FROM expenses", "unknown relation"),
            ("SELECT * FROM users", "unknown relation"),
            ("SELECT * FROM sqlite_master", "unknown relation"),
            ("SELECT * FROM my_expenses e JOIN expense_shares s ON s.expense_id = e.id", "unknown relation"),
            ("SELECT * FROM main.my_expenses", "schema-qualified"),
            ("SELECT * INTO stolen FROM my_expenses", "INTO"),
            ("WITH my_expenses AS (SELECT * FROM expenses) SELECT * FROM my_expenses", "shadow"),
            ("WITH r AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM r) SELECT * FROM r", "recursive"),
            ("SELECT load_extension('evil')", "not allowed"),
            ("SELECT * FROM my_expenses WHERE owner_id = :other", "PLACEHOLDER"),
            ("PRAGMA table_info(expenses)", "SELECT"),
            ("", "one SQL statement"),
        ],
    )
    def test_rejects(self, sql, reason):
        with pytest.raises(UnsafeQuery, match=reason):
            validate_report_sql(sql)

    def test_rejects_tsql_specific_attacks(self):
        for sql in [
            "SELECT * FROM OPENROWSET('SQLNCLI', 'server', 'SELECT 1')",
            "EXEC xp_cmdshell 'dir'",
            "SELECT * FROM dbo.expenses",
        ]:
            with pytest.raises(UnsafeQuery):
                validate_report_sql(sql, dialect="tsql")

    def test_scoped_sql_injects_ctes_and_limit(self):
        query = validate_report_sql("SELECT merchant FROM my_expenses")
        sql = reports.build_scoped_sql(query, "sqlite", 50)
        assert sql.startswith("WITH my_expenses AS (")
        assert "owner_id = :kasa_user_id" in sql
        assert sql.endswith("LIMIT 50")
        tsql = reports.build_scoped_sql(
            validate_report_sql("SELECT merchant FROM my_expenses", "tsql"), "tsql", 50
        )
        assert "TOP 50" in tsql and "dbo.expenses" in tsql


class TestRunReport:
    def test_only_sees_own_rows_and_converts_minor_units(self, db):
        day = dt.date(2026, 9, 1)
        create_expense(
            db,
            "test-user",
            ExpenseInput("Migros", "100.50", day, category="groceries", items=[ItemInput("Milk", "100.50")]),
        )
        create_expense(db, "test-user", ExpenseInput("BIM", "20.25", day, category="groceries"))
        create_expense(db, "test-user", ExpenseInput("Metro", "15", day, category="transport"))
        create_expense(db, "someone-else", ExpenseInput("Secret", "999", day, category="groceries"))

        result = run_report_query(
            db,
            "test-user",
            "SELECT category, SUM(total_minor) AS total_minor FROM my_expenses GROUP BY category ORDER BY category",
        )
        assert result["columns"] == ["category", "total"]
        assert result["rows"] == [
            {"category": "groceries", "total": "120.75"},
            {"category": "transport", "total": "15.00"},
        ]

        chart = build_chart(result, "bar", "category", "total_minor", "By category")
        assert chart == {
            "type": "bar",
            "title": "By category",
            "x": "category",
            "y": "total",
            "data": [{"category": "groceries", "total": 120.75}, {"category": "transport", "total": 15.0}],
        }

    def test_row_limit(self, db):
        for i in range(5):
            create_expense(db, "limit-user", ExpenseInput(f"Shop {i}", "1", dt.date(2026, 1, 1)))
        result = run_report_query(db, "limit-user", "SELECT merchant FROM my_expenses", row_limit=3)
        assert result["row_count"] == 3 and result["truncated"] is True

    def test_chart_rejects_unknown_column(self, db):
        result = run_report_query(db, "test-user", "SELECT merchant FROM my_expenses")
        with pytest.raises(ValueError):
            build_chart(result, "pie", "merchant", "nope")
