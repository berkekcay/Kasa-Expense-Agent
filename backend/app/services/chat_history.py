"""Saved chat conversations (owner: shared, chat). Every query filters by the owner; on SQL
Server the RLS policy does too.

The ADK session that holds the model's own context lives in memory (`agents.runtime`). This
module is the durable record the user scrolls back through, and the source of the short
history replayed into a new session when the old one is gone.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import ChatConversation, ChatMessage
from app.services.errors import NotFound

TITLE_CHARS = 80
REPLAY_MESSAGES = 10
REPLAY_CHARS = 600


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_CHARS else line[: TITLE_CHARS - 1].rstrip() + "…"


def create(db: Session, user_id: str, first_message: str) -> ChatConversation:
    conversation = ChatConversation(
        id=secrets.token_hex(16), user_id=user_id, title=_title(first_message) or "Chat"
    )
    db.add(conversation)
    db.flush()
    return conversation


def get(db: Session, user_id: str, conversation_id: str, *, with_messages: bool = False) -> ChatConversation:
    stmt = select(ChatConversation).where(
        ChatConversation.id == conversation_id, ChatConversation.user_id == user_id
    )
    if with_messages:
        stmt = stmt.options(selectinload(ChatConversation.messages))
    conversation = db.scalar(stmt)
    if conversation is None:
        raise NotFound("conversation not found")
    return conversation


def list_for(db: Session, user_id: str, limit: int = 50) -> list[tuple[ChatConversation, int]]:
    """Newest first, with the message count."""
    counts = (
        select(ChatMessage.conversation_id, func.count().label("n"))
        .where(ChatMessage.user_id == user_id)
        .group_by(ChatMessage.conversation_id)
        .subquery()
    )
    stmt = (
        select(ChatConversation, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.conversation_id == ChatConversation.id)
        .where(ChatConversation.user_id == user_id)
        .order_by(ChatConversation.updated_at.desc(), ChatConversation.created_at.desc())
        .limit(limit)
    )
    return [(c, int(n)) for c, n in db.execute(stmt)]


def add_message(
    db: Session, conversation: ChatConversation, role: str, text: str, payload: dict[str, Any] | None = None
) -> ChatMessage:
    message = ChatMessage(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
        role=role,
        text=text,
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    db.add(message)
    conversation.updated_at = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    db.flush()
    return message


def payload_of(message: ChatMessage) -> dict[str, Any]:
    try:
        return json.loads(message.payload_json) if message.payload_json else {}
    except ValueError:
        return {}


def set_card_state(
    db: Session, user_id: str, message_id: int, index: int, state: dict[str, Any]
) -> ChatMessage:
    """Remember what happened to a card (undone, confirmed) so it shows the same after a reload."""
    message = db.scalar(
        select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.user_id == user_id)
    )
    if message is None:
        raise NotFound("message not found")
    payload = payload_of(message)
    payload.setdefault("card_state", {})[str(index)] = state
    message.payload_json = json.dumps(payload, ensure_ascii=False)
    db.flush()
    return message


def rename(db: Session, user_id: str, conversation_id: str, title: str) -> ChatConversation:
    conversation = get(db, user_id, conversation_id)
    conversation.title = _title(title) or conversation.title
    db.flush()
    return conversation


def delete(db: Session, user_id: str, conversation_id: str) -> None:
    db.delete(get(db, user_id, conversation_id))
    db.flush()


def replay_text(conversation: ChatConversation) -> str:
    """The last messages as plain text, for a fresh agent session to pick up the thread."""
    lines = []
    for message in conversation.messages[-REPLAY_MESSAGES:]:
        who = "User" if message.role == "user" else "Kasa"
        text = " ".join(message.text.split())[:REPLAY_CHARS]
        if text:
            lines.append(f"{who}: {text}")
    if not lines:
        return ""
    return (
        "<earlier_conversation>\n"
        + "\n".join(lines)
        + "\n</earlier_conversation>\nThis is the earlier part of this chat, for context only. "
        "Numbers in it may be out of date; use tools for anything you state now."
    )
