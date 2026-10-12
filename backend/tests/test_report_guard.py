"""Report relations (user-scoped CTEs) and the static SQL guard."""

import datetime as dt

import pytest
import sqlglot

from app.services import reports
from app.services.reports import UnsafeQuery, build_scoped_sql, run_report_query, validate_report_sql
from evals.seed import SECRET_MERCHANT, seed_demo_data

TODAY = dt.date(2026, 10, 20)


@pytest.fixture
def seeded(db):
    """A seeded user (fresh id per test) plus the flatmate whose data must stay hidden."""
    import uuid

    user = f"guard-{uuid.uuid4().hex[:8]}"
    seed_demo_data(user, today=TODAY, db=db)
    return user


class TestRelations:
    @pytest.mark.parametrize("name", sorted(reports.ALLOWED_RELATIONS))
    @pytest.mark.parametrize("dialect", ["sqlite", "tsql"])
    def test_every_relation_parses_in_both_dialects(self, name, dialect):
        sql = reports.relation_sql(name, dialect)
        parsed = sqlglot.parse_one(sql, read=dialect)
        assert ":kasa_user_id" in parsed.sql(dialect=dialect)
        if dialect == "tsql":
            assert "dbo." in sql and "strftime" not in sql

    @pytest.mark.parametrize("name", sorted(reports.ALLOWED_RELATIONS))
    def test_scoped_query_renders_for_tsql(self, name):
        query = validate_report_sql(f"SELECT * FROM {name} LIMIT 5")
        tsql = build_scoped_sql(query, "tsql", 50)
        assert tsql.startswith(f"WITH {name} AS (")
        assert "TOP 5" in tsql and "LIMIT" not in tsql
        assert "dbo." in tsql and ":kasa_user_id" in tsql
        sqlglot.parse_one(tsql, read="tsql")  # the T-SQL we would send parses back

    def test_model_sql_is_transpiled_for_tsql(self):
        query = validate_report_sql(
            "SELECT expense_month, merchant || ' / ' || category AS label, SUM(total_minor) AS total "
            "FROM my_expenses WHERE house_id IS NULL GROUP BY expense_month, label "
            "ORDER BY total DESC LIMIT 10"
        )
        tsql = build_scoped_sql(query, "tsql", 200)
        assert "TOP 10" in tsql
        assert "CONVERT(CHAR(7), e.expense_date, 126) AS expense_month" in tsql
        assert "AS total_minor" in tsql and "ORDER BY total_minor DESC" in tsql
        assert "+ ' / ' +" in tsql

    def test_every_relation_runs_on_sqlite_and_is_scoped(self, db, seeded):
        for name in reports.ALLOWED_RELATIONS:
            mine = run_report_query(db, seeded, f"SELECT COUNT(*) AS n FROM {name}")
            stranger = run_report_query(db, "nobody-at-all", f"SELECT COUNT(*) AS n FROM {name}")
            assert mine["rows"][0]["n"] > 0, name
            assert stranger["rows"][0]["n"] == 0, name

    def test_my_expenses_columns(self, db, seeded):
        result = run_report_query(
            db,
            seeded,
            "SELECT merchant, expense_month, split_type, source, original_currency, original_total_minor, "
            "is_subscription, subscription_name FROM my_expenses "
            "WHERE merchant IN ('Amazon', 'Netflix', 'Trendyol', 'Kira') ORDER BY expense_date DESC",
        )
        rows = result["rows"]
        assert {r["merchant"] for r in rows} == {"Amazon", "Netflix", "Trendyol", "Kira"}
        amazon = next(r for r in rows if r["merchant"] == "Amazon")
        assert amazon["original_currency"] == "USD" and amazon["original_total"] == "49.99"
        assert amazon["expense_month"] == "2026-07"
        netflix = [r for r in rows if r["merchant"] == "Netflix"]
        assert len(netflix) == 6 and all(r["is_subscription"] == 1 for r in netflix)
        assert netflix[0]["subscription_name"] == "Netflix"
        assert next(r for r in rows if r["merchant"] == "Trendyol")["source"] == "email"
        assert next(r for r in rows if r["merchant"] == "Kira")["split_type"] == "equal"
        assert SECRET_MERCHANT not in str(rows)

    def test_house_shares_use_my_share_not_the_bill(self, db, seeded):
        result = run_report_query(
            db,
            seeded,
            "SELECT house_name, SUM(my_share_minor) AS my_share_minor, SUM(bill_total_minor) AS bill_minor, "
            "SUM(paid_by_me) AS paid_by_me FROM my_house_shares WHERE expense_month = '2026-10' "
            "GROUP BY house_name",
        )
        assert result["rows"] == [
            {"house_name": "Moda evi", "my_share": "5650.00", "bill": "16950.00", "paid_by_me": 2}
        ]

    def test_flatmate_sees_own_shares_only(self, db, seeded):
        result = run_report_query(
            db, f"{seeded}-ali", "SELECT SUM(my_share_minor) AS s FROM my_house_shares WHERE paid_by_me = 1"
        )
        assert result["rows"] == [{"s": "300.00"}]  # the electricity bill Ali paid
        mine = run_report_query(db, f"{seeded}-ali", "SELECT merchant FROM my_expenses")
        assert {r["merchant"] for r in mine["rows"]} == {SECRET_MERCHANT, "Elektrik faturası"}

    def test_items_budgets_subscriptions(self, db, seeded):
        items = run_report_query(
            db, seeded, "SELECT description, amount_minor, expense_month FROM my_expense_items ORDER BY id"
        )
        assert [r["description"] for r in items["rows"]] == ["Süt", "Peynir", "Deterjan"]
        assert items["rows"][0] == {"description": "Süt", "amount": "79.90", "expense_month": "2026-10"}
        budgets = run_report_query(
            db, seeded, "SELECT category, limit_minor FROM my_budgets ORDER BY limit_minor"
        )
        assert budgets["rows"] == [
            {"category": "groceries", "limit": "3000.00"},
            {"category": None, "limit": "15000.00"},
        ]
        subs = run_report_query(db, seeded, "SELECT name, amount_minor, period, status FROM my_subscriptions")
        assert subs["rows"] == [
            {"name": "Netflix", "amount": "229.99", "period": "monthly", "status": "active"}
        ]


class TestGuard:
    @pytest.mark.parametrize(
        ("sql", "reason"),
        [
            ("INSERT INTO my_expenses (merchant) VALUES ('x')", "SELECT"),
            ("REPLACE INTO my_budgets VALUES (1)", "SELECT"),
            ("UPDATE my_budgets SET limit_minor = 1", "SELECT"),
            ("DELETE FROM my_subscriptions", "SELECT"),
            ("DROP TABLE expenses", "SELECT"),
            ("SELECT 1; DROP TABLE expenses", "one SQL statement"),
            ("SELECT 1 /* harmless */; DROP TABLE expenses", "one SQL statement"),
            ("SELECT 1; -- just a comment\nDELETE FROM expenses", "one SQL statement"),
            ("SELECT * FROM budgets", "unknown relation"),
            ("SELECT * FROM expense_shares", "unknown relation"),
            ("SELECT * FROM my_house_shares JOIN houses ON houses.id = my_house_shares.house_id", "unknown"),
            ("SELECT * FROM sqlite_master", "unknown relation"),
            ("SELECT name FROM sqlite_schema", "unknown relation"),
            ("SELECT * FROM sys.objects", "schema-qualified"),
            ("SELECT * FROM main.my_budgets", "schema-qualified"),
            ("SELECT sqlite_version()", "not allowed"),
            ("SELECT load_extension('evil')", "not allowed"),
            ("SELECT * FROM json_each('[1]')", "table functions"),
            ("SELECT randomblob(1000000000) FROM my_expenses", "not allowed"),
            ("SELECT * FROM pragma_table_info('expenses')", "not allowed"),
            ("PRAGMA table_info(expenses)", "SELECT"),
            ("ATTACH DATABASE 'other.db' AS other", "SELECT"),
            ("SELECT * INTO stolen FROM my_expenses", "INTO"),
            ("WITH expenses AS (SELECT * FROM my_expenses) SELECT * FROM expenses", "shadow"),
            ("WITH my_budgets AS (SELECT 1 AS id) SELECT * FROM my_budgets", "shadow"),
            ("SELECT * FROM my_expenses LIMIT (SELECT COUNT(*) FROM my_expenses)", "LIMIT"),
            ("SELECT * FROM my_expenses WHERE owner_id = ?", "PLACEHOLDER"),
        ],
    )
    def test_rejects(self, sql, reason):
        with pytest.raises(UnsafeQuery, match=reason):
            validate_report_sql(sql)

    def test_tsql_objects_and_functions_are_rejected(self):
        for sql in [
            "SELECT * FROM sys.tables",
            "SELECT name FROM master.dbo.sysdatabases",
            "SELECT SUSER_SNAME()",
            "SELECT * FROM my_expenses WHERE merchant = @@VERSION",
            "SELECT SESSION_CONTEXT(N'user_id')",
        ]:
            with pytest.raises(UnsafeQuery):
                validate_report_sql(sql, dialect="tsql")

    def test_comments_are_dropped_from_the_executed_sql(self):
        sql = "SELECT merchant FROM my_expenses -- */ DROP TABLE expenses\n/* ; DELETE FROM expenses */"
        scoped = build_scoped_sql(validate_report_sql(sql), "sqlite", 50)
        assert "DROP" not in scoped and "DELETE" not in scoped and "/*" not in scoped and "--" not in scoped

    def test_large_limit_is_clamped(self, db, seeded):
        scoped = build_scoped_sql(
            validate_report_sql("SELECT merchant FROM my_expenses LIMIT 1000000"), "sqlite", 50
        )
        assert scoped.endswith("LIMIT 50")
        small = build_scoped_sql(
            validate_report_sql("SELECT merchant FROM my_expenses LIMIT 5"), "sqlite", 50
        )
        assert small.endswith("LIMIT 5")
        result = run_report_query(db, seeded, "SELECT merchant FROM my_expenses LIMIT 1000000", row_limit=3)
        assert result["row_count"] == 3 and result["truncated"] is True

    def test_union_gets_a_limit(self):
        query = validate_report_sql(
            "SELECT merchant FROM my_expenses UNION SELECT name FROM my_subscriptions"
        )
        assert build_scoped_sql(query, "sqlite", 20).endswith("LIMIT 20")
        assert "TOP 20" in build_scoped_sql(query, "tsql", 20)


class TestMoneyColumns:
    def test_avg_case_and_unaliased_sums_are_converted(self, db, seeded):
        result = run_report_query(
            db,
            seeded,
            "SELECT SUM(total_minor), AVG(total_minor) AS avg_total, "
            "SUM(CASE WHEN category = 'food' THEN total_minor ELSE 0 END) AS food, COUNT(*) AS n "
            "FROM my_expenses WHERE house_id IS NULL AND merchant IN ('Kahve Dünyası', 'Yemeksepeti') "
            "AND expense_month = '2026-10'",
        )
        assert result["columns"] == ["total", "avg_total", "food", "n"]
        assert result["rows"] == [{"total": "335.50", "avg_total": "167.75", "food": "335.50", "n": 2}]

    def test_union_of_personal_and_house_shares(self, db, seeded):
        result = run_report_query(
            db,
            seeded,
            "SELECT SUM(amount_minor) AS amount_minor FROM ("
            "SELECT total_minor AS amount_minor FROM my_expenses WHERE house_id IS NULL AND expense_month = '2026-10' "
            "UNION ALL SELECT my_share_minor FROM my_house_shares WHERE expense_month = '2026-10') AS t",
        )
        # personal this month: 1163.15 + 335.50 + 400 + 229.99 + 360 = 2488.64; house share 5650
        assert result["rows"] == [{"amount": "8138.64"}]

    def test_avg_rounds_half_up_to_kurus(self):
        assert reports._jsonable("avg_minor", 12345.5) == "123.46"
        assert reports._jsonable("avg_minor", 100.0) == "1.00"
        assert reports._jsonable("total_minor", 250) == "2.50"
