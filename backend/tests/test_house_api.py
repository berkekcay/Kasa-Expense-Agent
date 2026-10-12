"""House API: split expenses of every type, balances with payments, payment undo (track HOUSE)."""

from decimal import Decimal

import pytest

from app.services import fx, houses
from app.services.errors import Forbidden, InvalidInput
from app.services.expenses import ExpenseInput, ItemInput


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def make_house(client, owner: str, members: list[str], name: str = "Split flat") -> int:
    house_id = client.post("/houses", json={"name": name}, headers=as_user(owner)).json()["id"]
    for m in members:
        r = client.post(f"/houses/{house_id}/members", json={"user_id": m}, headers=as_user(owner))
        assert r.status_code == 201, r.text
    return house_id


def balances(client, house_id: int, user: str) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    body = client.get(f"/houses/{house_id}/balances", headers=as_user(user)).json()
    return (
        {b["user_id"]: b["balance_minor"] for b in body["balances"]},
        [(t["from_user"], t["to_user"], t["amount_minor"]) for t in body["transfers"]],
    )


@pytest.fixture
def flat(client):
    ali, ayse, me = "hs-ali", "hs-ayse", "hs-me"
    return make_house(client, me, [ali, ayse]), me, ali, ayse


class TestSplitEndpoint:
    def test_percent_split(self, client, flat):
        house_id, me, ali, ayse = flat
        r = client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "percent",
                "merchant": "Fatura",
                "total": "600",
                "percents": {ali: "50", ayse: 30, me: "20"},
            },
            headers=as_user(me),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["split_type"] == "percent" and body["owner_id"] == me and body["house_id"] == house_id
        assert {s["user_id"]: s["amount"] for s in body["shares"]} == {
            ali: "300.00",
            ayse: "180.00",
            me: "120.00",
        }
        assert balances(client, house_id, ali)[0] == {me: 48000, ali: -30000, ayse: -18000}

    def test_exact_split_and_paid_by(self, client, flat):
        house_id, me, ali, ayse = flat
        r = client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "exact",
                "merchant": "Market",
                "total": "300",
                "paid_by": ayse,
                "amounts": {ali: "120.00", ayse: "180"},
            },
            headers=as_user(me),
        )
        assert r.status_code == 201, r.text
        assert r.json()["owner_id"] == ayse
        assert {s["user_id"]: s["amount_minor"] for s in r.json()["shares"]} == {ali: 12000, ayse: 18000}

    def test_items_split_stores_assignees_and_lists_them(self, client, flat):
        house_id, me, ali, ayse = flat
        r = client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "items",
                "merchant": "Migros",
                "total": "110",
                "participants": [me, ali],
                "items": [
                    {"description": "Peynir", "amount": "60", "assignees": [ali]},
                    {"description": "Ekmek", "amount": "40"},
                ],
            },
            headers=as_user(me),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # items 100, total 110: ali had 80 -> 88, me had 20 -> 22
        assert {s["user_id"]: s["amount"] for s in body["shares"]} == {me: "22.00", ali: "88.00"}
        assert any("difference was spread" in w for w in body["warnings"])
        listed = client.get(f"/houses/{house_id}/expenses", headers=as_user(ayse)).json()
        expense = next(e for e in listed if e["id"] == body["id"])
        assert expense["split_type"] == "items"
        assert [(i["description"], i["assignees"]) for i in expense["items"]] == [
            ("Peynir", [ali]),
            ("Ekmek", [me, ali]),
        ]

    def test_equal_split_through_split_endpoint(self, client, flat):
        house_id, me, ali, ayse = flat
        r = client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "equal",
                "merchant": "İnternet",
                "total": "100",
                "participants": [ali, ayse, me],
            },
            headers=as_user(me),
        )
        assert r.status_code == 201
        assert [s["amount_minor"] for s in r.json()["shares"]] == [3334, 3333, 3333]

    @pytest.mark.parametrize(
        ("extra", "status", "detail"),
        [
            ({"split_type": "percent", "percents": {"hs-ali": "50", "hs-ayse": "40"}}, 422, "add up to 100"),
            ({"split_type": "percent", "percents": {"hs-ali": "50", "stranger": "50"}}, 403, "not members"),
            ({"split_type": "percent", "percents": {"hs-ali": "50.001", "hs-me": "49.999"}}, 422, None),
            ({"split_type": "exact", "amounts": {"hs-ali": "100", "hs-ayse": "100"}}, 422, "50.00 missing"),
            (
                {
                    "split_type": "items",
                    "items": [{"description": "x", "amount": "5", "assignees": ["nope"]}],
                },
                403,
                None,
            ),
            ({"split_type": "items", "items": []}, 422, None),
            ({"split_type": "weird"}, 422, None),
            ({"split_type": "equal", "paid_by": "stranger"}, 403, "stranger"),
        ],
    )
    def test_validation_errors(self, client, flat, extra, status, detail):
        house_id, me, _ali, _ayse = flat
        body = {"merchant": "Bad", "total": "250", **extra}
        r = client.post(f"/houses/{house_id}/expenses/split", json=body, headers=as_user(me))
        assert r.status_code == status, r.text
        if detail:
            assert detail in str(r.json()["detail"])

    def test_non_members_get_404(self, client, flat):
        house_id, *_ = flat
        body = {"split_type": "equal", "merchant": "x", "total": "1"}
        assert (
            client.post(
                f"/houses/{house_id}/expenses/split", json=body, headers=as_user("hs-out")
            ).status_code
            == 404
        )

    def test_old_equal_endpoint_still_works(self, client, flat):
        house_id, me, ali, ayse = flat
        r = client.post(
            f"/houses/{house_id}/expenses",
            json={"merchant": "Su", "total": "90", "split_between": [ali, ayse]},
            headers=as_user(me),
        )
        assert r.status_code == 201
        assert r.json()["split_type"] == "equal" and r.json()["warnings"] == []
        assert {s["user_id"] for s in r.json()["shares"]} == {ali, ayse}

    def test_openapi_documents_the_split_body(self, client):
        spec = client.get("/openapi.json").json()
        op = spec["paths"]["/houses/{house_id}/expenses/split"]["post"]
        assert "percent" in op["requestBody"]["content"]["application/json"]["examples"]
        assert "/houses/{house_id}/reminders/{reminder_id}" in spec["paths"]


class TestPayments:
    def test_overpayment_is_refused_unless_allowed(self, client):
        ali, ayse, mehmet = "op-ali", "op-ayse", "op-mehmet"
        house_id = make_house(client, ali, [ayse, mehmet])
        client.post(
            f"/houses/{house_id}/expenses", json={"merchant": "Kira", "total": "300"}, headers=as_user(ali)
        )
        url = f"/houses/{house_id}/settlements"

        r = client.post(url, json={"from_user": ayse, "to_user": ali, "amount": "150"}, headers=as_user(ayse))
        assert r.status_code == 409
        assert "at most 100.00 TRY" in r.json()["detail"]
        # Paying someone who is not owed anything is refused too.
        r = client.post(
            url, json={"from_user": ayse, "to_user": mehmet, "amount": "10"}, headers=as_user(ayse)
        )
        assert r.status_code == 409 and "not owed anything" in r.json()["detail"]
        # Exactly the debt is fine; then nothing more can be paid.
        assert (
            client.post(
                url, json={"from_user": ayse, "to_user": ali, "amount": "100"}, headers=as_user(ayse)
            ).status_code
            == 201
        )
        r = client.post(url, json={"from_user": ayse, "to_user": ali, "amount": "1"}, headers=as_user(ayse))
        assert r.status_code == 409 and "owes nothing" in r.json()["detail"]
        # A deliberate advance goes through and flips the sign.
        r = client.post(
            url,
            json={"from_user": ayse, "to_user": ali, "amount": "20", "allow_overpayment": True},
            headers=as_user(ayse),
        )
        assert r.status_code == 201
        assert balances(client, house_id, ali)[0] == {ali: 8000, ayse: 2000, mehmet: -10000}

    def test_delete_payment_by_creator_only(self, client):
        ali, ayse = "del-ali", "del-ayse"
        house_id = make_house(client, ali, [ayse])
        client.post(
            f"/houses/{house_id}/expenses", json={"merchant": "Gaz", "total": "100"}, headers=as_user(ali)
        )
        before = balances(client, house_id, ali)
        r = client.post(
            f"/houses/{house_id}/settlements",
            json={"from_user": ayse, "to_user": ali, "amount": "50"},
            headers=as_user(ayse),
        )
        payment_id = r.json()["id"]
        assert balances(client, house_id, ali)[0] == {ali: 0, ayse: 0}
        url = f"/houses/{house_id}/settlements/{payment_id}"
        assert client.delete(url, headers=as_user(ali)).status_code == 403
        assert client.delete(url, headers=as_user("del-outsider")).status_code == 404
        other_house = make_house(client, ayse, [], name="Other")
        assert (
            client.delete(
                f"/houses/{other_house}/settlements/{payment_id}", headers=as_user(ayse)
            ).status_code
            == 404
        )
        assert client.delete(url, headers=as_user(ayse)).status_code == 204
        assert client.delete(url, headers=as_user(ayse)).status_code == 404
        assert balances(client, house_id, ali) == before
        assert client.get(f"/houses/{house_id}/settlements", headers=as_user(ali)).json() == []

    def test_payments_feed_settle_up(self, client):
        a, b, c = "fs-a", "fs-b", "fs-c"
        house_id = make_house(client, a, [b, c])
        client.post(
            f"/houses/{house_id}/expenses/split",
            json={
                "split_type": "percent",
                "merchant": "Bill",
                "total": "100",
                "percents": {a: "20", b: "50", c: "30"},
            },
            headers=as_user(a),
        )
        assert balances(client, house_id, a)[1] == [(b, a, 5000), (c, a, 3000)]
        client.post(
            f"/houses/{house_id}/settlements",
            json={"from_user": b, "to_user": a, "amount": "20"},
            headers=as_user(b),
        )
        assert balances(client, house_id, a)[1] == [(b, a, 3000), (c, a, 3000)]
        listed = client.get(f"/houses/{house_id}/settlements", headers=as_user(c)).json()
        assert [(s["from_user"], s["amount"]) for s in listed] == [(b, "20.00")]


class TestServiceDirect:
    """Service-level checks that are awkward over HTTP."""

    def _house(self, db, owner, members):
        house = houses.create_house(db, owner, "Service flat")
        for m in members:
            houses.add_member(db, owner, house.id, m)
        return house.id

    def test_converted_expense_splits_the_converted_amounts(self, db, monkeypatch):
        house_id = self._house(db, "fxs-a", ["fxs-b"])

        def fake_convert(_db, expense, base):
            if expense.currency == base:
                return []
            expense.original_currency, expense.original_total_minor = expense.currency, expense.total_minor
            expense.currency, expense.fx_rate = base, Decimal(2)
            expense.total_minor *= 2
            for item in expense.items:
                item.amount_minor *= 2
            return ["converted at 2"]

        monkeypatch.setattr(fx, "apply_base_currency", fake_convert)
        expense, warnings = houses.add_split_expense(
            db,
            "fxs-a",
            house_id,
            ExpenseInput(
                "Amazon.de", "15", currency="EUR", items=[ItemInput("A", "10"), ItemInput("B", "5")]
            ),
            split_type="items",
            item_assignees=[["fxs-a"], ["fxs-b"]],
        )
        assert expense.currency == "TRY" and expense.total_minor == 3000
        assert {s.user_id: s.amount_minor for s in expense.shares} == {"fxs-a": 2000, "fxs-b": 1000}
        assert warnings == ["converted at 2"]

    def test_bad_inputs(self, db):
        house_id = self._house(db, "bad-a", ["bad-b"])
        data = ExpenseInput("x", "10")
        with pytest.raises(InvalidInput, match="needs percents"):
            houses.add_split_expense(db, "bad-a", house_id, data, split_type="percent")
        with pytest.raises(InvalidInput, match="do not match"):
            houses.add_split_expense(
                db,
                "bad-a",
                house_id,
                data,
                split_type="percent",
                percents={"bad-a": "100"},
                participants=["bad-b"],
            )
        with pytest.raises(InvalidInput, match="receipt lines"):
            houses.add_split_expense(db, "bad-a", house_id, data, split_type="items")
        with pytest.raises(InvalidInput, match="1 entries but there are 2 items"):
            houses.add_split_expense(
                db,
                "bad-a",
                house_id,
                ExpenseInput("x", "10", items=[ItemInput("a", "5"), ItemInput("b", "5")]),
                split_type="items",
                item_assignees=[["bad-a"]],
            )
        with pytest.raises(InvalidInput, match="too many decimal"):
            houses.add_split_expense(
                db,
                "bad-a",
                house_id,
                data,
                split_type="exact",
                exact_amounts={"bad-a": "9.999", "bad-b": "0.001"},
            )
        with pytest.raises(InvalidInput, match="unique"):
            houses.add_split_expense(
                db, "bad-a", house_id, data, split_type="equal", participants=["bad-a", "bad-a"]
            )
        with pytest.raises(Forbidden):
            houses.add_split_expense(
                db,
                "bad-a",
                house_id,
                ExpenseInput("x", "10", items=[ItemInput("a", "10")]),
                split_type="items",
                item_assignees=[["ghost"]],
            )
        assert houses.list_house_expenses(db, "bad-a", house_id) == []
