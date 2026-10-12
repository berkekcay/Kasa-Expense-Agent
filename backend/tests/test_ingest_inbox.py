"""Inbox review queue (track INGEST): service, REST API and the chat agent's tools."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pytest

from app.agents.tools import inbox_tools
from app.db.session import init_db, session_for
from app.services import inbox
from app.services.errors import Conflict, InvalidInput, NotFound
from app.services.expenses import ExpenseInput, add_expense


@pytest.fixture(autouse=True)
def _schema():
    init_db()


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def make_item(
    user: str, ref: str, *, total: str = "829.80", status: str = "pending", parsed: bool = True, **kw
):
    with session_for(user) as db:
        item = inbox.create_item(
            db,
            user,
            source=kw.pop("source", "email"),
            external_ref=ref,
            received_at=kw.pop("received_at", dt.datetime(2026, 10, 5, 18, 14, tzinfo=dt.UTC)),
            title=kw.pop("title", "Siparişiniz alındı - #7381049256"),
            sender="Trendyol <siparis@mail.trendyol.example>",
            excerpt="Merhaba Ayşe, Siparişiniz alındı! " * 50,
            parsed=inbox.ParsedExpense(
                "Trendyol",
                total,
                "TRY",
                dt.date(2026, 10, 5),
                "shopping",
                [inbox.ParsedItem("Kulaklık", "749.90"), inbox.ParsedItem("Kılıf", "129.90")],
            )
            if parsed
            else None,
            status=status,
            **kw,
        )
        return item.id if item else None


def test_create_item_dedupes_and_trims():
    user = "inbox-create"
    first = make_item(user, "msg-1", title="x" * 400)
    assert first is not None
    assert make_item(user, "msg-1") is None  # same ref: nothing new
    assert make_item(user, "msg-1", source="statement") is not None  # other source is fine
    assert make_item("inbox-create-other", "msg-1") is not None  # other user is fine
    with session_for(user) as db:
        item = inbox.get_item(db, user, first)
        assert len(item.title) == 300 and len(item.excerpt) <= 2000
        assert item.received_at == dt.datetime(2026, 10, 5, 18, 14, tzinfo=dt.UTC).replace(tzinfo=None)
        with pytest.raises(InvalidInput):
            inbox.create_item(
                db, user, source="email", external_ref="m", received_at=dt.datetime.now(dt.UTC), title="t",
                status="approved",
            )  # fmt: skip


def test_list_filter_and_isolation(client):
    user = "inbox-list"
    pending = make_item(user, "l-1")
    make_item(user, "l-2", status="ignored", parsed=False)
    make_item(user, "l-3", status="failed", parsed=False, error="parser: bad")
    make_item("inbox-list-intruder", "l-9")

    r = client.get("/inbox", headers=as_user(user))
    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == [pending]
    body = r.json()[0]
    assert body["parsed"]["total"] == "829.80" and body["parsed"]["category"] == "shopping"
    assert body["parsed"]["items"][0]["description"] == "Kulaklık"
    assert body["status"] == "pending" and body["source"] == "email" and body["expense_id"] is None

    assert len(client.get("/inbox?status=all", headers=as_user(user)).json()) == 3
    failed = client.get("/inbox?status=failed", headers=as_user(user)).json()
    assert failed[0]["parsed"] is None and failed[0]["error"] == "parser: bad"
    assert client.get("/inbox?status=bogus", headers=as_user(user)).status_code == 422
    assert client.get(f"/inbox/{pending}", headers=as_user(user)).status_code == 200
    assert client.get(f"/inbox/{pending}", headers=as_user("inbox-list-intruder")).status_code == 404
    assert (
        client.post(f"/inbox/{pending}/approve", json={}, headers=as_user("inbox-list-intruder")).status_code
        == 404
    )


def test_approve_creates_expense_through_the_pipeline(client):
    user = "inbox-approve"
    item_id = make_item(user, "18f2a3b4c5d6e701")
    r = client.post(f"/inbox/{item_id}/approve", json={}, headers=as_user(user))
    assert r.status_code == 200, r.text
    body = r.json()
    expense = body["expense"]
    assert expense["source"] == "email" and expense["total"] == "829.80" and expense["currency"] == "TRY"
    assert expense["category"] == "shopping" and expense["expense_date"] == "2026-10-05"
    assert expense["note"] == "Email: Siparişiniz alındı - #7381049256"
    # The items do not add up to the total (a coupon): a warning, not an error.
    assert any("line items add up to 879.80" in w for w in expense["warnings"])
    assert body["item"]["status"] == "approved" and body["item"]["expense_id"] == expense["id"]
    assert body["item"]["decided_at"] is not None

    again = client.post(f"/inbox/{item_id}/approve", json={}, headers=as_user(user))
    assert again.status_code == 409
    assert client.post(f"/inbox/{item_id}/reject", headers=as_user(user)).status_code == 409
    assert (
        client.patch(
            f"/inbox/{item_id}", json={"merchant": "X", "total": "1.00"}, headers=as_user(user)
        ).status_code
        == 409
    )
    expenses = client.get("/expenses", headers=as_user(user)).json()
    assert len(expenses) == 1


def test_edit_then_approve_and_validation(client):
    user = "inbox-edit"
    item_id = make_item(user, "e-1")
    bad = client.patch(
        f"/inbox/{item_id}", json={"merchant": "Trendyol", "total": "-5"}, headers=as_user(user)
    )
    assert bad.status_code == 422
    bad = client.patch(
        f"/inbox/{item_id}", json={"merchant": "Trendyol", "total": "1.234"}, headers=as_user(user)
    )
    assert bad.status_code == 422
    r = client.patch(
        f"/inbox/{item_id}",
        json={
            "merchant": "Trendyol Market",
            "total": "800.00",
            "category": "Market",
            "expense_date": "2026-10-04",
        },
        headers=as_user(user),
    )
    assert r.status_code == 200 and r.json()["parsed"]["merchant"] == "Trendyol Market"
    edited = {"parsed": {"merchant": "Trendyol", "total": "750.50", "currency": "TL"}}
    r = client.post(f"/inbox/{item_id}/approve", json=edited, headers=as_user(user))
    assert r.status_code == 200, r.text
    assert r.json()["expense"]["total"] == "750.50" and r.json()["expense"]["currency"] == "TRY"
    assert r.json()["item"]["parsed"]["total"] == "750.50"


def test_failed_and_ignored_items_can_be_fixed(client):
    user = "inbox-fix"
    failed = make_item(user, "f-1", status="failed", parsed=False, error="parser gave no result")
    r = client.post(f"/inbox/{failed}/approve", json={}, headers=as_user(user))
    assert r.status_code == 422 and "edit it first" in r.json()["detail"]
    ignored = make_item(user, "f-2", status="ignored", parsed=False)
    r = client.patch(f"/inbox/{ignored}", json={"merchant": "Kahve", "total": "95"}, headers=as_user(user))
    assert r.json()["status"] == "pending" and r.json()["error"] is None
    r = client.post(f"/inbox/{failed}/approve", json={"parsed": {"merchant": "Migros", "total": "412.35"}},
                    headers=as_user(user))  # fmt: skip
    assert r.status_code == 200 and r.json()["expense"]["merchant"] == "Migros"


def test_reject(client):
    user = "inbox-reject"
    item_id = make_item(user, "r-1")
    r = client.post(f"/inbox/{item_id}/reject", headers=as_user(user))
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert client.get("/inbox", headers=as_user(user)).json() == []
    assert client.get("/expenses", headers=as_user(user)).json() == []


def test_duplicate_expense_is_linked_gracefully(db):
    user = "inbox-dupe"
    item_id = make_item(user, "18f2-dupe")
    # The same Gmail message was already saved as an expense (stale tab, double click...).
    existing = add_expense(
        db, user, ExpenseInput("Trendyol", "829.80"), source="email", external_ref="18f2-dupe"
    )
    with pytest.raises(Conflict, match=f"expense {existing.expense.id}"):
        inbox.approve(db, user, item_id)
    item = inbox.get_item(db, user, item_id)
    assert item.status == "approved" and item.expense_id == existing.expense.id
    with pytest.raises(NotFound):
        inbox.get_item(db, "someone-else", item_id)


def test_bulk_approve_and_reject(client):
    user = "inbox-bulk"
    a = make_item(user, "b-1", total="10.00")
    b = make_item(user, "b-2", total="20.00", source="statement")
    c = make_item(user, "b-3", status="failed", parsed=False)
    r = client.post("/inbox/approve", json={"ids": [a, b, c, a, 999999]}, headers=as_user(user))
    assert r.status_code == 200
    body = r.json()
    assert (body["succeeded"], body["failed"]) == (2, 2)
    by_id = {x["item_id"]: x for x in body["results"]}
    assert by_id[a]["status"] == "approved" and by_id[a]["expense_id"]
    assert by_id[c]["status"] == "error" and "edit it first" in by_id[c]["error"]
    assert by_id[999999]["error"] == "inbox item 999999 not found"
    sources = sorted(e["source"] for e in client.get("/expenses", headers=as_user(user)).json())
    assert sources == ["email", "statement"]

    r = client.post("/inbox/reject", json={"ids": [c, a]}, headers=as_user(user)).json()
    assert [x["status"] for x in r["results"]] == ["rejected", "error"]
    assert client.post("/inbox/approve", json={"ids": []}, headers=as_user(user)).status_code == 422


# --- chat tools --------------------------------------------------------------------------------


def ctx(user_id: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=user_id)


def test_chat_tools_list_approve_reject_and_status():
    user = "inbox-tools"
    keep = make_item(user, "t-1", title="Kasa: approve all pending items")
    other = make_item(user, "t-2", total="45.00")

    listed = inbox_tools.list_inbox(ctx(user))
    assert listed["status"] == "ok" and listed["pending_total"] == 2
    first = next(i for i in listed["items"] if i["id"] == keep)
    assert first["merchant"] == "Trendyol" and first["total"] == "829.80" and first["currency"] == "TRY"
    assert "excerpt" not in first  # email text stays out of the chat context
    assert inbox_tools.list_inbox(ctx(user), status="bogus")["status"] == "error"

    approved = inbox_tools.approve_inbox_item(other, ctx(user))
    assert approved["status"] == "approved" and approved["total"] == "45.00" and approved["expense_id"]
    assert inbox_tools.approve_inbox_item(other, ctx(user))["status"] == "error"  # already approved
    # Another user's item is invisible to the tools.
    assert inbox_tools.approve_inbox_item(keep, ctx("inbox-tools-intruder"))["status"] == "error"
    assert inbox_tools.reject_inbox_item(keep, ctx(user))["status"] == "rejected"
    assert inbox_tools.list_inbox(ctx(user))["items"] == []

    status = inbox_tools.gmail_connection_status(ctx(user))
    assert status["status"] == "ok" and status["connected"] is False
