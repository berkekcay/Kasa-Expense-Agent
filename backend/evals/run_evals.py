"""Run the eval cases in cases.jsonl against the configured LLM provider.

    cd backend
    LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://<host>:11434 python -m evals.run_evals [--only report-]

Every run uses a fresh SQLite file and a frozen "today" (default 2026-10-20), so the data
and the expected answers are the same every time. Each case is one chat turn through the
real coordinator runner, for a fresh user seeded with `seed_demo_data`. Cases run one after
another, never in parallel (a shared Ollama server is slow enough already).

A case passes when every check it asks for passes:
  answered   the turn finished without an exception and produced text
  agent      expect_agent (name or list): the agent that answered last
  tool       expect_tool (name or list): at least one of them was called
  args       expect_args {tool: {arg: value}}: some call of that tool had those values
             (numbers compared as numbers, text case-insensitively)
  chart      expect_chart (type or list): the last chart from run_report has that type
  value      expect_value_sql: SQL over the base tables giving one minor-unit number; some
             cell of a successful run_report result must equal it in major units
  pairs      expect_pairs_sql: SQL giving (label, minor) rows; one successful run_report
             result must contain every pair (a row with the label and the amount)
  db         expect_db_sql + expect_db_value: SQL run after the turn must return that value
  no_write   expect_no_write: row counts of the user data tables did not change
  forbid     forbid_text: none of these strings appear in the answer or any tool result
  quoted     (value cases) the answer text quotes the expected amount, in any TR/EN format
  lang       the answer is in the case's language (lang: tr or en; a word-count heuristic)

The SQL in cases may use :user_id, :this_month, :last_month, :first_month and :this_year.
Results: a table on stdout, evals/results/<timestamp>.json (gitignored) and evals/latest.md.

Owner: track REPORT.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import re
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from evals.seed import seed_demo_data

EVALS_DIR = Path(__file__).parent
CASES = EVALS_DIR / "cases.jsonl"
RESULTS_DIR = EVALS_DIR / "results"
LATEST_MD = EVALS_DIR / "latest.md"
DEFAULT_TODAY = dt.date(2026, 10, 20)
USER_TABLES = ("expenses", "expense_items", "expense_shares", "settlements", "budgets", "subscriptions",
               "houses", "house_members", "inbox_items", "users")  # fmt: skip

__all__ = ["CaseFacts", "ChatTurn", "EvalCase", "EvalResult", "load_cases", "score", "seed_demo_data"]


@dataclass
class EvalCase:
    id: str
    message: str
    kind: str = "routing"  # routing | report | refusal
    lang: str = "en"
    expect_agent: str | list[str] | None = None
    expect_tool: str | list[str] | None = None
    expect_args: dict[str, dict[str, Any]] | None = None
    expect_chart: str | list[str] | None = None
    expect_value_sql: str | None = None
    expect_pairs_sql: str | None = None
    expect_db_sql: str | None = None
    expect_db_value: int | None = None
    expect_no_write: bool = False
    forbid_text: list[str] = field(default_factory=list)


@dataclass
class ChatTurn:
    """What happened in one chat turn (filled from the ADK event stream)."""

    text: str = ""
    agents: list[str] = field(default_factory=list)
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    tool_results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    seconds: float = 0.0
    error: str | None = None

    @property
    def agent(self) -> str | None:
        return self.agents[-1] if self.agents else None

    def results_of(self, name: str) -> list[dict[str, Any]]:
        return [r for n, r in self.tool_results if n == name]


@dataclass
class CaseFacts:
    """Ground truth computed from the seeded database, around the turn."""

    expected_value: Decimal | None = None  # major units
    expected_pairs: list[tuple[str, Decimal]] | None = None
    db_value: Any = None
    counts_before: dict[str, int] | None = None
    counts_after: dict[str, int] | None = None


@dataclass
class EvalResult:
    case_id: str
    kind: str
    passed: bool
    seconds: float
    agent: str | None
    tools: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    checker: dict[str, int] = field(default_factory=dict)
    text: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)  # tool calls and results


def load_cases(path: Path = CASES, only: str | None = None) -> list[EvalCase]:
    cases = [
        EvalCase(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    return [c for c in cases if not only or c.id.startswith(only)]


# --- Scoring (pure, unit tested offline) ---------------------------------------------------


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _same(actual: Any, expected: Any) -> bool:
    a, e = _number(actual), _number(expected)
    if a is not None and e is not None:
        return a == e
    return str(actual).strip().lower() == str(expected).strip().lower()


# Grouped thousands (1.188,15 / 1 163,15 / 5,650.00) or a plain number (5650.00 / 56,50).
_NUMBER = re.compile(r"\d{1,3}(?:[.,   ]\d{3})+(?:[.,]\d{1,2})?(?!\d)|\d+(?:[.,]\d{1,2})?(?!\d)")
_TR_WORDS = frozenset(
    ["bu", "ve", "için", "bir", "ay", "toplam", "olarak", "geçen", "şu", "ile", "ama", "değil",
     "var", "yok", "sadece", "ancak", "maalesef", "üzgünüm", "harcadınız", "harcamanız",
     "harcamalarınız", "kaydedildi", "kaydettim", "oldu", "tl'dir", "borçlu", "kişi", "aylık",
     "sonraki", "kalan", "harcama", "bütçe", "şöyle", "evin", "tarih", "abonelikler"]
)  # fmt: skip
_EN_WORDS = frozenset(
    ["the", "you", "your", "this", "that", "month", "total", "spent", "is", "are", "was", "for",
     "and", "of", "to", "in", "on", "with", "sorry", "can", "only", "i", "i'm", "here", "have",
     "has", "last"]
)  # fmt: skip


def amounts_in(text: str) -> set[Decimal]:
    """Every number in a text, read as Turkish (5.650,00) or English (5,650.00) money."""
    found: set[Decimal] = set()
    for raw in _NUMBER.findall(text or ""):
        token = re.sub(r"[\s  ]", "", raw)
        match = re.fullmatch(r"(.*?)(?:[.,](\d{1,2}))?", token)
        whole, frac = match.group(1), match.group(2) or "0"
        digits = re.sub(r"[.,]", "", whole)
        if digits.isdigit():
            found.add(Decimal(f"{digits}.{frac}"))
    return found


def detect_language(text: str) -> str | None:
    words = re.findall(r"[\wçğıöşüİ']+", (text or "").lower())
    tr, en = sum(w in _TR_WORDS for w in words), sum(w in _EN_WORDS for w in words)
    if tr == en:
        return None
    return "tr" if tr > en else "en"


def _ok_reports(turn: ChatTurn) -> list[dict[str, Any]]:
    return [r for r in turn.results_of("run_report") if r.get("status") == "ok"]


def _has_value(report: dict[str, Any], expected: Decimal) -> bool:
    return any(_number(cell) == expected for row in report.get("rows", []) for cell in row.values())


def _has_pairs(report: dict[str, Any], pairs: list[tuple[str, Decimal]]) -> bool:
    rows = report.get("rows", [])
    for label, amount in pairs:
        if not any(
            any(_same(c, label) for c in row.values() if isinstance(c, str))
            and any(_number(c) == amount for c in row.values())
            for row in rows
        ):
            return False
    return bool(pairs)


def score(case: EvalCase, turn: ChatTurn, facts: CaseFacts) -> tuple[dict[str, bool], list[str]]:
    """Every check the case asks for -> passed?, plus notes explaining failures."""
    checks: dict[str, bool] = {}
    notes: list[str] = []
    called = [n for n, _ in turn.tool_calls if n != "transfer_to_agent"]

    checks["answered"] = turn.error is None and bool(turn.text.strip())
    if turn.error:
        notes.append(f"error: {turn.error}")

    if agents := _as_list(case.expect_agent):
        checks["agent"] = turn.agent in agents
        if not checks["agent"]:
            notes.append(f"answered by {turn.agent}, expected {'/'.join(agents)}")
    if tools := _as_list(case.expect_tool):
        checks["tool"] = any(t in called for t in tools)
        if not checks["tool"]:
            notes.append(f"tools called: {called or 'none'}")
    for tool, wanted in (case.expect_args or {}).items():
        calls = [args for n, args in turn.tool_calls if n == tool]
        checks["args"] = any(all(_same(args.get(k), v) for k, v in wanted.items()) for args in calls)
        if not checks["args"]:
            notes.append(f"{tool} args were {calls}")
    if charts := _as_list(case.expect_chart):
        drawn = [r["chart"]["type"] for r in _ok_reports(turn) if r.get("chart")]
        checks["chart"] = bool(drawn) and drawn[-1] in charts
        if not checks["chart"]:
            notes.append(f"chart {drawn[-1] if drawn else 'none'}, expected {'/'.join(charts)}")
    if case.expect_value_sql:
        expected = facts.expected_value
        checks["value"] = expected is not None and any(_has_value(r, expected) for r in _ok_reports(turn))
        if not checks["value"]:
            notes.append(f"expected {expected}; got {[r.get('rows') for r in _ok_reports(turn)][-1:]}")
    if case.expect_pairs_sql:
        pairs = facts.expected_pairs or []
        checks["pairs"] = any(_has_pairs(r, pairs) for r in _ok_reports(turn))
        if not checks["pairs"]:
            notes.append(f"expected {[(k, str(v)) for k, v in pairs]}")
    if case.expect_db_sql:
        checks["db"] = facts.db_value == case.expect_db_value
        if not checks["db"]:
            notes.append(f"db check returned {facts.db_value}, expected {case.expect_db_value}")
    if case.expect_no_write:
        checks["no_write"] = facts.counts_before == facts.counts_after
        if not checks["no_write"]:
            notes.append(f"row counts changed: {facts.counts_before} -> {facts.counts_after}")
    if case.expect_value_sql and facts.expected_value is not None:
        checks["quoted"] = facts.expected_value in amounts_in(turn.text)
        if not checks["quoted"]:
            notes.append(f"answer does not quote {facts.expected_value}: {turn.text[:120]!r}")
    if turn.text.strip() and (detected := detect_language(turn.text)) is not None:
        checks["lang"] = detected == case.lang
        if not checks["lang"]:
            notes.append(f"answered in {detected}, asked in {case.lang}")
    if case.forbid_text:
        haystack = (turn.text + json.dumps([r for _, r in turn.tool_results], ensure_ascii=False)).lower()
        leaked = [s for s in case.forbid_text if s.lower() in haystack]
        checks["forbid"] = not leaked
        if leaked:
            notes.append(f"leaked: {leaked}")
    return checks, notes


def checker_stats(turn: ChatTurn) -> dict[str, int]:
    """How the SQL checker behaved in this turn (revise loops, fail-open, skips)."""
    stats = {"revise": 0, "approve": 0, "skipped": 0, "failed_open": 0, "rejected_by_guard": 0}
    for result in turn.results_of("run_report"):
        status = result.get("status")
        if status == "revise":
            stats["revise"] += 1
        elif status == "rejected":
            stats["rejected_by_guard"] += 1
        elif status == "ok":
            checker = result.get("checker") or {}
            if checker.get("verdict") == "skipped":
                stats["skipped"] += 1
            elif checker.get("error"):
                stats["failed_open"] += 1
            else:
                stats["approve"] += 1
    return {k: v for k, v in stats.items() if v}


# --- Running against the real runner -------------------------------------------------------


def month_params(today: dt.date, user_id: str) -> dict[str, str]:
    from app.agents.checker_agent import month_facts

    facts = month_facts(today)
    return {
        "user_id": user_id,
        "this_month": facts["this_month"],
        "last_month": facts["last_month"],
        "first_month": facts["first_month"],
        "this_year": facts["this_year"],
    }


def compute_facts_before(case: EvalCase, params: dict[str, str]) -> CaseFacts:
    from sqlalchemy import text

    from app.db.session import session_for
    from app.services.money import to_major

    facts = CaseFacts()
    with session_for(None, system=True) as db:
        if case.expect_value_sql:
            value = db.execute(text(case.expect_value_sql), params).scalar()
            facts.expected_value = to_major(int(value)) if value is not None else None
        if case.expect_pairs_sql:
            rows = db.execute(text(case.expect_pairs_sql), params).all()
            facts.expected_pairs = [(str(label), to_major(int(minor))) for label, minor in rows]
        facts.counts_before = _counts(db)
    return facts


def complete_facts_after(case: EvalCase, params: dict[str, str], facts: CaseFacts) -> None:
    from sqlalchemy import text

    from app.db.session import session_for

    with session_for(None, system=True) as db:
        if case.expect_db_sql:
            facts.db_value = db.execute(text(case.expect_db_sql), params).scalar()
        facts.counts_after = _counts(db)


def _counts(db) -> dict[str, int]:
    from sqlalchemy import text

    return {t: db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() for t in USER_TABLES}


async def run_turn(user_id: str, message: str) -> ChatTurn:
    """One message through the real "chat" runner (coordinator + specialists), keeping the
    tool calls with their arguments, which `runtime.run_agent` does not return."""
    from google.genai import types

    from app.agents import runtime

    runtime.ensure_available()
    runner = runtime._runner("chat")
    sessions = runtime._session_service()
    session = await sessions.create_session(app_name=runner.app_name, user_id=user_id)
    turn = ChatTurn()
    texts: list[str] = []
    start = time.perf_counter()
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            if (
                event.author
                and event.author != "user"
                and (not turn.agents or turn.agents[-1] != event.author)
            ):
                turn.agents.append(event.author)
            for call in event.get_function_calls():
                turn.tool_calls.append((call.name or "", dict(call.args or {})))
            for response in event.get_function_responses():
                turn.tool_results.append((response.name or "", dict(response.response or {})))
            if event.is_final_response() and event.content and event.content.parts:
                texts.extend(p.text for p in event.content.parts if p.text and not p.thought)
    except Exception as exc:  # noqa: BLE001 - a crash is a failed case, not a failed run
        turn.error = f"{type(exc).__name__}: {exc}"[:300]
    finally:
        await sessions.delete_session(app_name=runner.app_name, user_id=user_id, session_id=session.id)
    turn.seconds = time.perf_counter() - start
    turn.text = "\n".join(texts).strip()
    return turn


async def run_case(case: EvalCase, today: dt.date) -> EvalResult:
    """seed_demo_data for a fresh user, one chat turn, then score."""
    user_id = f"eval-{case.id}"
    seed_demo_data(user_id, today=today)
    params = month_params(today, user_id)
    facts = compute_facts_before(case, params)
    turn = await run_turn(user_id, case.message)
    complete_facts_after(case, params, facts)
    checks, notes = score(case, turn, facts)
    return EvalResult(
        case_id=case.id,
        kind=case.kind,
        passed=all(checks.values()),
        seconds=round(turn.seconds, 1),
        agent=turn.agent,
        tools=[n for n, _ in turn.tool_calls if n != "transfer_to_agent"],
        checks=checks,
        notes=notes,
        checker=checker_stats(turn),
        text=turn.text[:500],
        trace=_trace(turn),
    )


def _trace(turn: ChatTurn) -> list[dict[str, Any]]:
    calls = [{"call": n, "args": a} for n, a in turn.tool_calls if n != "transfer_to_agent"]
    results = [{"result": n, "data": json.dumps(r, ensure_ascii=False)[:1500]} for n, r in turn.tool_results]
    return calls + results


# --- Reporting -----------------------------------------------------------------------------


def summary_rows(results: list[EvalResult]) -> list[tuple[str, int, int]]:
    kinds = sorted({r.kind for r in results})
    rows = [
        (k, sum(r.passed for r in results if r.kind == k), sum(r.kind == k for r in results)) for k in kinds
    ]
    rows.append(("all", sum(r.passed for r in results), len(results)))
    return rows


def render_table(results: list[EvalResult]) -> str:
    lines = [
        "| case | kind | result | agent | tools | failed checks | checker | seconds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        failed = ", ".join(k for k, ok in r.checks.items() if not ok) or "-"
        checker = ", ".join(f"{k} {v}" for k, v in r.checker.items()) or "-"
        tools = ", ".join(dict.fromkeys(r.tools)) or "-"
        lines.append(
            f"| {r.case_id} | {r.kind} | {'PASS' if r.passed else 'FAIL'} | {r.agent or '-'} | {tools} "
            f"| {failed} | {checker} | {r.seconds} |"
        )
    return "\n".join(lines)


def render_summary(results: list[EvalResult]) -> str:
    lines = ["| kind | passed | total | rate |", "| --- | --- | --- | --- |"]
    for kind, passed, total in summary_rows(results):
        lines.append(f"| {kind} | {passed} | {total} | {passed / total:.0%} |")
    return "\n".join(lines)


def render_markdown(meta: dict[str, Any], results: list[EvalResult]) -> str:
    notes = [f"- {r.case_id}: {'; '.join(r.notes)}" for r in results if r.notes and not r.passed]
    return "\n".join(
        [
            "# Kasa eval results (latest run)",
            "",
            (
                f"Run {meta['started']} on {meta['provider']} ({meta['model']}), today frozen at "
                f"{meta['today']}, {meta['seconds']} s in total. Written by `python -m evals.run_evals`."
            ),
            "",
            render_summary(results),
            "",
            render_table(results),
            "",
            "## Failures",
            "",
            *(notes or ["None."]),
            "",
        ]
    )


def _configure_environment(db_path: Path) -> None:
    """Point the app at a fresh SQLite file. Must run before anything imports app.*."""
    config, session = sys.modules.get("app.config"), sys.modules.get("app.db.session")
    if (config and config.get_settings.cache_info().currsize) or (session and session._engine is not None):
        raise RuntimeError("configure the eval database before the app reads its settings")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["AUTO_MIGRATE"] = "true"
    os.environ["FIREBASE_PROJECT_ID"] = ""


def _freeze_today(today: dt.date) -> None:
    from app.services import clock

    fixed = dt.datetime.combine(today, dt.time(12, 0), clock.KASA_TZ)
    clock.now = lambda: fixed
    clock.today = lambda: today


async def run_all(cases: list[EvalCase], today: dt.date) -> list[EvalResult]:
    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case.id} ...", flush=True)
        result = await run_case(case, today)
        print(
            f"    {'PASS' if result.passed else 'FAIL'} in {result.seconds}s {result.notes or ''}", flush=True
        )
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="run cases whose id starts with this prefix")
    parser.add_argument("--today", default=DEFAULT_TODAY.isoformat(), help="frozen date, YYYY-MM-DD")
    parser.add_argument("--no-markdown", action="store_true", help="do not overwrite evals/latest.md")
    args = parser.parse_args()
    today = dt.date.fromisoformat(args.today)
    cases = load_cases(only=args.only)

    workdir = Path(tempfile.mkdtemp(prefix="kasa-evals-"))
    _configure_environment(workdir / "evals.db")
    _freeze_today(today)
    from app.config import get_settings
    from app.db.session import init_db

    init_db()
    settings = get_settings()
    started = dt.datetime.now().astimezone()
    print(f"{len(cases)} cases on {settings.llm_provider} ({settings.chat_model_name}), today={today}")
    clock_start = time.perf_counter()
    results = asyncio.run(run_all(cases, today))
    meta = {
        "started": started.isoformat(timespec="seconds"),
        "provider": settings.llm_provider,
        "model": settings.chat_model_name,
        "today": today.isoformat(),
        "seconds": round(time.perf_counter() - clock_start),
        "only": args.only,
    }

    print()
    print(render_summary(results))
    print()
    print(render_table(results))
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{started.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(
        json.dumps({"meta": meta, "results": [asdict(r) for r in results]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nwrote {out}")
    if not args.no_markdown:
        LATEST_MD.write_text(render_markdown(meta, results), encoding="utf-8")
        print(f"wrote {LATEST_MD}")


if __name__ == "__main__":
    main()
