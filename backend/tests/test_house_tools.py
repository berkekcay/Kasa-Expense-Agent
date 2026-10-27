"""House agent tools called directly with a fake ToolContext (track HOUSE)."""

import datetime as dt
from types import SimpleNamespace

import pytest

from app.agents import house_agent
from app.agents.tools import house_tools as t
from app.db.session import init_db, session_for
from app.integrations import google_oauth
from app.services import clock, houses


def ctx(user_id: str) -> SimpleNamespace:
    """Tools only read `user_id` from the ToolContext."""
    return SimpleNamespace(user_id=user_id)


@pytest.fixture
def flat():
    init_db()
    me, ali, ayse = "tt-me", "tt-ali", "tt-ayse"
    with session_for(me) as db:
        house = houses.create_house(db, me, "Ev 1")
        houses.add_member(db, me, house.id, ali, "Ali")
        houses.add_member(db, me, house.id, ayse, "Ayşe")
        house_id = house.id
    return house_id, me, ali, ayse


def test_list_my_houses_names_the_current_user(flat):
    house_id, me, ali, ayse = flat
    result = t.list_my_houses(ctx(me))
    assert result["current_user_id"] == me
    house = next(h for h in result["houses"] if h["id"] == house_id)
    assert {m["user_id"]: m["name"] for m in house["members"]} == {me: me, ali: "Ali", ayse: "Ayşe"}


def test_percent_split_with_names_and_me(flat):
    house_id, me, ali, ayse = flat
    result = t.add_house_expense_percent_split(
        house_id,
        "Fatura",
        "600",
        [
            t.PercentShare(user="Ali", percent="50"),
            t.PercentShare(user="AYŞE", percent=30),
            t.PercentShare(user="ben", percent="20"),
        ],
        ctx(me),
    )
    assert result["status"] == "saved", result
    assert result["split_type"] == "percent" and result["paid_by"] == me
    assert result["shares"] == {ali: "300.00", ayse: "180.00", me: "120.00"}


def test_percent_split_errors_come_back_as_data(flat):
    house_id, me, *_ = flat
    bad_sum = t.add_house_expense_percent_split(
        house_id,
        "x",
        "100",
        [t.PercentShare(user="Ali", percent="50"), t.PercentShare(user="me", percent="40")],
        ctx(me),
    )
    assert bad_sum == {"status": "error", "error": "percents must add up to 100, they add up to 90"}
    stranger = t.add_house_expense_percent_split(
        house_id, "x", "100", [t.PercentShare(user="Zeynep", percent="100")], ctx(me)
    )
    assert stranger["status"] == "error" and "not a member" in stranger["error"]
    twice = t.add_house_expense_percent_split(
        house_id,
        "x",
        "100",
        [t.PercentShare(user="Ali", percent="50"), t.PercentShare(user="tt-ali", percent="50")],
        ctx(me),
    )
    assert twice["status"] == "error" and "twice" in twice["error"]
    assert t.add_house_expense_percent_split(999_999, "x", "1", [], ctx(me))["status"] == "error"


def test_exact_split(flat):
    house_id, me, ali, ayse = flat
    result = t.add_house_expense_exact_split(
        house_id,
        "Market",
        300,
        [t.AmountShare(user="Ali", amount="120"), t.AmountShare(user="Ayşe", amount=180)],
        ctx(me),
        paid_by="Ayşe",
    )
    assert result["status"] == "saved", result
    assert result["paid_by"] == ayse and result["shares"] == {ali: "120.00", ayse: "180.00"}
    short = t.add_house_expense_exact_split(
        house_id, "Market", "300", [t.AmountShare(user="Ali", amount="120")], ctx(me)
    )
    assert short["status"] == "error" and "180.00 missing" in short["error"]


def test_item_split(flat):
    house_id, me, ali, _ayse = flat
    result = t.add_house_expense_item_split(
        house_id,
        "Migros",
        "110",
        [
            t.SplitItem(description="Peynir", amount="60", assignees=["Ali"]),
            t.SplitItem(description="Ekmek", amount="40"),
        ],
        ctx(me),
        participants=["Ali", "me"],
    )
    assert result["status"] == "saved", result
    assert result["shares"] == {ali: "88.00", me: "22.00"}
    assert result["items"] == [
        {"description": "Peynir", "amount": "60.00", "shared_by": [ali]},
        {"description": "Ekmek", "amount": "40.00", "shared_by": [ali, me]},
    ]
    assert any("difference" in w for w in result["warnings"])


def test_equal_split_balances_payment_and_undo(flat):
    house_id, me, ali, ayse = flat
    saved = t.add_house_expense_equal_split(house_id, "Kira", "300", ctx(me))
    assert saved["shares"] == {me: "100.00", ali: "100.00", ayse: "100.00"}

    state = t.get_house_balances(house_id, ctx(ali))
    assert state["balances"] == {me: "200.00", ali: "-100.00", ayse: "-100.00"}

    over = t.record_payment(house_id, "Ayşe", "me", "200", ctx(me))
    assert over["status"] == "error" and "at most 100.00" in over["error"]
    paid = t.record_payment(house_id, "Ayşe", "ben", "100", ctx(me), note="IBAN")
    assert paid["status"] == "saved" and (paid["from"], paid["to"], paid["amount"]) == (ayse, me, "100.00")
    assert paid["settle_up_now"] == [{"from": ali, "to": me, "amount": "100.00"}]

    assert t.undo_payment(house_id, paid["payment_id"], ctx(ali))["status"] == "error"  # not the creator
    undone = t.undo_payment(house_id, paid["payment_id"], ctx(me))
    assert undone["status"] == "deleted" and len(undone["settle_up_now"]) == 2
    assert t.get_house_balances(999_999, ctx(me))["status"] == "error"


def test_create_settle_up_reminders_tool(flat, monkeypatch):
    house_id, me, ali, ayse = flat
    monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: None)
    nothing = t.create_settle_up_reminders(house_id, ctx(me))
    assert nothing["status"] == "nothing_to_remind"
    t.add_house_expense_equal_split(house_id, "Kira", "300", ctx(me))
    result = t.create_settle_up_reminders(house_id, ctx(me))
    assert result["status"] == "saved" and result["calendar_connected"] is False
    assert result["due_date"] == (clock.today() + dt.timedelta(days=7)).isoformat()
    assert sorted(r["from"] for r in result["reminders"]) == [ali, ayse]
    assert all(not r["on_calendar"] for r in result["reminders"])
    assert t.create_settle_up_reminders(house_id, ctx(me), due_date="not a date")["status"] == "error"


def test_agent_lists_every_tool():
    names = {tool.__name__ for tool in house_agent.build_house_agent().tools}
    assert names == {
        "list_my_houses",
        "add_house_expense_equal_split",
        "add_house_expense_percent_split",
        "add_house_expense_exact_split",
        "add_house_expense_item_split",
        "get_house_balances",
        "record_payment",
        "undo_payment",
        "create_settle_up_reminders",
        "create_house_invite",
    }
    assert "{user, percent}" in house_agent.INSTRUCTION
