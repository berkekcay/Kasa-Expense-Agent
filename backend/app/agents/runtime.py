"""Runs Kasa agents with Google ADK for the API layer.

Sessions live in ADK's InMemorySessionService (per Cloud Run instance). That is fine for
sprint 1; a DB-backed session service can replace it without touching the endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.coordinator import build_coordinator
from app.agents.receipt_agent import build_receipt_agent
from app.config import get_settings
from app.db.session import get_engine

APP_NAME = "kasa"


class AgentsUnavailable(RuntimeError):
    """Raised when no Gemini API key is configured."""


@dataclass
class AgentRun:
    session_id: str
    text: str
    tool_results: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def last_tool_result(self, name: str) -> dict[str, Any] | None:
        return next((r for n, r in reversed(self.tool_results) if n == name), None)


@lru_cache
def _session_service() -> InMemorySessionService:
    return InMemorySessionService()


@lru_cache
def _runner(kind: str) -> Runner:
    dialect = "tsql" if get_engine().dialect.name == "mssql" else "sqlite"
    agent = build_coordinator(dialect) if kind == "chat" else build_receipt_agent()
    return Runner(app_name=f"{APP_NAME}-{kind}", agent=agent, session_service=_session_service())


def ensure_available() -> None:
    if not get_settings().agents_enabled:
        raise AgentsUnavailable(
            "AI features are disabled: set GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey)."
        )


async def run_agent(
    kind: str, user_id: str, parts: list[types.Part], session_id: str | None = None
) -> AgentRun:
    """Send one user message to the 'chat' (coordinator) or 'receipt' runner and collect
    the final text plus every tool result produced during the turn."""
    ensure_available()
    runner = _runner(kind)
    sessions = _session_service()
    session = None
    if session_id:
        # Sessions are keyed by user_id, so another user's session id simply isn't found.
        session = await sessions.get_session(app_name=runner.app_name, user_id=user_id, session_id=session_id)
    if session is None:
        session = await sessions.create_session(app_name=runner.app_name, user_id=user_id)

    run = AgentRun(session_id=session.id, text="")
    texts: list[str] = []
    async for event in runner.run_async(
        user_id=user_id, session_id=session.id, new_message=types.Content(role="user", parts=parts)
    ):
        for response in event.get_function_responses():
            run.tool_results.append((response.name or "", dict(response.response or {})))
        if event.is_final_response() and event.content and event.content.parts:
            texts.extend(p.text for p in event.content.parts if p.text and not p.thought)
    run.text = "\n".join(texts).strip()
    return run
