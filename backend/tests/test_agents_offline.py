"""Exercise the real ADK wiring (Runner, sessions, transfer, function tools, ToolContext)
with a scripted fake LLM, so /receipts and /chat are tested without any LLM provider."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from app.agents import common, runtime
from app.config import get_settings

RECEIPT_CALL = {
    "merchant": "Migros",
    "total": "57.50",
    "expense_date": "2026-10-02",
    "currency": "TL",
    "category": "groceries",
    "items": [{"description": "Ayran", "amount": "17.50"}, {"description": "Simit", "amount": "40"}],
}
REPORT_CALL = {
    "sql": "SELECT category, SUM(total_minor) AS total_minor FROM my_expenses GROUP BY category",
    "chart_type": "bar",
    "x": "category",
    "y": "total_minor",
    "title": "Spending by category",
}


class ScriptedLlm(BaseLlm):
    """Calls the obvious tool for whichever agent is asking, then answers with text."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1] if llm_request.contents else None
        tools = llm_request.tools_dict
        if last is not None and last.function_response is not None:
            part = types.Part(text=f"done: {last.function_response.response.get('status')}")
        elif "save_expense" in tools:
            part = types.Part(function_call=types.FunctionCall(name="save_expense", args=RECEIPT_CALL))
        elif "run_report" in tools:
            part = types.Part(function_call=types.FunctionCall(name="run_report", args=REPORT_CALL))
        else:
            part = types.Part(
                function_call=types.FunctionCall(
                    name="transfer_to_agent", args={"agent_name": "report_agent"}
                )
            )
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


@pytest.fixture
def fake_gemini(monkeypatch):
    monkeypatch.setattr(
        common, "build_model", lambda name, vision=False: ScriptedLlm(model=f"scripted-{name}")
    )
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    yield
    runtime._runner.cache_clear()


def test_receipt_upload_saves_expense_via_agent(client, fake_gemini):
    r = client.post(
        "/receipts",
        files={"file": ("receipt.jpg", b"\xff\xd8\xff fake jpeg", "image/jpeg")},
        headers={"X-User-Id": "agent-user"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["expense"]["owner_id"] == "agent-user"  # from ToolContext, not the model
    assert body["expense"]["total"] == "57.50" and body["expense"]["currency"] == "TRY"
    assert body["expense"]["source"] == "receipt"
    assert [i["amount_minor"] for i in body["expense"]["items"]] == [1750, 4000]
    assert body["warnings"] == []
    assert body["agent_message"] == "done: saved"


def test_chat_routes_to_report_agent_and_returns_chart(client, fake_gemini):
    client.post(
        "/expenses",
        json={"merchant": "Metro", "total": "15", "category": "transport"},
        headers={"X-User-Id": "agent-user"},
    )
    r = client.post("/chat", json={"message": "Where does my money go?"}, headers={"X-User-Id": "agent-user"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    assert body["agent"] == "report_agent"
    assert body["chart"]["type"] == "bar"
    assert body["chart"]["y"] == "total"
    assert {d["category"]: d["total"] for d in body["chart"]["data"]} == {
        "groceries": 57.5,
        "transport": 15.0,
    }

    # The session continues for the same user...
    again = client.post(
        "/chat",
        json={"message": "and again?", "session_id": body["session_id"]},
        headers={"X-User-Id": "agent-user"},
    )
    assert again.json()["session_id"] == body["session_id"]
    # ...but another user can't attach to it.
    other = client.post(
        "/chat", json={"message": "hi", "session_id": body["session_id"]}, headers={"X-User-Id": "intruder"}
    )
    assert other.json()["session_id"] != body["session_id"]
    assert other.json()["chart"]["data"] == []  # intruder has no expenses


class ParserLlm(BaseLlm):
    """Plays the email parser: submits one expense, then stops."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1]
        if last.function_response is not None:
            part = types.Part(text="ok")
        else:
            args = {
                "merchant": "Trendyol",
                "total": "349,9",
                "currency": "TL",
                "expense_date": "2026-10-03",
                "category": "alışveriş",
                "items": [{"description": "Kulaklık", "amount": "349.90"}],
            }
            part = types.Part(function_call=types.FunctionCall(name="submit_parsed_expense", args=args))
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


@pytest.fixture
def fake_parser(monkeypatch):
    monkeypatch.setattr(common, "build_model", lambda name, vision=False: ParserLlm(model="parser"))
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    yield
    runtime._runner.cache_clear()


def test_every_runner_kind_builds(fake_gemini):
    for kind in runtime.RUNNERS:
        assert runtime._runner(kind).agent is not None
    coordinator = runtime._runner("chat").agent
    assert {a.name for a in coordinator.sub_agents} == {
        "receipt_agent",
        "house_agent",
        "report_agent",
        "budget_agent",
        "inbox_agent",
        "file_agent",
    }


@pytest.mark.parametrize(
    "name",
    [
        "kasa_coordinator",
        "receipt_agent",
        "house_agent",
        "report_agent",
        "budget_agent",
        "inbox_agent",
        "file_agent",
    ],
)
def test_every_chat_agent_has_latest_message_language_instruction(fake_gemini, name):
    coordinator = runtime._runner("chat").agent
    agent = next(a for a in [coordinator, *coordinator.sub_agents] if a.name == name)
    instruction = agent.instruction(None)
    assert "Turkish in, Turkish out; English in, English out" in instruction
    assert "(Kasa: reply in Turkish.)" in instruction
    assert "(Kasa: reply in English.)" in instruction
    assert "not a new English user message" in instruction
    assert "instructions, earlier messages, tool results or UI locale" in instruction
    assert "Copy numbers and amounts exactly as tools return them" in instruction


@pytest.mark.parametrize(
    ("message", "locale", "note"),
    [
        ("Bu ay markete ne kadar harcadım?", "en", "(Kasa: reply in Turkish.)"),
        ("How much did I spend on groceries this month?", "tr", "(Kasa: reply in English.)"),
    ],
)
def test_chat_language_note_follows_message_over_ui_locale(message, locale, note):
    from app.api.agents import _message_parts
    from app.schemas.agents import ChatIn

    parts = _message_parts(ChatIn(message=message, locale=locale), "language-test-user")
    assert parts[0].text == message
    assert parts[-1].text == note


def test_email_parse_runner_returns_validated_expense(fake_parser):
    run = asyncio.run(
        runtime.run_agent("email-parse", "parse-user", [types.Part(text="Subject: Siparişiniz alındı")])
    )
    result = run.last_tool_result("submit_parsed_expense")
    assert result == {
        "status": "parsed",
        "expense": {
            "merchant": "Trendyol",
            "total": "349.90",
            "currency": "TRY",
            "expense_date": "2026-10-03",
            "category": "alışveriş",
            "items": [{"description": "Kulaklık", "amount": "349.90", "quantity": "1"}],
        },
    }
    # One-shot runners do not keep sessions around.
    sessions = asyncio.run(
        runtime._session_service().list_sessions(app_name="kasa-email-parse", user_id="parse-user")
    )
    assert sessions.sessions == []
