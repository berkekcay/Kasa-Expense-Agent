"""Helpers shared by all ADK function tools.

The acting user always comes from the ADK invocation (`tool_context.user_id`, set by the
API from the authenticated request) — never from a model-supplied argument.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from google.adk.tools import ToolContext
from sqlalchemy.orm import Session

from app.db.session import session_for
from app.services.errors import DomainError


@contextmanager
def tool_db(tool_context: ToolContext) -> Iterator[tuple[Session, str]]:
    user_id = tool_context.user_id
    with session_for(user_id) as db:
        yield db, user_id


def error(exc: Exception) -> dict:
    """Tools report problems as data so the model can explain them instead of crashing."""
    message = str(exc) if isinstance(exc, (DomainError, ValueError)) else "internal error"
    return {"status": "error", "error": message}


def not_available(feature: str) -> dict:
    """What a tool returns until its track lands, so the agent can say so politely."""
    return {"status": "unavailable", "error": f"{feature} is not available yet"}
