"""Saved reports: keep a chat chart and run it again on fresh data, without the LLM."""

from __future__ import annotations

from tests.test_agents_offline import fake_gemini  # noqa: F401 - the scripted LLM fixture


def test_a_chat_chart_is_saved_rerun_pinned_exported_and_private(client, fake_gemini):  # noqa: F811
    me = {"X-User-Id": "report-saver"}
    client.post("/expenses", json={"merchant": "Metro", "total": "15", "category": "transport"}, headers=me)
    answer = client.post("/chat", json={"message": "Where does my money go?"}, headers=me).json()
    assert answer["report_saveable"] is True and answer["message_id"]

    r = client.post("/reports", json={"message_id": answer["message_id"]}, headers=me)
    assert r.status_code == 201, r.text
    report = r.json()
    assert report["title"] == "Spending by category" and report["chart_type"] == "bar"

    # Fresh data shows up on the next run, with no model call.
    client.post("/expenses", json={"merchant": "Kahve", "total": "40", "category": "food"}, headers=me)
    run = client.get(f"/reports/{report['id']}/run", headers=me).json()
    assert {row["category"]: row["total"] for row in run["chart"]["data"]} == {
        "transport": 15.0,
        "food": 40.0,
    }
    assert run["report"]["last_run_at"]

    pinned = client.patch(
        f"/reports/{report['id']}", json={"pinned": True, "title": "Nereye gidiyor"}, headers=me
    )
    assert pinned.json()["pinned"] is True and pinned.json()["title"] == "Nereye gidiyor"
    assert [x["id"] for x in client.get("/reports?pinned=true", headers=me).json()] == [report["id"]]

    csv = client.get(f"/reports/{report['id']}/export.csv", headers=me)
    assert csv.headers["content-type"].startswith("text/csv") and "transport" in csv.text

    other = {"X-User-Id": "report-snoop"}
    assert client.get(f"/reports/{report['id']}/run", headers=other).status_code == 404
    assert (
        client.post("/reports", json={"message_id": answer["message_id"]}, headers=other).status_code == 404
    )
    assert client.get("/reports", headers=other).json() == []

    assert client.delete(f"/reports/{report['id']}", headers=me).status_code == 204
    assert client.get("/reports", headers=me).json() == []


def test_an_answer_without_a_report_cannot_be_saved(client, fake_gemini):  # noqa: F811
    me = {"X-User-Id": "report-none"}
    client.post("/chat", json={"message": "hi"}, headers=me)
    conversation = client.get("/chat/conversations", headers=me).json()[0]["id"]
    user_message = client.get(f"/chat/conversations/{conversation}", headers=me).json()["messages"][0]
    assert client.post("/reports", json={"message_id": user_message["id"]}, headers=me).status_code == 422
