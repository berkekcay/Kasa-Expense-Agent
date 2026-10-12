"""Sprint 2 foundation: expense pipeline, settlements, auth modes, internal endpoints, stubs."""

import base64
import json

import pytest

from app import auth
from app.api import internal
from app.config import get_settings
from app.db.models import User
from app.db.session import session_for
from app.services.errors import Conflict
from app.services.expenses import ExpenseInput, add_expense


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def test_categories_endpoint_and_normalised_storage(client):
    r = client.get("/categories")
    assert r.status_code == 200 and "groceries" in r.json()["categories"]
    r = client.post("/expenses", json={"merchant": "BİM", "total": "42.10", "category": "Market"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category"] == "groceries"
    assert body["warnings"] == [] and body["split_type"] is None and body["original_currency"] is None


def test_foreign_currency_expense_is_kept_with_a_warning_until_fx_lands(client):
    r = client.post("/expenses", json={"merchant": "Amazon.de", "total": "12", "currency": "EUR"})
    assert r.status_code == 201
    assert r.json()["currency"] == "EUR"
    assert "conversion" in r.json()["warnings"][0]


def test_external_ref_dedupe(db):
    data = ExpenseInput("Trendyol", "349.90", category="alışveriş")
    first = add_expense(db, "dedupe-user", data, source="email", external_ref="gmail:18c2f")
    assert first.expense.category == "shopping" and first.expense.external_ref == "gmail:18c2f"
    with pytest.raises(Conflict):
        add_expense(db, "dedupe-user", data, source="email", external_ref="gmail:18c2f")
    # Same ref from another source or for another user is fine; manual rows have no ref.
    add_expense(db, "dedupe-user", data, source="statement", external_ref="gmail:18c2f")
    add_expense(db, "someone-else", data, source="email", external_ref="gmail:18c2f")
    add_expense(db, "dedupe-user", data)
    add_expense(db, "dedupe-user", data)


def _house(client, owner: str, members: list[str]) -> int:
    house_id = client.post("/houses", json={"name": "Settle flat"}, headers=as_user(owner)).json()["id"]
    for m in members:
        client.post(f"/houses/{house_id}/members", json={"user_id": m}, headers=as_user(owner))
    return house_id


def test_recorded_payments_reduce_balances(client):
    ali, ayse, mehmet = "set-ali", "set-ayse", "set-mehmet"
    house_id = _house(client, ali, [ayse, mehmet])
    client.post(
        f"/houses/{house_id}/expenses", json={"merchant": "Rent", "total": "300"}, headers=as_user(ali)
    )

    def balances():
        r = client.get(f"/houses/{house_id}/balances", headers=as_user(ayse))
        return {b["user_id"]: b["balance_minor"] for b in r.json()["balances"]}, r.json()["transfers"]

    assert balances()[0] == {ali: 20000, ayse: -10000, mehmet: -10000}

    r = client.post(
        f"/houses/{house_id}/settlements",
        json={"from_user": ayse, "to_user": ali, "amount": "100", "note": "IBAN"},
        headers=as_user(ayse),
    )
    assert r.status_code == 201, r.text
    assert r.json()["amount_minor"] == 10000 and r.json()["created_by"] == ayse
    state, transfers = balances()
    assert state == {ali: 10000, ayse: 0, mehmet: -10000}
    assert [(t["from_user"], t["to_user"], t["amount"]) for t in transfers] == [(mehmet, ali, "100.00")]

    # A partial payment leaves the rest of the debt.
    client.post(
        f"/houses/{house_id}/settlements",
        json={"from_user": mehmet, "to_user": ali, "amount": "40.50"},
        headers=as_user(mehmet),
    )
    assert balances()[0] == {ali: 5950, ayse: 0, mehmet: -5950}
    listed = client.get(f"/houses/{house_id}/settlements", headers=as_user(ali)).json()
    assert sorted(s["amount"] for s in listed) == ["100.00", "40.50"]


def test_settlement_validation(client):
    house_id = _house(client, "val-a", ["val-b"])
    url = f"/houses/{house_id}/settlements"
    owner = as_user("val-a")

    def post(body):
        return client.post(url, json=body, headers=owner).status_code

    assert post({"from_user": "val-a", "to_user": "val-a", "amount": "5"}) == 422
    assert post({"from_user": "val-a", "to_user": "stranger", "amount": "5"}) == 403
    assert post({"from_user": "val-a", "to_user": "val-b", "amount": "0"}) == 422
    assert client.get(url, headers=as_user("stranger")).status_code == 404


class TestFirebaseAuth:
    @pytest.fixture
    def firebase(self, monkeypatch):
        monkeypatch.setattr(get_settings(), "firebase_project_id", "kasa-test")
        calls = []

        def fake_verify(token, project_id):
            calls.append((token, project_id))
            if token != "good-token":
                raise ValueError("bad signature")
            return {
                "sub": "fb-uid-123",
                "user_id": "fb-uid-123",
                "email": "ayse@example.com",
                "email_verified": True,
                "name": "Ayşe Yılmaz",
            }

        monkeypatch.setattr(auth, "verify_firebase_token", fake_verify)
        return calls

    def test_requires_bearer_token(self, client, firebase):
        assert client.get("/expenses").status_code == 401
        assert client.get("/expenses", headers=as_user("spoofed")).status_code == 401  # header ignored
        assert client.get("/expenses", headers={"Authorization": "Bearer nope"}).status_code == 401

    def test_valid_token_sets_user_and_profile(self, client, firebase):
        headers = {"Authorization": "Bearer good-token", "X-User-Id": "spoofed"}
        r = client.post("/expenses", json={"merchant": "Kahve", "total": "60"}, headers=headers)
        assert r.status_code == 201
        assert r.json()["owner_id"] == "fb-uid-123"
        assert firebase[-1] == ("good-token", "kasa-test")
        with session_for("fb-uid-123") as db:
            user = db.get(User, "fb-uid-123")
            assert user.email == "ayse@example.com" and user.display_name == "Ayşe Yılmaz"


class TestInternalEndpoints:
    def test_disabled_without_settings(self, client):
        assert client.post("/internal/gmail/sync-all").status_code == 503
        assert client.post("/internal/gmail/push", json={}).status_code == 503

    def test_task_token(self, client, monkeypatch):
        monkeypatch.setattr(get_settings(), "internal_task_token", "s3cret")
        assert client.post("/internal/fx/refresh").status_code == 401
        assert client.post("/internal/fx/refresh", headers={"X-Kasa-Task-Token": "wrong"}).status_code == 401
        # Authorised; the service itself is still a stub (track MONEY).
        assert client.post("/internal/fx/refresh", headers={"X-Kasa-Task-Token": "s3cret"}).status_code == 501

    def test_pubsub_push_checks_oidc_token(self, client, monkeypatch):
        settings = get_settings()
        monkeypatch.setattr(settings, "pubsub_push_audience", "https://api.kasa.test/internal/gmail/push")
        monkeypatch.setattr(settings, "pubsub_push_service_account", "push@kasa.iam.gserviceaccount.com")

        def fake_verify(token, audience):
            if token == "wrong-sa":
                return {"email": "evil@x.iam.gserviceaccount.com", "email_verified": True}
            if token != "good":
                raise ValueError("bad token")
            return {"email": "push@kasa.iam.gserviceaccount.com", "email_verified": True}

        pushed = []

        async def fake_handle(email, history_id):
            pushed.append((email, history_id))

        monkeypatch.setattr(internal, "verify_pubsub_token", fake_verify)
        monkeypatch.setattr(internal.gmail_sync, "handle_push", fake_handle)
        payload = json.dumps({"emailAddress": "ayse@gmail.com", "historyId": 991}).encode()
        body = {"message": {"data": base64.b64encode(payload).decode(), "messageId": "1"}}

        def push(token: str | None, json_body=body):
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            return client.post("/internal/gmail/push", json=json_body, headers=headers).status_code

        assert push(None) == 401
        assert push("bad") == 401
        assert push("wrong-sa") == 403
        assert push("good") == 204
        assert pushed == [("ayse@gmail.com", "991")]
        # Malformed messages are acknowledged so Pub/Sub does not retry them forever.
        assert push("good", {"message": {}}) == 204
        assert len(pushed) == 1


@pytest.mark.parametrize(
    "path",
    ["/budgets", "/subscriptions", "/dashboard", "/fx/rates/EUR", "/inbox", "/integrations/google/status"],
)
def test_track_endpoints_are_registered(client, path):
    """Routers exist now; until a track lands its endpoints answer 501."""
    assert client.get(path).status_code == 501
