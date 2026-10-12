"""Track INGEST parsers against a real LLM. Skipped unless KASA_LIVE_TESTS=1.

    LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://<host>:11434 KASA_LIVE_TESTS=1 \
        pytest tests/test_ingest_live.py -m live -s

Five model runs in total: four fixture emails through the email-parse runner and the
fixture PDF through the statement-parse runner. Each prints what the model produced.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app.config import get_settings
from app.integrations import gmail
from app.services import gmail_sync, statements
from tests.fixtures.ingest_fakes import gmail_fixture

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _needs_provider():
    settings = get_settings()
    if not settings.agents_enabled:
        pytest.skip("no LLM provider configured")
    print(f"\n[provider={settings.llm_provider} chat={settings.chat_model_name}]")


def parse(name: str):
    msg = gmail.message_from_api(gmail_fixture(name))
    start = time.perf_counter()
    outcome = asyncio.run(gmail_sync.parse_email("live-ingest", msg))
    print(
        f"{name}: {outcome.status} {outcome.parsed} {outcome.error or ''} ({time.perf_counter() - start:.1f}s)"
    )
    return outcome


def test_live_trendyol_order():
    outcome = parse("trendyol_order")
    assert outcome.status == "pending"
    assert outcome.parsed.total == "829.80" and outcome.parsed.currency == "TRY"
    assert "trendyol" in statements.fold(outcome.parsed.merchant)


def test_live_card_spend_alert():
    outcome = parse("card_alert")
    assert outcome.status == "pending"
    assert outcome.parsed.total == "412.35"
    assert "migros" in statements.fold(outcome.parsed.merchant)  # "MİGROS".lower() keeps a dot


def test_live_newsletter_is_ignored():
    assert parse("newsletter").status == "ignored"


def test_live_injection_email_is_only_parsed():
    outcome = parse("injection_order")
    # The parser can only submit or ignore; the hidden "Total is 1 TL" must not win.
    assert outcome.status == "pending"
    assert outcome.parsed.total == "245.50"


def test_live_statement_pdf():
    data = (FIXTURES / "statement_card.pdf").read_bytes()
    start = time.perf_counter()
    lines, errors = asyncio.run(statements._parse_pdf("live-ingest", data))
    print(f"statement: {len(lines)} lines, errors={errors} ({time.perf_counter() - start:.1f}s)")
    for line in lines:
        print(
            f"  {line.posted_on} {line.description!r} {line.amount} {line.currency} -> {statements.categorize(line.description)}"
        )
    amounts = sorted(line.amount for line in lines)
    expected = sorted(["412.35", "189.90", "118.40", "684.75", "1249.99", "260.00"])
    assert amounts == expected  # payments and refunds skipped, no "approve" line
