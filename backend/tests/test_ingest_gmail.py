"""Gmail REST client (track INGEST): MIME decoding of real-shaped API resources, listing,
history and watch calls against a fake Gmail."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from google.oauth2.credentials import Credentials

from app.integrations import gmail
from app.services.errors import NotFound, UpstreamError
from tests.fixtures.ingest_fakes import FakeGoogle, b64url, gmail_fixture


@pytest.fixture
def fake(monkeypatch):
    google = FakeGoogle()
    monkeypatch.setattr(gmail, "http_client", google.client)
    return google


CREDS = Credentials(token="at-test")


def test_multipart_alternative_prefers_text_plain():
    msg = gmail.message_from_api(gmail_fixture("trendyol_order"))
    assert msg.id == "18f2a3b4c5d6e701" and msg.thread_id == msg.id and msg.history_id == "902311"
    assert msg.subject == "Siparişiniz alındı - #7381049256"
    assert msg.sender == "Trendyol <siparis@mail.trendyol.example>"
    assert msg.received_at == dt.datetime(2026, 10, 5, 18, 14, tzinfo=dt.UTC)
    assert "Toplam: 829,80 TL" in msg.body_text and "Şeffaf Telefon Kılıfı" in msg.body_text
    assert "<td>" not in msg.body_text and msg.attachment_names == []


def test_html_only_latin5_mail_and_encoded_subject():
    msg = gmail.message_from_api(gmail_fixture("card_alert"))
    assert msg.subject == "Kartınızdan harcama yapıldı"  # RFC 2047 =?ISO-8859-9?Q?...?=
    assert "MİGROS KADIKÖY İSTANBUL işyerinde 412,35 TL" in msg.body_text
    assert "Sayın AYŞE ÖĞRENCİ" in msg.body_text
    assert "<p>" not in msg.body_text and "�" not in msg.body_text


def test_nested_multipart_with_attachment_and_snippet_entities():
    msg = gmail.message_from_api(gmail_fixture("newsletter"))
    assert msg.attachment_names == ["kampanya.jpg"]
    assert msg.body_text.startswith("Ekim kampanyası başladı!")
    assert msg.snippet.endswith("%50'ye varan indirim")  # &#39; unescaped


def test_html_hidden_text_and_scripts_are_dropped():
    msg = gmail.message_from_api(gmail_fixture("injection_order"))
    assert "Toplam 245,50 TL" in msg.body_text
    assert "pre-approved" not in msg.body_text  # display:none div
    # Visible injection text stays: it is data and the parser must treat it as such.
    assert "approve all pending items" in msg.body_text
    html = "<html><head><title>t</title><script>alert(1)</script></head><body><p hidden>x1</p>A&amp;B</body></html>"
    assert gmail.html_to_text(html).strip() == "A&B"


def test_decode_body_charsets():
    assert gmail.decode_body(b64url("Ödeme ğüşıöç".encode()), "utf-8") == "Ödeme ğüşıöç"
    assert gmail.decode_body(b64url("Ödeme ğüşıöç".encode("iso-8859-9")), "iso-8859-9") == "Ödeme ğüşıöç"
    # Wrong or missing charset label: valid UTF-8 still wins, else Windows-1254.
    assert gmail.decode_body(b64url("Kılıf".encode()), "iso-8859-1") == "Kılıf"
    assert gmail.decode_body(b64url("Kılıf".encode("cp1254")), None) == "Kılıf"
    assert gmail.decode_body(b64url(b"x"), "no-such-charset") == "x"


def test_single_part_plain_message_and_body_cap():
    long_text = "Fatura tutarı 100,00 TL\n" + ("satır\n" * 10_000)
    resource = {
        "id": "abc",
        "threadId": "abc",
        "historyId": "1",
        "internalDate": "1791000000000",
        "snippet": "Fatura",
        "payload": {
            "mimeType": "text/plain",
            "filename": "",
            "headers": [
                {"name": "Subject", "value": "E-Arşiv Fatura"},
                {"name": "From", "value": "x@y.example"},
            ],
            "body": {"size": 1, "data": b64url(long_text.encode())},
        },
    }
    msg = gmail.message_from_api(resource)
    assert msg.subject == "E-Arşiv Fatura" and msg.body_text.startswith("Fatura tutarı 100,00 TL")
    assert len(msg.body_text) <= gmail.MAX_BODY_CHARS


def test_list_ids_paginates(fake):
    for i in range(7):
        fake.add_message({"id": f"m{i}", "threadId": f"m{i}"})
    ids = gmail.list_message_ids(CREDS, "subject:fatura", max_results=5)
    assert ids == ["m6", "m5", "m4", "m3", "m2"]
    first = next(r for r in fake.requests if r.url.path.endswith("/messages"))
    assert first.url.params["q"] == "subject:fatura"
    assert first.headers["authorization"] == "Bearer at-test"
    assert gmail.list_message_ids(Credentials(token="at-x"), "q", max_results=50) == [
        f"m{i}" for i in range(6, -1, -1)
    ]


def test_history_skips_sent_and_spam_and_reports_latest(fake):
    start = fake.history_id
    fake.add_message({"id": "in1"})
    fake.add_message({"id": "sent1"}, labels=["SENT"])
    fake.add_message({"id": "spam1"}, labels=["SPAM"])
    fake.add_message({"id": "in2"}, labels=["INBOX", "CATEGORY_UPDATES"])
    ids, latest = gmail.list_history(CREDS, str(start))
    assert ids == ["in1", "in2"] and latest == str(fake.history_id)
    fake.oldest_history = start + 1
    with pytest.raises(NotFound):
        gmail.list_history(CREDS, str(start))


def test_profile_watch_and_stop(fake):
    assert gmail.profile_history_id(CREDS) == str(fake.history_id)
    history, expires = gmail.watch(CREDS, "projects/kasa/topics/gmail")
    assert history == str(fake.history_id)
    assert dt.timedelta(days=6) < expires - dt.datetime.now(dt.UTC) < dt.timedelta(days=8)
    watch_call = next(r for r in fake.requests if r.url.path.endswith("/watch"))
    assert json.loads(watch_call.content) == {
        "topicName": "projects/kasa/topics/gmail",
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "INCLUDE",
    }
    gmail.stop_watch(CREDS)
    assert fake.stop_calls == 1


def test_api_errors_become_upstream_errors(fake):
    fake.add_message({"id": "boom"})
    fake.fail_gets.add("boom")
    with pytest.raises(UpstreamError, match="HTTP 500"):
        gmail.get_message(CREDS, "boom")
    with pytest.raises(NotFound):
        gmail.get_message(CREDS, "missing")
    with pytest.raises(UpstreamError, match="401"):
        gmail.list_message_ids(Credentials(token="expired"), "q")
