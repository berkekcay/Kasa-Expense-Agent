def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "agents_enabled": False}


def test_create_and_list_expenses_is_scoped_per_user(client):
    body = {
        "merchant": "Migros",
        "total": "123.45",
        "expense_date": "2026-10-01",
        "category": "groceries",
        "items": [{"description": "Bread", "amount": "23.45"}, {"description": "Cheese", "amount": "100"}],
    }
    r = client.post("/expenses", json=body, headers=as_user("api-alice"))
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["total"] == "123.45" and created["total_minor"] == 12345
    assert [i["amount_minor"] for i in created["items"]] == [2345, 10000]
    assert created["owner_id"] == "api-alice"

    assert [e["id"] for e in client.get("/expenses", headers=as_user("api-alice")).json()] == [created["id"]]
    assert client.get("/expenses", headers=as_user("api-bob")).json() == []


def test_default_dev_user_without_header(client):
    r = client.post("/expenses", json={"merchant": "Kahve", "total": 55})
    assert r.status_code == 201
    assert r.json()["owner_id"] == "dev-user"


def test_expense_validation(client):
    assert client.post("/expenses", json={"merchant": "X", "total": "1.234"}).status_code == 422
    assert client.post("/expenses", json={"merchant": "X", "total": "-5"}).status_code == 422
    assert client.post("/expenses", json={"merchant": "", "total": "5"}).status_code == 422
    assert client.get("/expenses", headers={"X-User-Id": "bad id!"}).status_code == 400


def test_house_equal_split_balances_and_settle_up(client):
    ali = as_user("api-ali")
    r = client.post("/houses", json={"name": "Moda flat"}, headers=ali)
    assert r.status_code == 201, r.text
    house_id = r.json()["id"]
    for member in ("api-ayse", "api-mehmet"):
        r = client.post(f"/houses/{house_id}/members", json={"user_id": member}, headers=ali)
        assert r.status_code == 201, r.text
    assert [m["user_id"] for m in r.json()["members"]] == ["api-ali", "api-ayse", "api-mehmet"]

    # 100.00 split 3 ways -> 33.34 / 33.33 / 33.33 (remainder to the first member)
    r = client.post(
        f"/houses/{house_id}/expenses", json={"merchant": "Electricity", "total": "100"}, headers=ali
    )
    assert r.status_code == 201, r.text
    assert [s["amount"] for s in r.json()["shares"]] == ["33.34", "33.33", "33.33"]

    r = client.post(
        f"/houses/{house_id}/expenses",
        json={"merchant": "Internet", "total": "30", "paid_by": "api-ayse"},
        headers=as_user("api-mehmet"),
    )
    assert r.status_code == 201, r.text

    r = client.get(f"/houses/{house_id}/balances", headers=as_user("api-ayse"))
    assert r.status_code == 200
    data = r.json()
    balances = {b["user_id"]: b["balance_minor"] for b in data["balances"]}
    assert balances == {"api-ali": 5666, "api-ayse": -1333, "api-mehmet": -4333}
    assert sum(balances.values()) == 0
    assert [(t["from_user"], t["to_user"], t["amount"]) for t in data["transfers"]] == [
        ("api-mehmet", "api-ali", "43.33"),
        ("api-ayse", "api-ali", "13.33"),
    ]


def test_house_access_is_members_only(client):
    r = client.post("/houses", json={"name": "Private"}, headers=as_user("api-owner"))
    house_id = r.json()["id"]
    outsider = as_user("api-stranger")
    assert client.get(f"/houses/{house_id}/balances", headers=outsider).status_code == 404
    assert (
        client.post(f"/houses/{house_id}/members", json={"user_id": "x"}, headers=outsider).status_code == 404
    )
    r = client.post(
        f"/houses/{house_id}/expenses",
        json={"merchant": "Rent", "total": "10", "split_between": ["api-owner", "api-stranger"]},
        headers=as_user("api-owner"),
    )
    assert r.status_code == 403
    assert client.get("/houses", headers=outsider).json() == []


def test_agent_endpoints_return_503_without_api_key(client):
    r = client.post("/chat", json={"message": "How much did I spend?"})
    assert r.status_code == 503
    assert "GOOGLE_API_KEY" in r.json()["detail"]
    r = client.post("/receipts", files={"file": ("r.jpg", b"\xff\xd8fake", "image/jpeg")})
    assert r.status_code == 503
