"""Personal expenses: server-side filters and paging, edit, delete; GET/PATCH /me."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from app.db.models import ExpenseItem, InboxItem


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


@pytest.fixture
def user() -> str:
    return f"ex-{uuid.uuid4().hex[:8]}"


def add(client, user: str, merchant: str, total: str, date: str, **extra) -> dict:
    r = client.post(
        "/expenses",
        json={"merchant": merchant, "total": total, "expense_date": date, **extra},
        headers=as_user(user),
    )
    assert r.status_code == 201, r.text
    return r.json()


def house_with_bill(
    client, payer: str, other: str, total: str = "90", date: str = "2026-10-05"
) -> tuple[int, dict]:
    house_id = client.post("/houses", json={"name": "Flat"}, headers=as_user(payer)).json()["id"]
    assert (
        client.post(
            f"/houses/{house_id}/members", json={"user_id": other}, headers=as_user(payer)
        ).status_code
        == 201
    )
    r = client.post(
        f"/houses/{house_id}/expenses",
        json={"merchant": "Internet", "total": total, "expense_date": date, "category": "utilities"},
        headers=as_user(payer),
    )
    assert r.status_code == 201, r.text
    return house_id, r.json()


class TestFilters:
    @pytest.fixture
    def data(self, client, user):
        add(client, user, "Migros", "100", "2026-10-03", category="groceries")
        add(client, user, "BIM", "50", "2026-10-12", category="groceries")
        add(client, user, "Metro", "20", "2026-09-30", category="transport")
        add(client, user, "Kitap", "70", "2026-09-02")  # no category
        house_with_bill(client, user, f"{user}-flatmate")
        return user

    def ids(self, client, user, query: str = "") -> tuple[list[str], int]:
        r = client.get(f"/expenses{query}", headers=as_user(user))
        assert r.status_code == 200, r.text
        return [e["merchant"] for e in r.json()], int(r.headers["X-Total-Count"])

    def test_default_is_all_own_expenses_newest_first(self, client, data):
        merchants, total = self.ids(client, data)
        assert merchants == ["BIM", "Internet", "Migros", "Metro", "Kitap"] and total == 5

    def test_month_category_source_and_scope(self, client, data):
        assert self.ids(client, data, "?month=2026-10") == (["BIM", "Internet", "Migros"], 3)
        assert self.ids(client, data, "?month=2026-09&category=transport") == (["Metro"], 1)
        assert self.ids(client, data, "?category=none") == (["Kitap"], 1)
        assert self.ids(client, data, "?scope=house") == (["Internet"], 1)
        assert self.ids(client, data, "?scope=personal&month=2026-10") == (["BIM", "Migros"], 2)
        assert self.ids(client, data, "?source=receipt") == ([], 0)

    def test_paging_keeps_the_total(self, client, data):
        assert self.ids(client, data, "?limit=2") == (["BIM", "Internet"], 5)
        assert self.ids(client, data, "?limit=2&offset=2") == (["Migros", "Metro"], 5)
        assert self.ids(client, data, "?limit=2&offset=4") == (["Kitap"], 5)
        assert self.ids(client, data, "?limit=2&offset=10") == ([], 5)

    @pytest.mark.parametrize(
        "query",
        ["?month=2026-13", "?month=10-2026", "?category=snacks", "?source=fax", "?scope=friends",
         "?limit=0", "?offset=-1"],
    )  # fmt: skip
    def test_bad_filters_are_422(self, client, user, query):
        assert client.get(f"/expenses{query}", headers=as_user(user)).status_code == 422

    def test_total_count_header_is_exposed_to_the_browser(self, client, user):
        r = client.get("/expenses", headers={**as_user(user), "Origin": "http://localhost:3000"})
        assert "x-total-count" in r.headers["access-control-expose-headers"].lower()

    def test_only_own_expenses(self, client, data):
        assert self.ids(client, f"{data}-flatmate") == ([], 0)


class TestEdit:
    def test_patch_changes_only_the_given_fields(self, client, user):
        e = add(client, user, "Migros", "84.90", "2026-10-03", category="groceries", note="weekly")
        r = client.patch(
            f"/expenses/{e['id']}",
            json={"merchant": "  Migros Jet ", "expense_date": "2026-10-04", "category": "Kafe"},
            headers=as_user(user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["merchant"] == "Migros Jet" and body["expense_date"] == "2026-10-04"
        assert body["category"] == "food" and body["note"] == "weekly" and body["total"] == "84.90"
        cleared = client.patch(
            f"/expenses/{e['id']}", json={"note": None, "category": None}, headers=as_user(user)
        )
        assert cleared.json()["note"] is None and cleared.json()["category"] is None

    @pytest.mark.parametrize(
        ("body", "detail"),
        [
            ({"total": "10"}, "delete the expense and add it again"),
            ({"currency": "USD", "note": "x"}, "currency cannot be changed"),
            ({"merchant": ""}, ""),
            ({"merchant": None}, "merchant is required"),
            ({"expense_date": None}, "expense_date"),
            ({"owner_id": "someone"}, "Extra inputs"),
        ],
    )
    def test_patch_validation(self, client, user, body, detail):
        e = add(client, user, "Shop", "10", "2026-10-03")
        r = client.patch(f"/expenses/{e['id']}", json=body, headers=as_user(user))
        assert r.status_code == 422 and detail in r.text

    def test_patch_someone_elses_expense_is_404(self, client, user):
        e = add(client, user, "Shop", "10", "2026-10-03")
        r = client.patch(f"/expenses/{e['id']}", json={"note": "mine now"}, headers=as_user(f"{user}-other"))
        assert r.status_code == 404
        assert client.patch("/expenses/999999", json={"note": "x"}, headers=as_user(user)).status_code == 404

    def test_payer_can_edit_a_house_bill(self, client, user):
        _house_id, bill = house_with_bill(client, user, f"{user}-flatmate")
        r = client.patch(
            f"/expenses/{bill['id']}", json={"merchant": "Fiber internet"}, headers=as_user(user)
        )
        assert r.status_code == 200 and r.json()["shares"] == bill["shares"]
        flatmate = as_user(f"{user}-flatmate")
        assert (
            client.patch(f"/expenses/{bill['id']}", json={"note": "x"}, headers=flatmate).status_code == 404
        )


class TestDelete:
    def test_delete_own_expense_with_items(self, client, db, user):
        e = add(client, user, "Market", "30", "2026-10-03", items=[{"description": "Milk", "amount": "30"}])
        assert client.delete(f"/expenses/{e['id']}", headers=as_user(user)).status_code == 204
        assert client.get("/expenses", headers=as_user(user)).json() == []
        assert db.scalars(select(ExpenseItem).where(ExpenseItem.expense_id == e["id"])).all() == []
        assert client.delete(f"/expenses/{e['id']}", headers=as_user(user)).status_code == 404

    def test_others_get_404(self, client, user):
        e = add(client, user, "Market", "30", "2026-10-03")
        assert client.delete(f"/expenses/{e['id']}", headers=as_user(f"{user}-x")).status_code == 404
        assert len(client.get("/expenses", headers=as_user(user)).json()) == 1

    def test_house_expense_is_409_and_points_to_the_house_endpoint(self, client, user):
        house_id, bill = house_with_bill(client, user, f"{user}-flatmate")
        r = client.delete(f"/expenses/{bill['id']}", headers=as_user(user))
        assert r.status_code == 409
        assert f"DELETE /houses/{house_id}/expenses/{bill['id']}" in r.json()["detail"]

    def test_approved_inbox_item_keeps_its_row(self, client, db, user):
        e = add(client, user, "Trendyol", "99", "2026-10-03")
        item = InboxItem(
            user_id=user,
            source="email",
            external_ref=f"m-{user}",
            received_at=dt.datetime(2026, 10, 3, 9, 0, tzinfo=dt.UTC).replace(tzinfo=None),
            title="Order",
            status="approved",
            expense_id=e["id"],
        )
        db.add(item)
        db.commit()
        assert client.delete(f"/expenses/{e['id']}", headers=as_user(user)).status_code == 204
        db.refresh(item)
        assert item.expense_id is None and item.status == "approved"


class TestMe:
    def test_get_and_patch_display_name(self, client, user):
        me = client.get("/me", headers=as_user(user)).json()
        assert me == {"user_id": user, "display_name": user, "email": None}
        r = client.patch("/me", json={"display_name": "  Deniz Yılmaz  "}, headers=as_user(user))
        assert r.status_code == 200 and r.json()["display_name"] == "Deniz Yılmaz"
        assert client.get("/me", headers=as_user(user)).json()["display_name"] == "Deniz Yılmaz"

    def test_house_members_show_the_new_name(self, client, user):
        house_id = client.post("/houses", json={"name": "Flat"}, headers=as_user(user)).json()["id"]
        client.patch("/me", json={"display_name": "Deniz"}, headers=as_user(user))
        house = client.get(f"/houses/{house_id}", headers=as_user(user)).json()
        assert house["members"] == [{"user_id": user, "display_name": "Deniz"}]

    @pytest.mark.parametrize("name", ["", "   ", "x" * 101, " " + "y" * 101])
    def test_name_must_be_1_to_100_characters(self, client, user, name):
        assert client.patch("/me", json={"display_name": name}, headers=as_user(user)).status_code == 422

    def test_100_characters_after_trimming_is_fine(self, client, user):
        r = client.patch("/me", json={"display_name": "  " + "z" * 100 + "  "}, headers=as_user(user))
        assert r.status_code == 200 and r.json()["display_name"] == "z" * 100
