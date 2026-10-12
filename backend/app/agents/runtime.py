"""Runs Kasa agents with Google ADK for the API layer and background jobs (shared, finished).

Runner kinds (RUNNERS registry):
  chat            coordinator + all specialists (POST /chat, sessions kept per user)
  receipt         receipt agent with the vision model (POST /receipts)
  email-parse     one email -> submit_parsed_expense / mark_not_expense (gmail_sync)
  statement-parse statement text -> submit_statement_lines (statements.parse_pdf)

Only "chat" keeps its session between calls; the others are one-shot and their session is
deleted after the run. Sessions live in ADK's InMemorySessionService (per Cloud Run
instance); a DB-backed session service can replace it without touching the callers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from google.adk.agents import BaseAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.config import get_settings
from app.db.session import get_engine

APP_NAME = "kasa"

RunnerKind = Literal["chat", "receipt", "email-parse", "statement-parse"]


def _build_chat(sql_dialect: str) -> BaseAgent:
    from app.agents.coordinator import build_coordinator

    return build_coordinator(sql_dialect)


def _build_receipt(_sql_dialect: str) -> BaseAgent:
    from app.agents.receipt_agent import build_receipt_agent

    return build_receipt_agent(for_images=True)


def _build_email_parse(_sql_dialect: str) -> BaseAgent:
    from app.agents.email_agent import build_email_parser_agent

    return build_email_parser_agent()


def _build_statement_parse(_sql_dialect: str) -> BaseAgent:
    from app.agents.statement_agent import build_statement_parser_agent

    return build_statement_parser_agent()


# kind -> (agent builder taking the report SQL dialect, keep session between calls)
RUNNERS: dict[str, tuple[Callable[[str], BaseAgent], bool]] = {
    "chat": (_build_chat, True),
    "receipt": (_build_receipt, False),
    "email-parse": (_build_email_parse, False),
    "statement-parse": (_build_statement_parse, False),
}


class AgentsUnavailable(RuntimeError):
    """Raised when no LLM provider is configured."""


@dataclass
class AgentRun:
    session_id: str
    text: str
    tool_results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)  # authors of model events, in order

    def last_tool_result(self, name: str) -> dict[str, Any] | None:
        return next((r for n, r in reversed(self.tool_results) if n == name), None)

    @property
    def agent(self) -> str | None:
        """The agent that answered last (e.g. "report_agent")."""
        return self.agents[-1] if self.agents else None


@lru_cache
def _session_service() -> InMemorySessionService:
    return InMemorySessionService()


@lru_cache
def _runner(kind: str) -> Runner:
    if kind not in RUNNERS:
        raise ValueError(f"unknown runner kind {kind!r}; known: {', '.join(RUNNERS)}")
    build, _keep = RUNNERS[kind]
    dialect = "tsql" if get_engine().dialect.name == "mssql" else "sqlite"
    return Runner(app_name=f"{APP_NAME}-{kind}", agent=build(dialect), session_service=_session_service())


def ensure_available() -> None:
    settings = get_settings()
    if settings.agents_enabled:
        return
    if settings.llm_provider == "ollama":
        raise AgentsUnavailable("AI features are disabled: set OLLAMA_BASE_URL (LLM_PROVIDER=ollama).")
    raise AgentsUnavailable(
        "AI features are disabled: set GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey) "
        "or use LLM_PROVIDER=ollama with OLLAMA_BASE_URL."
    )


async def run_agent(
    kind: RunnerKind, user_id: str, parts: list[types.Part], session_id: str | None = None
) -> AgentRun:
    """Send one user message to a runner and collect the final text, every tool result
    produced during the turn, and which agents spoke."""
    ensure_available()
    runner = _runner(kind)
    keep_session = RUNNERS[kind][1]
    sessions = _session_service()
    session = None
    if session_id and keep_session:
        # Sessions are keyed by user_id, so another user's session id simply isn't found.
        session = await sessions.get_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
    if session is None:
        session = await sessions.create_session(app_name=runner.app_name, user_id=user_id)

    run = AgentRun(session_id=session.id, text="")
    texts: list[str] = []
    try:
        async for event in runner.run_async(
            user_id=user_id, session_id=session.id, new_message=types.Content(role="user", parts=parts)
        ):
            if event.author and event.author != "user" and (not run.agents or run.agents[-1] != event.author):
                run.agents.append(event.author)
            for response in event.get_function_responses():
                run.tool_results.append((response.name or "", dict(response.response or {})))
            if event.is_final_response() and event.content and event.content.parts:
                texts.extend(p.text for p in event.content.parts if p.text and not p.thought)
    finally:
        if not keep_session:
            await sessions.delete_session(app_name=runner.app_name, user_id=user_id, session_id=session.id)
    run.text = "\n".join(texts).strip()
    return run
