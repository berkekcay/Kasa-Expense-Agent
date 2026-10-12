"""Settle-up reminders and the Google Calendar client, with a fake HTTP transport (track HOUSE)."""

import datetime as dt
import json

import httpx
import pytest
from google.oauth2.credentials import Credentials

from app.db.models import User
from app.integrations import google_calendar, google_oauth
from app.services import clock, houses, reminders
from app.services.errors import Forbidden, InvalidInput, NotFound, UpstreamError
from app.services.expenses import ExpenseInput

DUE = clock.today() + dt.timedelta(days=3)


class FakeCalendar:
    """Records Calendar API calls and answers like Google would."""

    def __init__(self, fail_create: bool = False, delete_status: int = 204):
        self.calls: list[httpx.Request] = []
        self.fail_create = fail_create
        self.delete_status = delete_status
        self.next_id = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.method == "POST":
            if self.fail_create:
                return httpx.Response(
                    403, json={"error": {"code": 403, "message": "Insufficient Permission"}}
                )
            self.next_id += 1
            return httpx.Response(200, json={"id": f"evt{self.next_id}", "status": "confirmed"})
        if request.method == "DELETE":
            return httpx.Response(self.delete_status)
        return httpx.Response(405)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))


def creds() -> Credentials:
    return Credentials(token="access-123")


class TestCalendarClient:
    def test_create_event_request(self):
        fake = FakeCalendar()
        event_id = google_calendar.create_event(
            creds(),
            summary="Kasa: Ayşe -> Ali 150.00 TRY",
            description="pay up",
            day=dt.date(2026, 10, 20),
            attendee_emails=["ayse@example.com", "", "ayse@example.com", "ali@example.com"],
            http=fake.client(),
        )
        assert event_id == "evt1"
        request = fake.calls[0]
        assert request.url.path == "/calendar/v3/calendars/primary/events"
        assert request.url.params["sendUpdates"] == "all"
        assert request.headers["Authorization"] == "Bearer access-123"
        body = json.loads(request.content)
        assert body["start"] == {"date": "2026-10-20"} and body["end"] == {"date": "2026-10-21"}
        assert body["attendees"] == [{"email": "ayse@example.com"}, {"email": "ali@example.com"}]
        assert body["reminders"]["overrides"][0]["method"] == "popup"
        assert body["summary"].startswith("Kasa:")

    def test_no_attendees_sends_no_updates(self):
        fake = FakeCalendar()
        google_calendar.create_event(creds(), summary="s", description="d", day=DUE, http=fake.client())
        assert fake.calls[0].url.params["sendUpdates"] == "none"

    def test_api_error_becomes_upstream_error(self):
        fake = FakeCalendar(fail_create=True)
        with pytest.raises(UpstreamError, match="403: Insufficient Permission"):
            google_calendar.create_event(creds(), summary="s", description="d", day=DUE, http=fake.client())

    def test_network_error_becomes_upstream_error(self):
        def boom(request):
            raise httpx.ConnectError("no route", request=request)

        client = httpx.Client(transport=httpx.MockTransport(boom))
        with pytest.raises(UpstreamError, match="request failed"):
            google_calendar.create_event(creds(), summary="s", description="d", day=DUE, http=client)

    @pytest.mark.parametrize("status", [204, 200, 404, 410])
    def test_delete_event_ok_and_already_gone(self, status):
        fake = FakeCalendar(delete_status=status)
        google_calendar.delete_event(creds(), "evt/1", http=fake.client())
        assert fake.calls[0].method == "DELETE"
        assert fake.calls[0].url.raw_path.startswith(b"/calendar/v3/calendars/primary/events/evt%2F1")

    def test_delete_event_error(self):
        fake = FakeCalendar(delete_status=500)
        with pytest.raises(UpstreamError):
            google_calendar.delete_event(creds(), "evt1", http=fake.client())

    def test_expired_token_refresh_failure(self):
        expired = Credentials(token=None, refresh_token="r", token_uri="https://oauth2.invalid/token")

        def fail_refresh(_request):
            raise RuntimeError("refresh denied")

        expired.refresh = fail_refresh
        with pytest.raises(UpstreamError, match="refresh"):
            google_calendar.create_event(
                expired, summary="s", description="d", day=DUE, http=FakeCalendar().client()
            )


@pytest.fixture
def calendar(monkeypatch):
    fake = FakeCalendar()
    monkeypatch.setattr(google_calendar, "_new_client", fake.client)
    return fake


@pytest.fixture
def connected(monkeypatch):
    """The caller has connected Google (credentials_for_user belongs to track INGEST)."""
    monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: creds())


def make_debts(db, prefix: str) -> tuple[int, str, str, str]:
    """me paid 300 for three; ali and ayse each owe me 100."""
    me, ali, ayse = f"{prefix}-me", f"{prefix}-ali", f"{prefix}-ayse"
    house = houses.create_house(db, me, f"{prefix} flat")
    houses.add_member(db, me, house.id, ali, "Ali")
    houses.add_member(db, me, house.id, ayse, "Ayşe")
    db.get(User, ayse).email = f"{prefix}-ayse@example.com"
    db.get(User, me).email = f"{prefix}-me@example.com"
    db.commit()
    houses.add_split_expense(db, me, house.id, ExpenseInput("Kira", "300"), split_type="equal")
    return house.id, me, ali, ayse


class TestReminders:
    def test_not_connected_saves_in_kasa_only(self, db, calendar, monkeypatch):
        monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: None)
        house_id, me, ali, ayse = make_debts(db, "rn")
        result = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert result.calendar_connected is False
        assert reminders.NOT_CONNECTED in result.warnings
        assert sorted((r.from_user, r.to_user, r.amount_minor) for r in result.reminders) == [
            (ali, me, 10000),
            (ayse, me, 10000),
        ]
        assert all(r.calendar_event_id is None and r.status == "scheduled" for r in result.reminders)
        assert calendar.calls == []

    def test_stub_not_implemented_counts_as_not_connected(self, db, calendar, monkeypatch):
        def stub(_db, _uid):
            raise NotImplementedError("credentials_for_user: track INGEST")

        monkeypatch.setattr(google_oauth, "credentials_for_user", stub)
        house_id, me, *_ = make_debts(db, "rs")
        result = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert len(result.reminders) == 2 and result.calendar_connected is False

    def test_connected_creates_events_with_known_emails(self, db, calendar, connected):
        house_id, me, _ali, _ayse = make_debts(db, "rc")
        result = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert result.calendar_connected is True and result.warnings == []
        assert {r.calendar_event_id for r in result.reminders} == {"evt1", "evt2"}
        bodies = [json.loads(c.content) for c in calendar.calls]
        attendees = sorted(tuple(a["email"] for a in b["attendees"]) for b in bodies)
        # ali has no email; the caller's own address is never added as an attendee
        assert attendees == [(), ("rc-ayse@example.com",)]
        assert all(b["start"] == {"date": DUE.isoformat()} for b in bodies)
        assert any("Ayşe" in b["summary"] and "100.00 TRY" in b["summary"] for b in bodies)

    def test_rerun_does_not_duplicate(self, db, calendar, connected):
        house_id, me, *_ = make_debts(db, "rr")
        first = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        again = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert [r.id for r in again.reminders] == [r.id for r in first.reminders]
        assert len(calendar.calls) == 2
        assert len(reminders.list_reminders(db, me, house_id)) == 2

    def test_calendar_failure_keeps_the_reminder(self, db, monkeypatch, connected):
        fake = FakeCalendar(fail_create=True)
        monkeypatch.setattr(google_calendar, "_new_client", fake.client)
        house_id, me, *_ = make_debts(db, "rf")
        result = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert len(result.reminders) == 2
        assert all(r.calendar_event_id is None for r in result.reminders)
        assert len(result.warnings) == 2 and "failed" in result.warnings[0]
        assert len(reminders.list_reminders(db, me, house_id)) == 2

    def test_nothing_to_settle(self, db, calendar, connected):
        house = houses.create_house(db, "r0-me", "Empty flat")
        result = reminders.create_settle_up_reminders(db, "r0-me", house.id, due_date=DUE)
        assert result.reminders == [] and result.warnings == ["everyone is settled up"]

    def test_validation_and_access(self, db, calendar, connected):
        house_id, me, *_ = make_debts(db, "rv")
        with pytest.raises(InvalidInput, match="past"):
            reminders.create_settle_up_reminders(
                db, me, house_id, due_date=clock.today() - dt.timedelta(days=1)
            )
        with pytest.raises(NotFound):
            reminders.create_settle_up_reminders(db, "rv-outsider", house_id, due_date=DUE)
        with pytest.raises(NotFound):
            reminders.list_reminders(db, "rv-outsider", house_id)
        with pytest.raises(InvalidInput):
            reminders.list_reminders(db, me, house_id, status="bogus")

    def test_status_changes_and_cancel_deletes_the_event(self, db, calendar, connected):
        house_id, me, ali, _ayse = make_debts(db, "rx")
        rows = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE).reminders
        first, second = rows
        # Any member can mark done and undo it; nothing is sent to Google for that.
        assert reminders.set_reminder_status(db, ali, first.id, "done").status == "done"
        assert reminders.set_reminder_status(db, ali, first.id, "scheduled").status == "scheduled"
        assert [r.id for r in reminders.list_reminders(db, me, house_id, status="scheduled")] == [
            first.id,
            second.id,
        ]
        # Only the creator cancels; that deletes the calendar event.
        with pytest.raises(Forbidden):
            reminders.set_reminder_status(db, ali, second.id, "cancelled")
        event_id = second.calendar_event_id
        row = reminders.set_reminder_status(db, me, second.id, "cancelled")
        assert row.status == "cancelled" and row.calendar_event_id is None
        assert calendar.calls[-1].method == "DELETE" and calendar.calls[-1].url.path.endswith(event_id)
        with pytest.raises(InvalidInput, match="cancelled"):
            reminders.set_reminder_status(db, me, second.id, "scheduled")
        with pytest.raises(NotFound):
            reminders.set_reminder_status(db, "rx-outsider", first.id, "done")
        with pytest.raises(NotFound):
            reminders.set_reminder_status(db, me, first.id, "done", house_id=house_id + 999)
        with pytest.raises(InvalidInput):
            reminders.set_reminder_status(db, me, first.id, "later")

    def test_cancel_with_calendar_error_changes_nothing(self, db, monkeypatch, connected):
        fake = FakeCalendar(delete_status=500)
        monkeypatch.setattr(google_calendar, "_new_client", fake.client)
        house_id, me, *_ = make_debts(db, "re")
        row = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE).reminders[0]
        with pytest.raises(UpstreamError):
            reminders.set_reminder_status(db, me, row.id, "cancelled")
        db.refresh(row)
        assert row.status == "scheduled" and row.calendar_event_id is not None


class TestReminderApi:
    def test_create_list_update(self, client, calendar, monkeypatch):
        monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: None)
        h = {"X-User-Id": "ra-me"}
        house_id = client.post("/houses", json={"name": "Api flat"}, headers=h).json()["id"]
        client.post(f"/houses/{house_id}/members", json={"user_id": "ra-ali"}, headers=h)
        client.post(f"/houses/{house_id}/expenses", json={"merchant": "Kira", "total": "50"}, headers=h)

        r = client.post(f"/houses/{house_id}/reminders", json={"due_date": DUE.isoformat()}, headers=h)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["calendar_connected"] is False and body["warnings"] == [reminders.NOT_CONNECTED]
        [reminder] = body["reminders"]
        assert (reminder["from_user"], reminder["to_user"], reminder["amount"]) == (
            "ra-ali",
            "ra-me",
            "25.00",
        )

        listed = client.get(f"/houses/{house_id}/reminders", headers={"X-User-Id": "ra-ali"}).json()
        assert [x["id"] for x in listed] == [reminder["id"]]
        url = f"/houses/{house_id}/reminders/{reminder['id']}"
        r = client.patch(url, json={"status": "done"}, headers={"X-User-Id": "ra-ali"})
        assert r.status_code == 200 and r.json()["status"] == "done"
        assert client.get(f"/houses/{house_id}/reminders?status=scheduled", headers=h).json() == []
        assert (
            client.patch(url, json={"status": "cancelled"}, headers={"X-User-Id": "ra-ali"}).status_code
            == 403
        )
        assert client.patch(url, json={"status": "nope"}, headers=h).status_code == 422
        assert (
            client.patch(url, json={"status": "cancelled"}, headers={"X-User-Id": "ra-out"}).status_code
            == 404
        )
        past = (clock.today() - dt.timedelta(days=2)).isoformat()
        assert (
            client.post(f"/houses/{house_id}/reminders", json={"due_date": past}, headers=h).status_code
            == 422
        )


def keys(rows) -> list[tuple[str, str, int]]:
    return sorted((r.from_user, r.to_user, r.amount_minor) for r in rows)


class TestOutdatedReminders:
    """Creating reminders again cancels the scheduled ones the balances no longer support."""

    def test_changed_amount_replaces_the_reminder_and_deletes_its_event(self, db, calendar, connected):
        house_id, me, ali, ayse = make_debts(db, "ro")
        first = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        old_ali = next(r for r in first.reminders if r.from_user == ali)
        old_event = old_ali.calendar_event_id
        houses.record_settlement(db, me, house_id, from_user=ali, to_user=me, amount="40")

        assert reminders.outdated_reminder_ids(
            db, me, house_id, reminders.list_reminders(db, me, house_id)
        ) == {old_ali.id}
        again = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert keys(again.reminders) == [(ali, me, 6000), (ayse, me, 10000)]
        assert [r.id for r in again.cancelled] == [old_ali.id] and again.warnings == []
        db.refresh(old_ali)
        assert old_ali.status == "cancelled" and old_ali.cancel_reason == "outdated"
        assert old_ali.calendar_event_id is None
        deletes = [c for c in calendar.calls if c.method == "DELETE"]
        assert len(deletes) == 1 and deletes[0].url.path.endswith(f"/events/{old_event}")
        # Ayşe's reminder still matches and is kept; one new event for Ali's new amount.
        assert len([c for c in calendar.calls if c.method == "POST"]) == 3
        rows = reminders.list_reminders(db, me, house_id)
        assert reminders.outdated_reminder_ids(db, me, house_id, rows) == set()
        assert keys(r for r in rows if r.status == "scheduled") == [(ali, me, 6000), (ayse, me, 10000)]

    def test_calendar_error_keeps_the_old_reminder_with_a_warning(self, db, monkeypatch, connected):
        fake = FakeCalendar(delete_status=500)
        monkeypatch.setattr(google_calendar, "_new_client", fake.client)
        house_id, me, ali, _ayse = make_debts(db, "rw")
        first = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        old_ali = next(r for r in first.reminders if r.from_user == ali)
        houses.record_settlement(db, me, house_id, from_user=ali, to_user=me, amount="40")

        again = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert again.cancelled == []
        assert len(again.warnings) == 1 and "stays scheduled" in again.warnings[0]
        db.refresh(old_ali)
        assert old_ali.status == "scheduled" and old_ali.calendar_event_id is not None
        assert (ali, me, 6000) in keys(again.reminders)  # the new amount is still reminded

    def test_someone_elses_event_stays_and_is_named(self, db, calendar, connected):
        house_id, me, ali, ayse = make_debts(db, "rx2")
        first = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        old_ayse = next(r for r in first.reminders if r.from_user == ayse)
        houses.record_settlement(db, ali, house_id, from_user=ayse, to_user=me, amount="100")

        again = reminders.create_settle_up_reminders(db, ali, house_id, due_date=DUE)
        assert [r.id for r in again.cancelled] == [old_ayse.id]
        assert any(me in w and "Google Calendar" in w for w in again.warnings)
        assert not [c for c in calendar.calls if c.method == "DELETE"]
        db.refresh(old_ayse)
        assert old_ayse.status == "cancelled" and old_ayse.cancel_reason == "outdated"

    def test_settled_house_cancels_everything_scheduled(self, db, calendar, monkeypatch):
        monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: None)
        house_id, me, ali, ayse = make_debts(db, "rz")
        reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        houses.record_settlement(db, me, house_id, from_user=ali, to_user=me, amount="100")
        houses.record_settlement(db, me, house_id, from_user=ayse, to_user=me, amount="100")
        result = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE)
        assert result.reminders == [] and len(result.cancelled) == 2
        assert result.warnings == ["everyone is settled up"]
        assert reminders.list_reminders(db, me, house_id, status="scheduled") == []

    def test_manual_cancel_says_user(self, db, calendar, connected):
        house_id, me, *_ = make_debts(db, "rm2")
        row = reminders.create_settle_up_reminders(db, me, house_id, due_date=DUE).reminders[0]
        assert reminders.set_reminder_status(db, me, row.id, "cancelled").cancel_reason == "user"

    def test_api_shows_outdated_then_updated(self, client, calendar, monkeypatch):
        monkeypatch.setattr(google_oauth, "credentials_for_user", lambda _db, _uid: None)
        h = {"X-User-Id": "rapi-me"}
        house_id = client.post("/houses", json={"name": "Api flat"}, headers=h).json()["id"]
        client.post(f"/houses/{house_id}/members", json={"user_id": "rapi-ali"}, headers=h)
        client.post(f"/houses/{house_id}/expenses", json={"merchant": "Kira", "total": "50"}, headers=h)
        url = f"/houses/{house_id}/reminders"
        [old] = client.post(url, json={"due_date": DUE.isoformat()}, headers=h).json()["reminders"]
        assert old["outdated"] is False and old["cancel_reason"] is None

        client.post(f"/houses/{house_id}/expenses", json={"merchant": "Su", "total": "10"}, headers=h)
        [listed] = client.get(url, headers=h).json()
        assert listed["id"] == old["id"] and listed["outdated"] is True

        body = client.post(url, json={"due_date": DUE.isoformat()}, headers=h).json()
        assert [c["id"] for c in body["cancelled"]] == [old["id"]]
        assert body["cancelled"][0]["cancel_reason"] == "outdated"
        assert [r["amount"] for r in body["reminders"]] == ["30.00"]
        by_id = {r["id"]: r for r in client.get(url, headers=h).json()}
        assert by_id[old["id"]]["status"] == "cancelled" and by_id[old["id"]]["cancel_reason"] == "outdated"
        assert by_id[old["id"]]["outdated"] is False
        assert all(not r["outdated"] for r in by_id.values())
