"""The Gemini model retries rate limits (429) instead of failing the chat turn (US-ASK-06)."""

from google.adk.models import Gemini

from app.agents import common
from app.config import Settings


def test_gemini_model_retries_rate_limits(monkeypatch):
    monkeypatch.setattr(
        common, "get_settings", lambda: Settings(llm_provider="gemini", google_api_key="test")
    )

    model = common.build_model("gemini-3.5-flash-lite")

    assert isinstance(model, Gemini)
    retry = model.retry_options
    assert retry is not None
    assert 429 in retry.http_status_codes
    assert retry.attempts >= 5
    # The waits must add up to about a minute, the window of the free tier's per-minute quota.
    waits = [min(retry.initial_delay * retry.exp_base**i, retry.max_delay) for i in range(retry.attempts - 1)]
    assert sum(waits) >= 55


def test_vision_model_retries_too(monkeypatch):
    monkeypatch.setattr(
        common, "get_settings", lambda: Settings(llm_provider="gemini", google_api_key="test")
    )

    model = common.build_model("gemini-3.5-flash-lite", vision=True)

    assert model.retry_options is common.GEMINI_RETRY
