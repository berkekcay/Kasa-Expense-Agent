"""Parser tools (track INGEST) accept the shapes real models send, and the PDF parser
retries once when a local model emits a broken tool call."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agents import runtime
from app.agents.tools.inbox_tools import (
    ParsedLine,
    StatementLineArg,
    submit_parsed_expense,
    submit_statement_lines,
)
from app.config import get_settings
from app.services import statements
from app.services.errors import UpstreamError

CTX = SimpleNamespace(user_id="parser-tools")
PDF = (Path(__file__).parent / "fixtures" / "statement_card.pdf").read_bytes()


def test_items_in_any_shape_and_turkish_amounts():
    result = submit_parsed_expense(
        "Trendyol",
        "829,80 TL",
        CTX,
        currency="tl",
        expense_date="05.10.2026",
        items=[
            ["Kablosuz Kulaklık", "749,90", "1 adet"],  # what gpt-oss sent live
            {"description": "Kupon indirimi", "amount": "-50,00"},  # discounts are dropped
            ParsedLine(description="Şeffaf  Kılıf", amount="1.129,90", quantity="2"),
            "garbage",
        ],
    )
    assert result["status"] == "parsed"
    expense = result["expense"]
    assert (expense["total"], expense["currency"], expense["expense_date"]) == ("829.80", "TRY", "2026-10-05")
    # A dot before three digits groups thousands, as Turkish receipts print it.
    assert submit_parsed_expense("X", "1.005", CTX)["expense"]["total"] == "1005.00"
    assert expense["items"] == [
        {"description": "Kablosuz Kulaklık", "amount": "749.90", "quantity": "1"},
        {"description": "Şeffaf Kılıf", "amount": "1129.90", "quantity": "2"},
    ]


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"merchant": "", "total": "10"}, "merchant is required"),
        ({"merchant": "X", "total": "-5"}, "positive"),
        ({"merchant": "X", "total": "on bin"}, "not a valid amount"),
        ({"merchant": "X", "total": "10", "expense_date": "yesterday"}, "not a date"),
        ({"merchant": "X", "total": "10", "currency": "lira"}, "currency"),
    ],
)
def test_bad_fields_are_reported_not_raised(args, error):
    result = submit_parsed_expense(tool_context=CTX, **args)
    assert result["status"] == "error" and error in result["error"]


def test_statement_lines_tool_is_lenient_but_strict_on_values():
    result = submit_statement_lines(
        [
            StatementLineArg(posted_on="02.09.2026", description="MİGROS  ATAŞEHİR", amount="1.249,99"),
            {"posted_on": "2026-09-04", "description": "YEMEKSEPETİ", "amount": "189.90", "currency": "TL"},
            StatementLineArg(posted_on="2026-09-06", description="ÖDEME", amount="-3.250,00"),
            StatementLineArg(posted_on="2026-09-31", description="BAD", amount="1"),
            StatementLineArg(posted_on="2026-09-07", description="  ", amount="1"),
        ],
        CTX,
    )
    assert [(x["posted_on"], x["description"], x["amount"], x["currency"]) for x in result["lines"]] == [
        ("2026-09-02", "MİGROS ATAŞEHİR", "1249.99", "TRY"),
        ("2026-09-04", "YEMEKSEPETİ", "189.90", "TRY"),
    ]
    assert [r.split(":")[0] for r in result["rejected"]] == ["line 3", "line 4", "line 5"]


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")


def test_pdf_parser_retries_once(provider, monkeypatch):
    attempts = []

    async def flaky(kind, user_id, parts, session_id=None):
        attempts.append(kind)
        if len(attempts) == 1:
            raise RuntimeError("error parsing tool call: unexpected end of JSON input")
        lines = [StatementLineArg(posted_on="2026-09-02", description="MİGROS", amount="412.35")]
        return runtime.AgentRun(
            "s", "", tool_results=[("submit_statement_lines", submit_statement_lines(lines, CTX))]
        )

    monkeypatch.setattr(runtime, "run_agent", flaky)
    lines, errors = asyncio.run(statements._parse_pdf("parser-tools", PDF))
    assert len(attempts) == 2 and [x.amount for x in lines] == ["412.35"] and errors == []


def test_pdf_parser_gives_up_with_a_502(provider, monkeypatch):
    async def down(*args, **kwargs):
        raise ConnectionError("unreachable")

    monkeypatch.setattr(runtime, "run_agent", down)
    with pytest.raises(UpstreamError, match="upload the CSV"):
        asyncio.run(statements._parse_pdf("parser-tools", PDF))
    assert UpstreamError.status_code == 502


def test_pdf_parser_without_tool_call_reports_an_error(provider, monkeypatch):
    async def chatty(*args, **kwargs):
        return runtime.AgentRun("s", "Here are your lines: ...")

    monkeypatch.setattr(runtime, "run_agent", chatty)
    lines, errors = asyncio.run(statements._parse_pdf("parser-tools", PDF))
    assert lines == [] and errors == ["part 1: the parser returned no lines"]
