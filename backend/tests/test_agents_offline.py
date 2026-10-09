"""Exercise the real ADK wiring (Runner, sessions, transfer, function tools, ToolContext)
with a scripted fake LLM, so /receipts and /chat are tested without a Gemini key."""

from collections.abc import AsyncGenerator

import pytest
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from app.agents import budget_agent, coordinator, house_agent, receipt_agent, report_agent, runtime
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
    for module in (receipt_agent, house_agent, report_agent, budget_agent, coordinator):
        monkeypatch.setattr(module, "gemini_model", lambda: ScriptedLlm(model="scripted"))
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
