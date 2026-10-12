"""End-to-end flows against a real LLM (Gemini or Ollama). Skipped unless KASA_LIVE_TESTS=1.

    # Ollama (dev): LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://<host>:11434
    # Gemini:       LLM_PROVIDER=gemini GOOGLE_API_KEY=...
    KASA_LIVE_TESTS=1 pytest -m live -s

Each test prints its latency and the agents that spoke. Keep the suite small: on a shared
Ollama server every test is several model calls.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import clock

pytestmark = pytest.mark.live

RECEIPT_PNG = Path(__file__).parent / "fixtures" / "receipt_market.png"


@pytest.fixture(autouse=True)
def _needs_provider():
    settings = get_settings()
    if not settings.agents_enabled:
        pytest.skip("no LLM provider configured (GOOGLE_API_KEY or LLM_PROVIDER=ollama + OLLAMA_BASE_URL)")
    print(
        f"\n[provider={settings.llm_provider} chat={settings.chat_model_name} vision={settings.vision_model_name}]"
    )


def _user(prefix: str) -> dict[str, str]:
    return {"X-User-Id": f"{prefix}-{uuid.uuid4().hex[:8]}"}


def _timed(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def test_live_chat_report_by_category_with_chart(client):
    user = _user("live-report")
    today = clock.today().isoformat()
    for merchant, total, category in [
        ("Migros", "250.00", "groceries"),
        ("BİM", "120.50", "groceries"),
        ("Kahve Dünyası", "85.00", "food"),
        ("İstanbulkart", "60.00", "transport"),
    ]:
        r = client.post(
            "/expenses",
            json={"merchant": merchant, "total": total, "category": category, "expense_date": today},
            headers=user,
        )
        assert r.status_code == 201, r.text

    r, seconds = _timed(
        client.post,
        "/chat",
        json={"message": "Bu ay kategoriye göre ne kadar harcadım? Grafik çiz"},
        headers=user,
    )
    body = r.json()
    print(f"report flow: {seconds:.1f}s agent={body.get('agent')} text={body.get('text')!r}")
    assert r.status_code == 200, r.text
    assert body["agent"] == "report_agent"
    assert body["chart"] is not None, "report agent did not return a chart"
    values = {row[body["chart"]["x"]]: row[body["chart"]["y"]] for row in body["chart"]["data"]}
    assert values == {"groceries": 370.5, "food": 85.0, "transport": 60.0}


def test_live_chat_house_equal_split(client):
    owner = _user("live-ali")
    house = client.post("/houses", json={"name": "Moda evi"}, headers=owner).json()
    suffix = owner["X-User-Id"].rsplit("-", 1)[1]
    for name, display in (("ayse", "Ayşe"), ("mehmet", "Mehmet")):
        r = client.post(
            f"/houses/{house['id']}/members",
            json={"user_id": f"live-{name}-{suffix}", "display_name": display},
            headers=owner,
        )
        assert r.status_code == 201

    r, seconds = _timed(
        client.post,
        "/chat",
        json={"message": "Evdeki 300 TL'lik internet faturasını ben ödedim, 3 kişi arasında eşit bölüştür."},
        headers=owner,
    )
    body = r.json()
    print(f"house flow: {seconds:.1f}s agent={body.get('agent')} text={body.get('text')!r}")
    assert r.status_code == 200, r.text
    assert body["agent"] == "house_agent"
    expenses = client.get(f"/houses/{house['id']}/expenses", headers=owner).json()
    assert len(expenses) == 1, expenses
    assert expenses[0]["total_minor"] == 30000
    assert expenses[0]["owner_id"] == owner["X-User-Id"]
    assert sorted(s["amount_minor"] for s in expenses[0]["shares"]) == [10000, 10000, 10000]


def test_live_receipt_image(client):
    user = _user("live-receipt")
    with RECEIPT_PNG.open("rb") as f:
        r, seconds = _timed(
            client.post, "/receipts", files={"file": ("receipt.png", f.read(), "image/png")}, headers=user
        )
    body = r.json()
    print(f"receipt flow: {seconds:.1f}s response={body!r}"[:600])
    assert r.status_code == 201, r.text
    expense = body["expense"]
    assert expense["total"] == "239.35"
    assert expense["currency"] == "TRY"
    assert expense["expense_date"] == "2026-10-05"
    assert "ZDEM" in expense["merchant"].upper()
    assert expense["category"] == "groceries"
    assert len(expense["items"]) == 5
