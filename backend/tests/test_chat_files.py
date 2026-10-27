"""Chat with an attached spreadsheet, streaming and cards, through the real ADK wiring with a
scripted fake LLM (no provider needed)."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator

import pytest
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

from app.agents import common, runtime
from app.config import get_settings
from app.services import sheets

CSV = (
    "Tarih;Açıklama;Tutar;Kategori\n"
    "01.10.2026;Migros;-245,90;market\n"
    "02.10.2026;Maaş;15.000,00;gelir\n"
    "03.10.2026;Starbucks;-89,50;kahve\n"
    "04.10.2026;Migros;-100,10;market\n"
).encode()


def _text(request: LlmRequest) -> str:
    return "\n".join(p.text or "" for c in request.contents for p in c.parts or [] if p.text)


class FileLlm(BaseLlm):
    """Routes to file_agent, then queries or prepares an import depending on the question."""

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1]
        tools = llm_request.tools_dict
        file_id = (re.search(r"file_id=(\w+)", _text(llm_request)) or [None, ""])[1]
        if last.function_response is not None:
            part = types.Part(text=f"done: {last.function_response.response.get('status')}")
        elif "query_file" in tools and "kaydet" in _text(llm_request).lower():
            args = {
                "file_id": file_id,
                "date_column": "Tarih",
                "description_column": "Açıklama",
                "amount_column": "Tutar",
            }
            part = types.Part(function_call=types.FunctionCall(name="prepare_expense_import", args=args))
        elif "query_file" in tools:
            args = {
                "file_id": file_id,
                "sql": 'SELECT "Kategori", SUM("Tutar") AS total FROM data WHERE "Tutar" < 0 GROUP BY 1 ORDER BY 2',
                "chart_type": "bar",
                "x": "Kategori",
                "y": "total",
                "title": "Kategoriye göre",
            }
            part = types.Part(function_call=types.FunctionCall(name="query_file", args=args))
        elif "save_expense" in tools:
            args = {"merchant": "Simit Sarayı", "total": "45", "from_receipt": False}
            part = types.Part(function_call=types.FunctionCall(name="save_expense", args=args))
        else:
            target = "file_agent" if "attached_files" in _text(llm_request) else "receipt_agent"
            part = types.Part(
                function_call=types.FunctionCall(name="transfer_to_agent", args={"agent_name": target})
            )
        yield LlmResponse(content=types.Content(role="model", parts=[part]))


@pytest.fixture
def fake_llm(monkeypatch):
    monkeypatch.setattr(common, "build_model", lambda name, vision=False: FileLlm(model=f"scripted-{name}"))
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    runtime._runner.cache_clear()
    sheets.uploads.clear()
    sheets.drafts.clear()
    yield
    runtime._runner.cache_clear()


def _attach(client, user: str) -> str:
    r = client.post("/chat/files", files={"file": ("ekim.csv", CSV, "text/csv")}, headers={"X-User-Id": user})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["sheets"] == [
        {"name": "Sheet1", "rows": 4, "columns": ["Tarih", "Açıklama", "Tutar", "Kategori"]}
    ]
    return body["file_id"]


def test_question_about_an_attached_file_returns_a_chart(client, fake_llm):
    user = "file-chat"
    file_id = _attach(client, user)
    r = client.post(
        "/chat",
        json={"message": "Bu dosyada en çok neye harcamışım?", "file_ids": [file_id]},
        headers={"X-User-Id": user},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["agent"] == "file_agent"
    assert body["chart"]["type"] == "bar" and body["chart"]["title"] == "Kategoriye göre"
    assert body["chart"]["data"] == [
        {"Kategori": "market", "total": -346.0},
        {"Kategori": "kahve", "total": -89.5},
    ]


def test_import_from_a_file_needs_the_users_confirmation(client, fake_llm):
    user = "file-import"
    file_id = _attach(client, user)
    r = client.post(
        "/chat",
        json={"message": "Bunları harcamalarıma kaydet", "file_ids": [file_id]},
        headers={"X-User-Id": user},
    )
    [card] = r.json()["cards"]
    assert card["kind"] == "import"
    preview = card["data"]
    assert preview["count"] == 3 and preview["totals"] == [{"currency": "TRY", "total": "435.50"}]
    # Nothing is saved yet.
    assert client.get("/inbox", headers={"X-User-Id": user}).json() == []

    # Another user cannot confirm it.
    other = client.post(f"/chat/imports/{preview['draft_id']}", headers={"X-User-Id": "intruder"})
    assert other.status_code == 404

    ok = client.post(f"/chat/imports/{preview['draft_id']}", headers={"X-User-Id": user})
    assert ok.json() == {"created": 3, "duplicates": 0}
    items = client.get("/inbox", headers={"X-User-Id": user}).json()
    assert {i["title"] for i in items} == {"Migros", "Starbucks"} and len(items) == 3
    # The draft is used up.
    assert client.post(f"/chat/imports/{preview['draft_id']}", headers={"X-User-Id": user}).status_code == 404


def test_stream_shows_agents_and_tools_then_the_reply_with_a_card(client, fake_llm):
    r = client.post(
        "/chat/stream", json={"message": "45 TL simit aldım"}, headers={"X-User-Id": "stream-user"}
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-ndjson")
    lines = [json.loads(line) for line in r.text.splitlines() if line]
    kinds = [(e["type"], e.get("agent") or e.get("name")) for e in lines[:-1]]
    assert ("agent", "receipt_agent") in kinds
    assert ("tool", "save_expense") in kinds and ("tool_done", "save_expense") in kinds
    final = lines[-1]
    assert final["type"] == "final"
    [card] = final["reply"]["cards"]
    assert card["kind"] == "expense" and card["data"]["merchant"] == "Simit Sarayı"
    assert card["data"]["total"] == "45.00" and card["data"]["house"] is False


def test_chat_files_reject_other_types_and_expired_ids(client, fake_llm):
    r = client.post(
        "/chat/files", files={"file": ("photo.png", b"\x89PNG", "image/png")}, headers={"X-User-Id": "u"}
    )
    assert r.status_code == 415
    # An unknown file id is passed on as expired, and the turn still works.
    r = client.post(
        "/chat", json={"message": "what is in it?", "file_ids": ["deadbeef"]}, headers={"X-User-Id": "u"}
    )
    assert r.status_code == 200


def test_reply_language_follows_the_ui_when_the_message_is_neutral():
    from app.agents.language import reply_language_note

    assert reply_language_note("Netflix?", "tr") == "(Kasa: reply in Turkish.)"
    assert reply_language_note("Netflix?", None) == "(Kasa: reply in English.)"
    assert reply_language_note("How much did I spend?", "tr") == "(Kasa: reply in English.)"
    assert reply_language_note("bu ay ne kadar harcadim", "en") == "(Kasa: reply in Turkish.)"


def test_conversations_are_saved_listed_reopened_and_private(client, fake_llm):
    user = {"X-User-Id": "history-user"}
    first = client.post("/chat", json={"message": "45 TL simit aldım"}, headers=user).json()
    cid = first["conversation_id"]
    assert cid and first["message_id"]
    again = client.post(
        "/chat", json={"message": "bir tane daha", "conversation_id": cid}, headers=user
    ).json()
    assert again["conversation_id"] == cid

    [listed] = client.get("/chat/conversations", headers=user).json()
    assert (listed["id"], listed["title"], listed["message_count"]) == (cid, "45 TL simit aldım", 4)

    detail = client.get(f"/chat/conversations/{cid}", headers=user).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    answer = detail["messages"][1]
    assert answer["agent"] == "receipt_agent" and answer["cards"][0]["kind"] == "expense"

    # Card state survives a reload.
    r = client.put(
        f"/chat/messages/{answer['id']}/cards/0", json={"state": {"status": "undone"}}, headers=user
    )
    assert r.status_code == 204
    detail = client.get(f"/chat/conversations/{cid}", headers=user).json()
    assert detail["messages"][1]["card_state"] == {"0": {"status": "undone"}}

    # Someone else sees nothing and can change nothing.
    other = {"X-User-Id": "history-intruder"}
    assert client.get("/chat/conversations", headers=other).json() == []
    assert client.get(f"/chat/conversations/{cid}", headers=other).status_code == 404
    assert client.delete(f"/chat/conversations/{cid}", headers=other).status_code == 404
    assert (
        client.post("/chat", json={"message": "hi", "conversation_id": cid}, headers=other).status_code == 404
    )

    assert (
        client.patch(f"/chat/conversations/{cid}", json={"title": "Kahve"}, headers=user).json()["title"]
        == "Kahve"
    )
    assert client.delete(f"/chat/conversations/{cid}", headers=user).status_code == 204
    assert client.get("/chat/conversations", headers=user).json() == []


def test_a_lost_agent_session_gets_the_saved_history_replayed(client, fake_llm, monkeypatch):
    user = {"X-User-Id": "replay-user"}
    cid = client.post("/chat", json={"message": "45 TL simit aldım"}, headers=user).json()["conversation_id"]
    seen: list[str] = []
    real = runtime.stream_agent

    async def spy(kind, user_id, parts, session_id=None, new_session_parts=None):
        seen.extend(p.text for p in new_session_parts or [])
        async for item in real(kind, user_id, parts, "gone-after-restart", new_session_parts):
            yield item

    monkeypatch.setattr(runtime, "stream_agent", spy)
    client.post("/chat", json={"message": "ne kaydettin?", "conversation_id": cid}, headers=user)
    [replay] = seen
    assert "<earlier_conversation>" in replay and "User: 45 TL simit aldım" in replay
