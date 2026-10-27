"""The demo data command (scripts/seed_demo.py): what it creates, the guard and --reset.

It must never need the network: TCMB is replaced by a function that fails the test.
"""

import pytest
from sqlalchemy import delete

from app.db.models import FxRate
from app.integrations import tcmb
from app.services import clock, fx
from app.services.errors import UpstreamError
from scripts import seed_demo


@pytest.fixture
def no_tcmb(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("the demo seed must not call TCMB")

    monkeypatch.setattr(tcmb, "fetch_rates", fail)


def get(client, user, path):
    response = client.get(path, headers={"X-User-Id": user})
    assert response.status_code == 200, response.text
    return response


def test_seed_creates_the_demo_dataset(client, no_tcmb, capsys):
    user = "seed-demo-a"
    assert seed_demo.main(["--user", user]) == 0
    assert "Seeded demo data" in capsys.readouterr().out

    me = get(client, user, "/me").json()
    assert me["display_name"] == "Deniz"

    expenses = get(client, user, "/expenses?scope=personal&limit=500").json()
    assert len(expenses) == 33
    assert len({e["category"] for e in expenses}) >= 8
    usd = [e for e in expenses if e["original_currency"] == "USD"]
    assert len(usd) == 1
    assert usd[0]["fx_rate"] == "49.216000"
    assert usd[0]["original_total"] == "14.99"
    assert usd[0]["total"] == "737.75"  # 1499 * 49.2160 = 73774.784 minor units, rounded half-even

    dash = get(client, user, "/dashboard").json()
    assert dash["pending_inbox"] == 3
    levels = {b["budget"]["category"]: b["level"] for b in dash["budgets"]}
    assert levels["entertainment"] == "warning"
    assert {s["display_name"] for s in dash["upcoming_subscriptions"]} == {"Netflix", "Spotify"}

    [house] = get(client, user, "/houses").json()
    assert house["name"] == "Moda evi"
    assert {m["display_name"] for m in house["members"]} == {"Deniz", "Ali", "Ayşe"}
    bills = get(client, user, f"/houses/{house['id']}/expenses").json()
    assert {b["split_type"] for b in bills} == {"equal", "percent", "exact", "items"}
    for bill in bills:
        assert sum(s["amount_minor"] for s in bill["shares"]) == bill["total_minor"]
    assert len(get(client, user, f"/houses/{house['id']}/settlements").json()) == 1

    balances = get(client, user, f"/houses/{house['id']}/balances").json()
    assert sum(b["balance_minor"] for b in balances["balances"]) == 0
    owed = {t["from_user"]: t["amount"] for t in balances["transfers"]}
    assert owed == {f"{user}-ali": "6128.33", f"{user}-ayse": "11348.33"}
    # The flatmates see the same house when the dev user is switched to them.
    assert get(client, f"{user}-ali", "/houses").json()[0]["id"] == house["id"]

    inbox = get(client, user, "/inbox").json()
    assert {i["source"] for i in inbox} == {"statement"}
    assert all(i["status"] == "pending" for i in inbox)


def test_refuses_a_user_with_data_unless_reset(client, no_tcmb, capsys):
    user = "seed-demo-b"
    assert seed_demo.main(["--user", user]) == 0
    count = get(client, user, "/expenses").headers["X-Total-Count"]

    assert seed_demo.main(["--user", user]) == 1
    assert "--reset" in capsys.readouterr().err
    assert get(client, user, "/expenses").headers["X-Total-Count"] == count

    assert seed_demo.main(["--user", user, "--reset"]) == 0
    assert get(client, user, "/expenses").headers["X-Total-Count"] == count
    assert len(get(client, user, "/houses").json()) == 1
    assert len(get(client, user, "/inbox").json()) == 3


def test_reset_refuses_when_someone_else_shares_the_house(client, no_tcmb, capsys):
    user = "seed-demo-d"
    assert seed_demo.main(["--user", user]) == 0
    house_id = get(client, user, "/houses").json()[0]["id"]
    added = client.post(
        f"/houses/{house_id}/members", json={"user_id": "not-a-demo-user"}, headers={"X-User-Id": user}
    )
    assert added.status_code == 201, added.text
    count = get(client, user, "/expenses").headers["X-Total-Count"]

    assert seed_demo.main(["--user", user, "--reset"]) == 1
    assert "not-a-demo-user" in capsys.readouterr().err
    assert get(client, user, "/expenses").headers["X-Total-Count"] == count
    assert len(get(client, "not-a-demo-user", "/houses").json()) == 1


def test_a_usd_expense_added_live_converts_without_tcmb(client, db, no_tcmb, monkeypatch):
    user = "seed-demo-c"
    assert seed_demo.main(["--user", user]) == 0
    # Other tests cache made-up bulletins for today; on demo day today is not cached yet.
    db.execute(delete(FxRate).where(FxRate.rate_date == clock.today()))
    db.commit()

    def offline(*_args, **_kwargs):
        raise UpstreamError("no network")

    monkeypatch.setattr(tcmb, "fetch_rates", offline)
    fx._no_bulletin.clear()
    response = client.post(
        "/expenses",
        json={"merchant": "Steam", "total": "15.00", "currency": "USD", "category": "entertainment"},
        headers={"X-User-Id": user},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["total"] == "738.24"
    assert body["warnings"][0].startswith("Converted 15.00 USD to 738.24 TRY")
    assert any(w.startswith("Entertainment budget exceeded") for w in body["warnings"])
