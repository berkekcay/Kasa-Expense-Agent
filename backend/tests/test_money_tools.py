"""Track MONEY: budget agent tools with a fake ToolContext, and the coordinator routing to
the budget agent with a scripted LLM (no provider, no network)."""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncGenerator
from decimal import Decimal
from types import SimpleNamespace

import pytest
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from app.agents import common, runtime
from app.agents.tools import budget_tools
from app.config import get_settings
from app.db.models import Expense, FxRate
from app.db.session import init_db, session_for
from app.integrations import tcmb
from app.services import budgets, clock
from app.services.expenses import ExpenseInput, add_expense


def ctx(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id)


@pytest.fixture(autouse=True)
def _db_and_no_network(monkeypatch):
    init_db()

    def refuse(url, timeout):
        raise AssertionError(f"unexpected TCMB request {url}")

    monkeypatch.setattr(tcmb, "_http_get", refuse)


def test_set_budget_and_status_tools():
    user = "tool-budget"
    with session_for(user) as db:
        add_expense(db, user, ExpenseInput("Migros", "2550.75", category="market"))

    r = budget_tools.set_budget("3000", ctx(user), category="Market")
    assert r["status"] == "saved"
    assert (r["category"], r["limit"], r["currency"], r["alert_threshold_pct"]) == (
        "groceries",
        "3000.00",
        "TRY",
        80,
    )
    assert r["this_month"]["summary"] == "groceries: 2,550.75 of 3,000.00 TRY spent (85%), 449.25 TRY left"
    assert r["this_month"]["level"] == "warning"

    assert budget_tools.set_budget("5000", ctx(user))["category"] == "overall"
    r = budget_tools.get_budget_status(ctx(user))
    assert r["status"] == "ok" and r["month"] == f"{clock.today():%Y-%m}"
    assert [(b["category"], b["spent"], b["remaining"], b["pct_used"]) for b in r["budgets"]] == [
        ("overall", "2550.75", "2449.25", 51),
        ("groceries", "2550.75", "449.25", 85),
    ]
    last = budgets.add_months(budgets.month_start(clock.today()), -1)
    old = budget_tools.get_budget_status(ctx(user), month=last.isoformat())
    assert [b["spent"] for b in old["budgets"]] == ["0.00", "0.00"]


def test_budget_tool_errors_are_data():
    user = "tool-errors"
    assert budget_tools.set_budget("abc", ctx(user), category="food")["status"] == "error"
    r = budget_tools.set_budget("100", ctx(user), category="uzay gemisi")
    assert r["status"] == "error" and "unknown category" in r["error"]
    assert budget_tools.set_budget("100", ctx(user), alert_threshold_pct=150)["status"] == "error"
    assert budget_tools.get_budget_status(ctx(user), month="June")["status"] == "error"
    assert budget_tools.get_budget_status(ctx(user))["status"] == "no_budgets"


def test_tools_use_the_context_user_only():
    budget_tools.set_budget("100", ctx("tool-owner"), category="food")
    assert budget_tools.get_budget_status(ctx("tool-stranger"))["status"] == "no_budgets"


def test_list_subscriptions_tool():
    user = "tool-subs"
    today = clock.today()
    with session_for(user) as db:
        from app.services.expenses import ensure_user
        from app.services.subscriptions import add_months

        ensure_user(db, user)
        for k in (-3, -2, -1, 0):
            day = add_months(today - dt.timedelta(days=3), k)
            db.add(
                Expense(
                    owner_id=user,
                    merchant="NETFLIX.COM 77",
                    expense_date=day,
                    currency="TRY",
                    total_minor=22999,
                )
            )
        db.commit()
    assert budget_tools.list_subscriptions(ctx("tool-subs-empty"))["status"] == "none"
    r = budget_tools.list_subscriptions(ctx(user))
    assert r["status"] == "ok"
    [sub] = r["subscriptions"]
    assert (sub["name"], sub["amount"], sub["currency"], sub["period"]) == (
        "NETFLIX.COM 77",
        "229.99",
        "TRY",
        "monthly",
    )
    assert sub["next_expected_date"] == add_months(today - dt.timedelta(days=3), 1).isoformat()
    assert budget_tools.list_subscriptions(ctx(user), refresh=False)["subscriptions"] == r["subscriptions"]


def test_convert_currency_tool(monkeypatch):
    day = dt.date(2025, 11, 14)
    monkeypatch.setattr(clock, "today", lambda: day)
    with session_for(None) as db:
        db.add(FxRate(rate_date=day, currency="EUR", try_per_unit=Decimal("49.123400")))
        db.commit()
    r = budget_tools.convert_currency("50", "eur", ctx("tool-fx"))
    assert r == {
        "status": "ok",
        "amount": "50.00",
        "from_currency": "EUR",
        "converted": "2456.17",
        "to_currency": "TRY",
        "rate": "49.1234",
        "rate_date": "2025-11-14",
        "summary": "50.00 EUR = 2,456.17 TRY (TCMB rate 49.1234, 2025-11-14)",
    }
    assert budget_tools.convert_currency("0", "EUR", ctx("tool-fx"))["status"] == "error"
    assert budget_tools.convert_currency("10", "EURO", ctx("tool-fx"))["status"] == "error"
    assert (
        budget_tools.convert_currency("10", "EUR", ctx("tool-fx"), on_date="14/11/2025")["status"] == "error"
    )


# --- ADK wiring with a scripted model -----------------------------------------------------


class BudgetScriptLlm(BaseLlm):
    """Coordinator: transfer to budget_agent. Budget agent: call set_budget, then answer."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1] if llm_request.contents else None
        tools = llm_request.tools_dict
        if last is not None and last.function_response is not None:
            result = last.function_response.response
            part = types.Part(text=f"{result.get('status')}: {result.get('this_month', {}).get('summary')}")
        elif "set_budget" in tools:
            args = {"limit": "3000", "category": "market"}
            part = types.Part(function_call=types.FunctionCall(name="set_budget", args=args))
        else:
            args = {"agent_name": "budget_agent"}
            part = types.Part(function_call=types.FunctionCall(name="transfer_to_agent", args=args))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(common, "build_model", lambda name, vision=False: BudgetScriptLlm(model="scripted"))
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    yield
    runtime._runner.cache_clear()


def test_chat_routes_to_budget_agent_and_saves_for_the_caller(client, scripted):
    r = client.post(
        "/chat",
        json={"message": "Market kategorisi için aylık 3000 TL bütçe koy"},
        headers={"X-User-Id": "tool-chat"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["agent"] == "budget_agent"
    assert body["text"] == "saved: groceries: 0.00 of 3,000.00 TRY spent (0%), 3,000.00 TRY left"
    with session_for("tool-chat") as db:
        [budget] = budgets.list_budgets(db, "tool-chat")
        assert (budget.category, budget.limit_minor) == ("groceries", 300000)
