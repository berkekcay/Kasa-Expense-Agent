"""Gmail -> inbox items (owner: track INGEST).

For each new message matching settings.gmail_query: fetch it, run the "email-parse" agent
runner (`agents.runtime.run_agent("email-parse", user_id, parts)`) on its text, and create
an InboxItem with external_ref = Gmail message id. Messages the agent says are not a
purchase become status "ignored"; parser errors become "failed" with `error` set.

Background entry points (Cloud Scheduler / Pub/Sub, see api/internal.py) find accounts with
`session_for(None, system=True)` and then do all per-user work in `session_for(user_id)`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SyncResult:
    user_id: str
    fetched: int = 0
    created: int = 0
    ignored: int = 0
    duplicates: int = 0
    failed: int = 0
    error: str | None = None  # set when the whole sync failed (e.g. token revoked)


async def sync_user(user_id: str, *, max_messages: int | None = None) -> SyncResult:
    """Incremental when gmail_history_id is set (history.list), else a query sync
    (settings.gmail_query, at most settings.gmail_sync_max_messages). Updates history id."""
    raise NotImplementedError("sync_user: track INGEST")


async def sync_all() -> list[SyncResult]:
    """Every connected account, one at a time (Cloud Scheduler, e.g. hourly)."""
    raise NotImplementedError("sync_all: track INGEST")


async def handle_push(email_address: str, history_id: str) -> SyncResult | None:
    """Pub/Sub push for one mailbox. None if no account uses that address."""
    raise NotImplementedError("handle_push: track INGEST")


def renew_watches() -> int:
    """Re-run users.watch for accounts whose watch expires within a day; returns count.
    Gmail watches last 7 days, so the scheduler calls this daily."""
    raise NotImplementedError("renew_watches: track INGEST")
