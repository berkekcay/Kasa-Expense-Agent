"""House invite links: create, list, revoke, preview, accept (track HOUSE, US-HOUSE-02)."""

import datetime as dt
from types import SimpleNamespace

import pytest

from app.agents import house_agent
from app.agents.tools import house_tools
from app.db.models import HouseInvite
from app.db.session import session_for
from app.services import invites


def as_user(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


@pytest.fixture
def house(client):
    owner = "inv-owner"
    r = client.post("/houses", json={"name": "Moda evi"}, headers=as_user(owner))
    assert r.status_code == 201, r.text
    return r.json()["id"], owner


def create(client, house_id: int, user: str, **body) -> dict:
    r = client.post(f"/houses/{house_id}/invites", json=body or None, headers=as_user(user))
    assert r.status_code == 201, r.text
    return r.json()


def set_invite(code: str, **values) -> None:
    with session_for("test", system=True) as db:
        invite = db.query(HouseInvite).filter_by(code=code).one()
        for key, value in values.items():
            setattr(invite, key, value)
        db.commit()


def test_member_creates_a_link_with_defaults(client, house):
    house_id, owner = house
    body = create(client, house_id, owner)
    code = body["code"]
    assert len(code) == 10 and set(code) <= set(invites.CODE_ALPHABET)
    assert body["url"].endswith(f"/invite/{code}")
    assert (body["max_uses"], body["uses"]) == (10, 0)
    expires = dt.datetime.fromisoformat(body["expires_at"])
    assert expires.tzinfo is not None
    days = (expires - dt.datetime.now(dt.UTC)).total_seconds() / 86400
    assert 6.9 < days <= 7


def test_create_takes_days_and_max_uses_within_bounds(client, house):
    house_id, owner = house
    body = create(client, house_id, owner, days=2, max_uses=1)
    assert body["max_uses"] == 1
    for bad in ({"days": 0}, {"days": 31}, {"max_uses": 0}, {"max_uses": 51}):
        r = client.post(f"/houses/{house_id}/invites", json=bad, headers=as_user(owner))
        assert r.status_code == 422, bad


def test_non_members_get_404_on_house_invite_endpoints(client, house):
    house_id, owner = house
    invite_id = create(client, house_id, owner)["id"]
    stranger = as_user("inv-stranger")
    assert client.post(f"/houses/{house_id}/invites", headers=stranger).status_code == 404
    assert client.get(f"/houses/{house_id}/invites", headers=stranger).status_code == 404
    assert client.delete(f"/houses/{house_id}/invites/{invite_id}", headers=stranger).status_code == 404


def test_list_shows_only_usable_links_and_revoke_hides_them(client, house):
    house_id, owner = house
    keep = create(client, house_id, owner)
    gone = create(client, house_id, owner)
    old = create(client, house_id, owner)
    set_invite(old["code"], expires_at=invites.utcnow() - dt.timedelta(days=1))

    r = client.delete(f"/houses/{house_id}/invites/{gone['id']}", headers=as_user(owner))
    assert r.status_code == 204
    # Revoking twice is harmless; an id from another house is 404.
    assert (
        client.delete(f"/houses/{house_id}/invites/{gone['id']}", headers=as_user(owner)).status_code == 204
    )
    other = client.post("/houses", json={"name": "Other"}, headers=as_user(owner)).json()["id"]
    assert client.delete(f"/houses/{other}/invites/{keep['id']}", headers=as_user(owner)).status_code == 404

    ids = [i["id"] for i in client.get(f"/houses/{house_id}/invites", headers=as_user(owner)).json()]
    assert keep["id"] in ids
    assert gone["id"] not in ids and old["id"] not in ids


def test_preview_works_for_a_non_member(client, house):
    house_id, owner = house
    code = create(client, house_id, owner)["code"]
    r = client.get(f"/invites/{code}", headers=as_user("inv-guest"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["house_name"] == "Moda evi"
    assert body["invited_by"] == owner  # display name defaults to the id in dev mode
    assert body["usable"] is True and body["reason"] is None
    assert body["already_member"] is False and body["house_id"] is None
    # Typed by hand: lower case with a dash in the middle still works.
    typed = f"{code[:5]}-{code[5:]}".lower()
    assert client.get(f"/invites/{typed}", headers=as_user("inv-guest")).status_code == 200


def test_unknown_code_is_404(client):
    for code in ("NOPE234567", "x"):
        r = client.get(f"/invites/{code}", headers=as_user("inv-guest"))
        assert r.status_code == 404
        assert client.post(f"/invites/{code}/accept", headers=as_user("inv-guest")).status_code == 404


def test_accept_adds_the_member_and_bumps_uses(client, house):
    house_id, owner = house
    invite = create(client, house_id, owner)
    guest = "inv-joiner"
    r = client.post(f"/invites/{invite['code']}/accept", headers=as_user(guest))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == house_id
    assert guest in [m["user_id"] for m in r.json()["members"]]
    # The new member now sees the house like any other member.
    assert client.get(f"/houses/{house_id}", headers=as_user(guest)).status_code == 200
    listed = client.get(f"/houses/{house_id}/invites", headers=as_user(owner)).json()
    assert next(i for i in listed if i["id"] == invite["id"])["uses"] == 1

    # Accepting twice is harmless and does not use the link again.
    again = client.post(f"/invites/{invite['code']}/accept", headers=as_user(guest))
    assert again.status_code == 200 and again.json()["id"] == house_id
    members = [m["user_id"] for m in again.json()["members"]]
    assert members.count(guest) == 1
    listed = client.get(f"/houses/{house_id}/invites", headers=as_user(owner)).json()
    assert next(i for i in listed if i["id"] == invite["id"])["uses"] == 1

    preview = client.get(f"/invites/{invite['code']}", headers=as_user(guest)).json()
    assert preview["already_member"] is True and preview["house_id"] == house_id


@pytest.mark.parametrize(
    ("change", "reason", "words"),
    [
        ({"revoked_at": invites.utcnow()}, "revoked", "cancelled"),
        ({"expires_at": invites.utcnow() - dt.timedelta(minutes=1)}, "expired", "expired"),
        ({"uses": 3, "max_uses": 3}, "used_up", "maximum"),
    ],
)
def test_unusable_links_are_refused_with_the_reason(client, house, change, reason, words):
    house_id, owner = house
    code = create(client, house_id, owner)["code"]
    set_invite(code, **change)
    guest = as_user(f"inv-late-{reason}")

    preview = client.get(f"/invites/{code}", headers=guest).json()
    assert preview["usable"] is False and preview["reason"] == reason
    assert words in preview["message"]

    r = client.post(f"/invites/{code}/accept", headers=guest)
    assert r.status_code == 409
    assert words in r.json()["detail"]
    assert client.get(f"/houses/{house_id}", headers=guest).status_code == 404


def test_last_use_is_taken_once(client, house):
    house_id, owner = house
    code = create(client, house_id, owner, max_uses=1)["code"]
    assert client.post(f"/invites/{code}/accept", headers=as_user("inv-first")).status_code == 200
    r = client.post(f"/invites/{code}/accept", headers=as_user("inv-second"))
    assert r.status_code == 409 and "maximum" in r.json()["detail"]


def test_agent_tool_returns_a_link(client, house):
    house_id, owner = house
    result = house_tools.create_house_invite(house_id, SimpleNamespace(user_id=owner))
    assert result["status"] == "created", result
    assert result["url"].endswith(f"/invite/{result['code']}")
    assert result["house"] == "Moda evi" and result["max_uses"] == 10
    assert dt.datetime.fromisoformat(result["expires_at"]).utcoffset() == dt.timedelta(hours=3)

    stranger = house_tools.create_house_invite(house_id, SimpleNamespace(user_id="inv-nobody"))
    assert stranger["status"] == "error"


def test_house_agent_has_the_invite_tool():
    agent = house_agent.build_house_agent()
    assert house_tools.create_house_invite in agent.tools
    assert "create_house_invite" in house_agent.INSTRUCTION
