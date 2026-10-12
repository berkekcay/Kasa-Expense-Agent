"""House: delete a shared expense, leave a house, remove a member (track HOUSE)."""

import uuid

import pytest
from sqlalchemy import select

from app.db.models import ExpenseItem, ExpenseItemAssignee, ExpenseShare


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


@pytest.fixture
def flat(client):
    """me created the house; ali and ayse joined."""
    p = uuid.uuid4().hex[:6]
    me, ali, ayse = f"hm-{p}-me", f"hm-{p}-ali", f"hm-{p}-ayse"
    house_id = client.post("/houses", json={"name": "Flat"}, headers=as_user(me)).json()["id"]
    for m, name in ((ali, "Ali"), (ayse, "Ayşe")):
        r = client.post(
            f"/houses/{house_id}/members", json={"user_id": m, "display_name": name}, headers=as_user(me)
        )
        assert r.status_code == 201
    return house_id, me, ali, ayse


def balances(client, house_id: int, user: str) -> dict[str, int]:
    body = client.get(f"/houses/{house_id}/balances", headers=as_user(user)).json()
    return {b["user_id"]: b["balance_minor"] for b in body["balances"]}


def add_bill(client, house_id: int, payer: str, total: str = "300") -> dict:
    r = client.post(
        f"/houses/{house_id}/expenses", json={"merchant": "Kira", "total": total}, headers=as_user(payer)
    )
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, house_id: int, frm: str, to: str, amount: str, recorded_by: str | None = None) -> None:
    r = client.post(
        f"/houses/{house_id}/settlements",
        json={"from_user": frm, "to_user": to, "amount": amount},
        headers=as_user(recorded_by or frm),
    )
    assert r.status_code == 201, r.text


class TestDeleteHouseExpense:
    def test_payer_deletes_items_split_and_balances_follow(self, client, db, flat):
        house_id, me, ali, ayse = flat
        add_bill(client, house_id, ali, "90")
        r = client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "items",
                "merchant": "Migros",
                "total": "100",
                "items": [
                    {"description": "Cheese", "amount": "60", "assignees": [ali]},
                    {"description": "Bread", "amount": "40"},
                ],
            },
            headers=as_user(me),
        )
        expense = r.json()
        before = balances(client, house_id, me)
        assert before[me] != 0
        url = f"/houses/{house_id}/expenses/{expense['id']}"

        assert client.delete(url, headers=as_user(ali)).status_code == 403  # not the payer
        assert client.delete(url, headers=as_user("hm-outsider")).status_code == 404
        assert client.delete(url, headers=as_user(me)).status_code == 204
        assert client.delete(url, headers=as_user(me)).status_code == 404

        assert balances(client, house_id, me) == {me: -3000, ali: 6000, ayse: -3000}
        listed = client.get(f"/houses/{house_id}/expenses", headers=as_user(ayse)).json()
        assert [e["merchant"] for e in listed] == ["Kira"]
        assert db.scalars(select(ExpenseShare).where(ExpenseShare.expense_id == expense["id"])).all() == []
        assert db.scalars(select(ExpenseItem).where(ExpenseItem.expense_id == expense["id"])).all() == []
        orphan = db.scalars(
            select(ExpenseItemAssignee).join(ExpenseItem, ExpenseItem.id == ExpenseItemAssignee.item_id, isouter=True)
            .where(ExpenseItem.id.is_(None))
        ).all()  # fmt: skip
        assert orphan == []

    def test_expense_of_another_house_is_404(self, client, flat):
        house_id, me, _ali, _ayse = flat
        other = client.post("/houses", json={"name": "Other"}, headers=as_user(me)).json()["id"]
        bill = add_bill(client, house_id, me)
        assert client.delete(f"/houses/{other}/expenses/{bill['id']}", headers=as_user(me)).status_code == 404
        personal = client.post(
            "/expenses", json={"merchant": "Mine", "total": "5"}, headers=as_user(me)
        ).json()
        assert (
            client.delete(f"/houses/{house_id}/expenses/{personal['id']}", headers=as_user(me)).status_code
            == 404
        )

    def test_not_when_someone_who_shares_it_left(self, client, flat):
        house_id, me, _ali, ayse = flat
        bill = add_bill(client, house_id, me, "300")
        pay(client, house_id, ayse, me, "100")
        assert client.delete(f"/houses/{house_id}/members/{ayse}", headers=as_user(ayse)).status_code == 204
        r = client.delete(f"/houses/{house_id}/expenses/{bill['id']}", headers=as_user(me))
        assert r.status_code == 409 and ayse in r.json()["detail"]


class TestMembers:
    def test_leave_with_zero_balance(self, client, flat):
        house_id, me, ali, ayse = flat
        add_bill(client, house_id, me, "300")
        r = client.delete(f"/houses/{house_id}/members/{ayse}", headers=as_user(ayse))
        assert r.status_code == 409
        assert r.json()["detail"] == "you owe 100.00 TRY in this house; settle up to zero before leaving"
        pay(client, house_id, ayse, me, "100", recorded_by=me)
        assert client.delete(f"/houses/{house_id}/members/{ayse}", headers=as_user(ayse)).status_code == 204

        assert client.get(f"/houses/{house_id}", headers=as_user(ayse)).status_code == 404
        house = client.get(f"/houses/{house_id}", headers=as_user(me)).json()
        assert [m["user_id"] for m in house["members"]] == [me, ali]
        # History stays: the bill still has Ayşe's share, and she is out of the balances.
        bill = client.get(f"/houses/{house_id}/expenses", headers=as_user(me)).json()[0]
        assert {s["user_id"] for s in bill["shares"]} == {me, ali, ayse}
        assert balances(client, house_id, me) == {me: 10000, ali: -10000}
        # New bills split between the people still there.
        new = add_bill(client, house_id, me, "50")
        assert {s["user_id"] for s in new["shares"]} == {me, ali}
        # The payment from Ayşe cannot be undone any more: it would change her balance.
        payment = client.get(f"/houses/{house_id}/settlements", headers=as_user(me)).json()[0]
        r = client.delete(f"/houses/{house_id}/settlements/{payment['id']}", headers=as_user(me))
        assert r.status_code == 409 and ayse in r.json()["detail"]

    def test_creator_removes_someone_only_at_zero(self, client, flat):
        house_id, me, ali, ayse = flat
        add_bill(client, house_id, ali, "300")
        r = client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user(me))
        assert r.status_code == 409 and r.json()["detail"].startswith("Ali is owed 200.00 TRY")
        r = client.delete(f"/houses/{house_id}/members/{me}", headers=as_user(ali))
        assert r.status_code == 403  # only the creator removes others
        pay(client, house_id, me, ali, "100")
        pay(client, house_id, ayse, ali, "100")
        assert client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user(ayse)).status_code == 403
        assert client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user(me)).status_code == 204
        assert client.get(f"/houses/{house_id}", headers=as_user(ali)).status_code == 404

    def test_last_member_cannot_leave_and_unknown_member_is_404(self, client, flat):
        house_id, me, ali, ayse = flat
        assert client.delete(f"/houses/{house_id}/members/nobody", headers=as_user(me)).status_code == 404
        assert (
            client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user("hm-outsider")).status_code
            == 404
        )
        assert client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user(ali)).status_code == 204
        assert client.delete(f"/houses/{house_id}/members/{ayse}", headers=as_user(me)).status_code == 204
        r = client.delete(f"/houses/{house_id}/members/{me}", headers=as_user(me))
        assert r.status_code == 409 and "last member" in r.json()["detail"]

    def test_someone_who_left_can_be_added_again(self, client, flat):
        house_id, me, ali, _ayse = flat
        assert client.delete(f"/houses/{house_id}/members/{ali}", headers=as_user(ali)).status_code == 204
        r = client.post(f"/houses/{house_id}/members", json={"user_id": ali}, headers=as_user(me))
        assert r.status_code == 201 and ali in [m["user_id"] for m in r.json()["members"]]

    def test_house_out_names_the_creator(self, client, flat):
        house_id, me, _ali, _ayse = flat
        assert client.get(f"/houses/{house_id}", headers=as_user(me)).json()["created_by"] == me
