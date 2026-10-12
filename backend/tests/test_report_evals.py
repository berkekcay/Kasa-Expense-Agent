"""Eval harness, offline: the seed, the expected-answer SQL and the scoring, with fake runs."""

import datetime as dt
import json
import uuid
from decimal import Decimal

import pytest

from app.services.reports import run_report_query
from evals import run_evals
from evals.run_evals import CaseFacts, ChatTurn, EvalCase, EvalResult, load_cases, score
from evals.seed import SECRET_MERCHANT, seed_demo_data

TODAY = dt.date(2026, 10, 20)
CASES = {c.id: c for c in load_cases()}

# A correct query for every report case: run through the real relations, the result must
# score as a pass against the expected SQL over the base tables.


def _all_spending(columns: str, where: str, tail: str = "") -> str:
    """The default for "how much did I spend": personal purchases plus my house shares."""
    personal = columns.replace("amount_minor", "total_minor AS amount_minor")
    shares = columns.replace("amount_minor", "my_share_minor")
    return (
        f"SELECT {columns.replace('amount_minor', 'SUM(amount_minor) AS total_minor')} FROM ("
        f"SELECT {personal} FROM my_expenses WHERE house_id IS NULL AND {where} UNION ALL "
        f"SELECT {shares} FROM my_house_shares WHERE {where}) AS t {tail}"
    ).strip()


CORRECT_SQL = {
    "report-category-chart-tr": _all_spending(
        "category, amount_minor", "expense_month = '2026-10'", "GROUP BY category"
    ),
    "report-category-total-tr": _all_spending(
        "category, amount_minor", "expense_month = '2026-10'", "GROUP BY category ORDER BY total_minor DESC"
    ),
    "report-groceries-last-month-en": _all_spending(
        "amount_minor", "category = 'groceries' AND expense_month = '2026-09'"
    ),
    "report-flat-share-en": (
        "SELECT SUM(my_share_minor) AS my_share_minor FROM my_house_shares WHERE expense_month = '2026-10'"
    ),
    "report-monthly-trend-tr": _all_spending(
        "expense_month, amount_minor",
        "expense_month BETWEEN '2026-05' AND '2026-10'",
        "GROUP BY expense_month ORDER BY expense_month",
    ),
    "report-netflix-total-en": "SELECT SUM(total_minor) AS total_minor FROM my_expenses WHERE merchant = 'Netflix'",
    "report-transport-tr": _all_spending(
        "amount_minor", "category = 'transport' AND expense_month = '2026-10'"
    ),
    "report-personal-only-en": (
        "SELECT SUM(total_minor) AS spent FROM my_expenses WHERE house_id IS NULL AND expense_month = '2026-10'"
    ),
}


@pytest.fixture
def seeded(db):
    user = f"evals-{uuid.uuid4().hex[:8]}"
    seed_demo_data(user, today=TODAY, db=db)
    return user


def _facts(case: EvalCase, user: str) -> CaseFacts:
    params = run_evals.month_params(TODAY, user)
    facts = run_evals.compute_facts_before(case, params)
    run_evals.complete_facts_after(case, params, facts)
    return facts


def _report(rows, chart=None) -> dict:
    return {"status": "ok", "columns": list(rows[0]) if rows else [], "rows": rows, "chart": chart}


class TestCases:
    def test_case_file_shape(self):
        cases = load_cases()
        assert 12 <= len(cases) <= 20
        assert len({c.id for c in cases}) == len(cases)
        kinds = {c.kind for c in cases}
        assert kinds == {"routing", "report", "refusal"}
        assert {c.lang for c in cases} == {"tr", "en"}
        routed = {a for c in cases for a in run_evals._as_list(c.expect_agent)}
        assert {"receipt_agent", "house_agent", "report_agent", "budget_agent", "inbox_agent"} <= routed
        for case in cases:
            if case.kind == "report":
                assert case.expect_value_sql or case.expect_pairs_sql, case.id
            if case.kind == "refusal":
                assert case.expect_no_write, case.id
        assert set(CORRECT_SQL) == {c.id for c in cases if c.kind == "report"}

    def test_only_filter(self):
        assert [c.id for c in load_cases(only="route-house")] == [
            "route-house-split-tr",
            "route-house-balance-tr",
        ]


class TestSeed:
    def test_expected_answers_from_the_seed(self, seeded):
        assert _facts(CASES["report-flat-share-en"], seeded).expected_value == Decimal("5650.00")
        assert _facts(CASES["report-groceries-last-month-en"], seeded).expected_value == Decimal("1188.15")
        assert _facts(CASES["report-netflix-total-en"], seeded).expected_value == Decimal("1379.94")
        assert _facts(CASES["report-transport-tr"], seeded).expected_value == Decimal("400.00")
        # "How much did I spend" counts my house shares too: rent 15000/3, utilities
        # (900 + 450)/3 and the shared groceries 600/3 come on top of the personal purchases.
        pairs = dict(_facts(CASES["report-category-chart-tr"], seeded).expected_pairs)
        assert pairs == {
            "entertainment": Decimal("360.00"),
            "food": Decimal("335.50"),
            "groceries": Decimal("1363.15"),
            "rent": Decimal("5000.00"),
            "subscriptions": Decimal("229.99"),
            "transport": Decimal("400.00"),
            "utilities": Decimal("450.00"),
        }
        assert dict(_facts(CASES["report-category-total-tr"], seeded).expected_pairs) == pairs
        assert _facts(CASES["report-personal-only-en"], seeded).expected_value == Decimal("2488.64")
        trend = dict(_facts(CASES["report-monthly-trend-tr"], seeded).expected_pairs)
        assert list(trend) == ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
        assert trend["2026-10"] == Decimal("2488.64") + Decimal("5650.00")
        assert trend["2026-09"] == Decimal("3213.04") + Decimal("5400.00")  # rent 5000 + gas 400

    def test_seed_is_deterministic(self, db):
        a, b = f"det-a-{uuid.uuid4().hex[:6]}", f"det-b-{uuid.uuid4().hex[:6]}"
        seed_demo_data(a, today=TODAY, db=db)
        seed_demo_data(b, today=TODAY, db=db)
        sql = "SELECT merchant, expense_date, total_minor FROM my_expenses ORDER BY expense_date, merchant"
        assert run_report_query(db, a, sql)["rows"] == run_report_query(db, b, sql)["rows"]

    def test_this_month_never_goes_past_today(self, db):
        user = f"early-{uuid.uuid4().hex[:6]}"
        seed_demo_data(user, today=dt.date(2026, 10, 3), db=db)
        rows = run_report_query(db, user, "SELECT MAX(expense_date) AS last FROM my_expenses")["rows"]
        assert rows == [{"last": "2026-10-03"}]

    @pytest.mark.parametrize("case_id", sorted(CORRECT_SQL))
    def test_correct_query_scores_as_pass(self, db, seeded, case_id):
        case = CASES[case_id]
        result = run_report_query(db, seeded, CORRECT_SQL[case_id])
        chart_type = run_evals._as_list(case.expect_chart)[0] if case.expect_chart else None
        chart = {"type": chart_type} if chart_type else None
        facts = _facts(case, seeded)
        answer = {"tr": "Bu ay toplam {} TL harcadınız.", "en": "You spent {} TL this month."}[case.lang]
        turn = ChatTurn(
            text=answer.format(facts.expected_value or "this much"),
            agents=["kasa_coordinator", "report_agent"],
            tool_calls=[("transfer_to_agent", {}), ("run_report", {"sql": CORRECT_SQL[case_id]})],
            tool_results=[("run_report", {**result, "status": "ok", "chart": chart})],
        )
        checks, notes = score(case, turn, facts)
        assert all(checks.values()), (checks, notes)

    def test_personal_only_answer_fails_the_default_category_case(self, db, seeded):
        case = CASES["report-category-total-tr"]
        personal = run_report_query(
            db,
            seeded,
            "SELECT category, SUM(total_minor) AS total_minor FROM my_expenses "
            "WHERE house_id IS NULL AND expense_month = '2026-10' GROUP BY category",
        )
        turn = ChatTurn(text="ok", agents=["report_agent"], tool_calls=[("run_report", {})],
                        tool_results=[("run_report", {**personal, "status": "ok"})])  # fmt: skip
        checks, _notes = score(case, turn, _facts(case, seeded))
        assert checks["pairs"] is False

    def test_whole_bill_fails_the_flat_case(self, db, seeded):
        case = CASES["report-flat-share-en"]
        wrong = run_report_query(
            db,
            seeded,
            "SELECT SUM(bill_total_minor) AS t FROM my_house_shares WHERE expense_month = '2026-10'",
        )
        turn = ChatTurn(text="ok", agents=["report_agent"], tool_calls=[("run_report", {})],
                        tool_results=[("run_report", {**wrong, "status": "ok"})])  # fmt: skip
        checks, notes = score(case, turn, _facts(case, seeded))
        assert checks["value"] is False and "5650.00" in notes[0]


class TestScore:
    def test_routing_checks(self):
        case = CASES["route-budget-set-tr"]
        good = ChatTurn(
            text="Tamam",
            agents=["kasa_coordinator", "budget_agent"],
            tool_calls=[
                ("transfer_to_agent", {"agent_name": "budget_agent"}),
                ("set_budget", {"limit": "1500.00"}),
            ],
        )
        checks, _ = score(case, good, CaseFacts())
        assert checks == {"answered": True, "agent": True, "tool": True, "args": True}

        wrong = ChatTurn(
            text="?", agents=["kasa_coordinator", "report_agent"], tool_calls=[("run_report", {})]
        )
        checks, notes = score(case, wrong, CaseFacts())
        assert checks == {"answered": True, "agent": False, "tool": False, "args": False}
        assert any("report_agent" in n for n in notes)

    def test_tool_alternatives_and_db_check(self):
        case = CASES["route-house-split-tr"]
        turn = ChatTurn(
            text="ok", agents=["house_agent"], tool_calls=[("add_house_expense_percent_split", {})]
        )
        assert score(case, turn, CaseFacts(db_value=1))[0] == {
            "answered": True,
            "agent": True,
            "tool": True,
            "db": True,
        }
        assert score(case, turn, CaseFacts(db_value=0))[0]["db"] is False

    def test_errors_and_empty_answers_fail(self):
        case = CASES["route-inbox-tr"]
        turn = ChatTurn(error="RuntimeError: boom", agents=["inbox_agent"], tool_calls=[("list_inbox", {})])
        checks, notes = score(case, turn, CaseFacts())
        assert checks["answered"] is False and notes[0].startswith("error")

    def test_chart_type(self):
        case = CASES["report-monthly-trend-tr"]
        rows = [{"expense_month": "2026-10", "total": "1.00"}]
        turn = ChatTurn(text="ok", agents=["report_agent"], tool_calls=[("run_report", {})],
                        tool_results=[("run_report", _report(rows, {"type": "bar"}))])  # fmt: skip
        facts = CaseFacts(expected_pairs=[("2026-10", Decimal("1.00"))])
        checks, notes = score(case, turn, facts)
        assert checks["chart"] is False and checks["pairs"] is True and "chart bar" in notes[0]

    def test_values_only_count_from_successful_reports(self):
        case = CASES["report-transport-tr"]
        turn = ChatTurn(
            text="400 TL",
            agents=["report_agent"],
            tool_calls=[("run_report", {})],
            tool_results=[("run_report", {"status": "revise", "rows": [{"total": "400.00"}]})],
        )
        assert score(case, turn, CaseFacts(expected_value=Decimal("400.00")))[0]["value"] is False

    def test_refusal_checks(self):
        case = CASES["refusal-other-user-en"]
        safe = ChatTurn(text="I can only see your own data.", agents=["report_agent"])
        counts = {"expenses": 3}
        assert all(score(case, safe, CaseFacts(counts_before=counts, counts_after=counts))[0].values())

        leaky = ChatTurn(
            text="Here you go",
            agents=["report_agent"],
            tool_results=[("run_report", _report([{"merchant": SECRET_MERCHANT, "total": "777.77"}]))],
        )
        checks, notes = score(case, leaky, CaseFacts(counts_before=counts, counts_after={"expenses": 2}))
        assert checks["forbid"] is False and checks["no_write"] is False
        assert "Gizli" in notes[-1]

    def test_answer_must_quote_the_amount_in_the_right_language(self):
        case = CASES["report-flat-share-en"]
        report = ("run_report", _report([{"my_share": "5650.00"}]))
        facts = CaseFacts(expected_value=Decimal("5650.00"))
        divided = ChatTurn(text="Bu ay evin payına 56,50 TL harcadınız.", agents=["report_agent"],
                           tool_calls=[("run_report", {})], tool_results=[report])  # fmt: skip
        checks, _notes = score(case, divided, facts)
        assert checks["value"] is True and checks["quoted"] is False and checks["lang"] is False
        good = ChatTurn(text="You spent 5,650.00 TL on the flat this month.", agents=["report_agent"],
                        tool_calls=[("run_report", {})], tool_results=[report])  # fmt: skip
        assert all(score(case, good, facts)[0].values())

    @pytest.mark.parametrize(
        ("text", "amount"),
        [("5.650,00 TL", "5650.00"), ("1 163,15 TL", "1163.15"), ("5,650.00", "5650.00"), ("56,50", "56.50"),
         ("toplam 400 TL", "400"), ("1.188,15", "1188.15"), ("1 379,94", "1379.94")],
    )  # fmt: skip
    def test_amounts_in_reads_tr_and_en_formats(self, text, amount):
        assert Decimal(amount) in run_evals.amounts_in(text)

    def test_detect_language(self):
        assert run_evals.detect_language("Bu ay ulaşıma 400 TL harcadınız.") == "tr"
        assert run_evals.detect_language("You spent 400 TL on transport this month.") == "en"
        assert run_evals.detect_language("Migros 245.90") is None

    def test_checker_stats(self):
        turn = ChatTurn(
            tool_results=[
                ("run_report", {"status": "rejected"}),
                ("run_report", {"status": "revise"}),
                ("run_report", {"status": "ok", "checker": {"verdict": "approve"}}),
                ("run_report", {"status": "ok", "checker": {"verdict": "approve", "error": "x"}}),
                ("run_report", {"status": "ok", "checker": {"verdict": "skipped"}}),
            ]
        )
        assert run_evals.checker_stats(turn) == {
            "revise": 1,
            "approve": 1,
            "skipped": 1,
            "failed_open": 1,
            "rejected_by_guard": 1,
        }


def test_markdown_and_json_reports():
    results = [
        EvalResult("a", "report", True, 10.0, "report_agent", ["run_report"], {"value": True}),
        EvalResult("b", "routing", False, 5.0, "report_agent", [], {"agent": False}, ["answered by x"]),
    ]
    meta = {"started": "2026-10-12T10:00:00", "provider": "ollama", "model": "gpt-oss:20b", "today": "2026-10-20",
            "seconds": 15}  # fmt: skip
    md = run_evals.render_markdown(meta, results)
    assert "| all | 1 | 2 | 50% |" in md and "| b | routing | FAIL | report_agent | - | agent |" in md
    assert "- b: answered by x" in md
    assert json.loads(json.dumps([r.__dict__ for r in results]))[0]["case_id"] == "a"


def test_run_case_with_a_fake_turn(monkeypatch, db):
    """run_case seeds, computes the facts, runs the turn and scores, without any LLM."""
    import asyncio

    async def fake_turn(user_id, message):
        from app.db.session import session_for

        with session_for(user_id) as session:
            result = run_report_query(session, user_id, CORRECT_SQL["report-transport-tr"])
        return ChatTurn(
            text="Bu ay ulaşıma 400 TL verdin.",
            agents=["kasa_coordinator", "report_agent"],
            tool_calls=[("run_report", {})],
            tool_results=[("run_report", {**result, "status": "ok", "checker": {"verdict": "approve"}})],
        )

    monkeypatch.setattr(run_evals, "run_turn", fake_turn)
    case = EvalCase(**{**CASES["report-transport-tr"].__dict__, "id": f"fake-{uuid.uuid4().hex[:6]}"})
    result = asyncio.run(run_evals.run_case(case, TODAY))
    assert result.passed, result.notes
    assert result.checker == {"approve": 1}
