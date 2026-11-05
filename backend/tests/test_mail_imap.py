"""Purchase emails without Google Cloud (track INGEST): an IMAP mailbox with an app password
and uploaded .eml files. IMAP is faked in memory; the email parser runs through the real ADK
runner with the scripted model from the Gmail tests."""

from __future__ import annotations

import asyncio
import imaplib
import socket
from email.message import EmailMessage
from types import SimpleNamespace

import pytest

from app.agents import common, runtime
from app.agents.tools import inbox_tools
from app.config import get_settings
from app.db.models import MailAccount
from app.db.session import init_db, session_for
from app.integrations import imap_mail
from app.services import crypto, inbox, mail_sync
from app.services.errors import InvalidInput
from tests.fixtures.ingest_fakes import ParserLlm
from tests.fixtures.make_gmail_messages import NEWSLETTER_TEXT, TRENDYOL_TEXT

APP_PASSWORD = "abcd efgh ijkl mnop"  # how Gmail shows it: four groups


def eml(subject: str, body: str, *, message_id: str | None = None, html: bool = False) -> bytes:
    msg = EmailMessage()
    msg["From"] = "Trendyol <siparis@trendyol.com>"
    msg["To"] = "ayse.ogrenci@gmail.com"
    msg["Subject"] = subject
    msg["Date"] = "Tue, 03 Nov 2026 14:05:00 +0300"
    if message_id:
        msg["Message-ID"] = f"<{message_id}>"
    if html:
        msg.set_content("HTML only")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)
    return bytes(msg)


ORDER = eml("Siparişiniz alındı", TRENDYOL_TEXT, message_id="order-1@trendyol.com")
NEWSLETTER = eml("Haftanın kampanyaları", NEWSLETTER_TEXT, message_id="news-1@shop.com")
PROMO = eml("Hello from the team", "Nothing to see", message_id="hello-1@shop.com")


class FakeMailbox:
    """One IMAP server in memory. `gmail` adds Gmail's X-GM-EXT-1 search extension."""

    def __init__(self) -> None:
        self.messages: dict[int, bytes] = {}
        self.uid_validity = b"777"
        self.gmail = False
        self.searches: list[tuple] = []
        self.fetched: list[int] = []
        self.logins = 0

    def add(self, raw: bytes) -> int:
        uid = max(self.messages, default=0) + 1
        self.messages[uid] = raw
        return uid

    def client(self, host, port, ssl_context=None, timeout=None):
        return FakeImap(self, host, port)


class FakeImap:
    def __init__(self, box: FakeMailbox, host: str, port: int) -> None:
        assert port == 993  # IMAP over SSL only
        self.box, self.literal = box, None

    def login(self, user, password):
        if password != APP_PASSWORD.replace(" ", ""):
            raise imaplib.IMAP4.error("[AUTHENTICATIONFAILED] Invalid credentials")
        self.box.logins += 1
        return "OK", [b"logged in"]

    def select(self, folder, readonly=False):
        assert readonly, "the mailbox must be opened read-only"
        return ("OK", [b"3"]) if folder == '"INBOX"' else ("NO", [b"no such folder"])

    def response(self, code):
        return code, [self.box.uid_validity]

    def capability(self):
        return "OK", [b"IMAP4rev1 X-GM-EXT-1" if self.box.gmail else b"IMAP4rev1"]

    def uid(self, command, *args):
        if command == "SEARCH":
            self.box.searches.append((*args, self.literal))
            return "OK", [" ".join(str(u) for u in sorted(self.box.messages)).encode()]
        assert command == "FETCH" and "BODY.PEEK[]" in args[1], "fetch must not mark mail as read"
        uid = int(args[0])
        self.box.fetched.append(uid)
        return "OK", [(f"{uid} (UID {uid} BODY[]".encode(), self.box.messages[uid]), b")"]

    def logout(self):
        return "BYE", []


@pytest.fixture(autouse=True)
def _schema():
    init_db()


@pytest.fixture
def mailbox(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "token_encryption_key", crypto.generate_key())
    monkeypatch.setattr(settings, "mail_allow_private_hosts", True)  # no DNS in tests
    box = FakeMailbox()
    monkeypatch.setattr(imap_mail.imaplib, "IMAP4_SSL", box.client)
    return box


@pytest.fixture
def parser(monkeypatch):
    monkeypatch.setattr(common, "build_model", lambda name, vision=False: ParserLlm(model="parser"))
    monkeypatch.setattr(get_settings(), "llm_provider", "gemini")
    monkeypatch.setattr(get_settings(), "google_api_key", "test-key")
    ParserLlm.calls = 0
    ParserLlm.obey_injection = False
    runtime._runner.cache_clear()
    yield ParserLlm
    runtime._runner.cache_clear()


def items(user: str) -> dict[str, inbox.InboxItem]:
    with session_for(user) as db:
        return {i.external_ref: i for i in inbox.list_items(db, user, status="all")}


def as_user(user: str) -> dict[str, str]:
    return {"X-User-Id": user}


# --- parsing ---------------------------------------------------------------------------------


def test_parse_message_reads_text_html_and_message_id():
    msg = imap_mail.parse_message(ORDER)
    assert msg.id == "mid:order-1@trendyol.com"
    assert msg.subject == "Siparişiniz alındı" and "Trendyol" in msg.sender
    assert "7381049256" in msg.body_text
    assert msg.received_at.isoformat() == "2026-11-03T11:05:00+00:00"

    rich = imap_mail.parse_message(
        eml("Fatura", "<p>Toplam <b>149,90 TL</b></p><script>steal()</script>", html=True)
    )
    assert rich.id.startswith("sha:")  # no Message-ID: a hash of the bytes
    assert rich.body_text == "HTML only"  # the plain part wins when there is one


def test_purchase_subjects():
    assert imap_mail.looks_like_purchase("Siparişiniz kargoya verildi")
    assert imap_mail.looks_like_purchase("Your ORDER #123")
    assert not imap_mail.looks_like_purchase("Haftanın kampanyaları")
    assert imap_mail.imap_date(__import__("datetime").date(2026, 11, 5)) == "05-Nov-2026"


@pytest.mark.parametrize(
    ("host", "port", "reason"),
    [
        ("imap.gmail.com", 143, "port 993"),
        ("localhost", 993, "public internet"),
        ("10.0.0.5", 993, "public internet"),
        ("169.254.169.254", 993, "public internet"),
        ("imap gmail com", 993, "host name"),
    ],
)
def test_check_server_refuses_unsafe_targets(host, port, reason):
    with pytest.raises(InvalidInput, match=reason):
        imap_mail.check_server(host, port)


def test_check_server_allows_a_public_host(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("142.250.102.108", 993))])
    imap_mail.check_server("imap.gmail.com", 993)


# --- connecting ------------------------------------------------------------------------------


def test_connect_checks_the_password_and_stores_it_encrypted(client, mailbox):
    user = "mail-connect"
    bad = client.post(
        "/integrations/mail",
        json={"address": "ayse.ogrenci@gmail.com", "password": "wrong"},
        headers=as_user(user),
    )
    assert bad.status_code == 422 and "app password" in bad.json()["detail"]

    r = client.post(
        "/integrations/mail",
        json={"address": "ayse.ogrenci@gmail.com", "password": APP_PASSWORD},
        headers=as_user(user),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["connected"] and body["host"] == "imap.gmail.com" and body["folder"] == "INBOX"
    with session_for(user) as db:
        account = db.get(MailAccount, user)
        assert APP_PASSWORD.replace(" ", "") not in account.password_enc
        assert crypto.decrypt(account.password_enc) == APP_PASSWORD.replace(" ", "")

    assert client.get("/integrations/mail", headers=as_user("someone-else")).json()["connected"] is False
    assert client.delete("/integrations/mail", headers=as_user(user)).status_code == 204
    assert client.get("/integrations/mail", headers=as_user(user)).json()["connected"] is False


def test_unknown_provider_needs_a_server(client, mailbox):
    r = client.post(
        "/integrations/mail",
        json={"address": "ayse@okul.edu.tr", "password": APP_PASSWORD},
        headers=as_user("mail-unknown"),
    )
    assert r.status_code == 422 and "IMAP server" in r.json()["detail"]


# --- syncing ---------------------------------------------------------------------------------


def connect(user: str) -> None:
    with session_for(user) as db:
        mail_sync.connect(
            db, user, username="ayse.ogrenci@okul.edu.tr", password=APP_PASSWORD, host="imap.okul.edu.tr"
        )


def test_sync_parses_purchase_mail_and_starts_after_the_last_uid(mailbox, parser):
    user = "mail-sync"
    connect(user)
    mailbox.add(ORDER)
    mailbox.add(PROMO)  # no purchase word in the subject: never reaches the model
    mailbox.add(eml("Kampanya siparişi değil", NEWSLETTER_TEXT, message_id="news-2@shop.com"))

    result = asyncio.run(mail_sync.sync_user(user))
    assert (result.fetched, result.created, result.ignored, result.error) == (2, 1, 1, None)
    assert parser.calls == 2
    found = items(user)
    order = found["mid:order-1@trendyol.com"]
    assert order.status == "pending" and order.source == "email"
    assert inbox.parsed_of(order).total == "829.80"  # TRENDYOL_ARGS in the scripted parser
    assert found["mid:news-2@shop.com"].status == "ignored"

    # Next sync: only mail after the last UID is fetched.
    mailbox.fetched.clear()
    new_uid = mailbox.add(eml("Fatura: Getir siparişi", "GTR-55120 toplam", message_id="getir-1@getir.com"))
    result = asyncio.run(mail_sync.sync_user(user))
    assert mailbox.fetched == [new_uid] and result.created == 1
    with session_for(user) as db:
        account = db.get(MailAccount, user)
        assert account.last_uid == new_uid and account.uid_validity == "777" and account.last_error is None


def test_gmail_over_imap_uses_the_gmail_query(mailbox, parser, monkeypatch):
    user = "mail-gmail"
    mailbox.gmail = True
    with session_for(user) as db:
        mail_sync.connect(db, user, username="ayse.ogrenci@gmail.com", password=APP_PASSWORD)
    mailbox.add(PROMO)  # Gmail's search did the filtering, so the subject check is skipped
    asyncio.run(mail_sync.sync_user(user))
    args = mailbox.searches[-1]
    assert args[:3] == ("CHARSET", "UTF-8", "X-GM-RAW")
    assert args[3] == get_settings().gmail_query.encode("utf-8")
    assert parser.calls == 1


def test_a_renumbered_folder_falls_back_to_message_ids(mailbox, parser):
    user = "mail-validity"
    connect(user)
    mailbox.add(ORDER)
    asyncio.run(mail_sync.sync_user(user))
    mailbox.uid_validity = b"778"  # the server rebuilt the folder; UIDs mean nothing now
    result = asyncio.run(mail_sync.sync_user(user))
    assert result.duplicates == 1 and result.created == 0
    assert len(items(user)) == 1


def test_sync_without_a_mailbox_or_model(mailbox, parser, monkeypatch):
    assert asyncio.run(mail_sync.sync_user("mail-none")).error == "no mailbox is connected"
    monkeypatch.setattr(get_settings(), "google_api_key", "")
    connect("mail-nomodel")
    assert "GOOGLE_API_KEY" in asyncio.run(mail_sync.sync_user("mail-nomodel")).error


# --- .eml upload -----------------------------------------------------------------------------


def test_upload_eml_creates_a_pending_item_once(client, parser):
    user = "mail-upload"
    files = {"file": ("trendyol.eml", ORDER, "message/rfc822")}
    r = client.post("/imports/email", files=files, headers=as_user(user))
    assert r.status_code == 201, r.text
    assert r.json()["created"] == 1
    again = client.post("/imports/email", files=files, headers=as_user(user))
    assert again.json()["duplicates"] == 1 and again.json()["created"] == 0
    assert list(items(user)) == ["mid:order-1@trendyol.com"]


def test_upload_rejects_other_files_and_needs_a_model(client, parser, monkeypatch):
    r = client.post(
        "/imports/email", files={"file": ("a.txt", b"hello", "text/plain")}, headers=as_user("mail-415")
    )
    assert r.status_code == 415
    monkeypatch.setattr(get_settings(), "google_api_key", "")
    r = client.post(
        "/imports/email", files={"file": ("a.eml", ORDER, "message/rfc822")}, headers=as_user("mail-503")
    )
    assert r.status_code == 503


# --- the inbox agent's tool ------------------------------------------------------------------


def test_check_email_tool(mailbox, parser):
    context = SimpleNamespace(user_id="mail-tool")
    assert asyncio.run(inbox_tools.check_email(context))["status"] == "not_connected"
    connect("mail-tool")
    mailbox.add(ORDER)
    result = asyncio.run(inbox_tools.check_email(context))
    assert result["status"] == "ok" and result["new_items_to_review"] == 1 and result["pending_items"] == 1


# --- the check when the app opens ------------------------------------------------------------


def test_auto_sync_runs_only_when_due(client, mailbox, parser, monkeypatch):
    user = "mail-auto"
    assert client.post("/integrations/mail/auto-sync", headers=as_user(user)).json() == {
        "ran": False,
        "result": None,
    }
    connect(user)
    mailbox.add(ORDER)
    first = client.post("/integrations/mail/auto-sync", headers=as_user(user)).json()
    assert first["ran"] and first["result"]["created"] == 1

    mailbox.add(eml("Fatura: Getir siparişi", "GTR-55120 toplam", message_id="getir-2@getir.com"))
    again = client.post("/integrations/mail/auto-sync", headers=as_user(user)).json()
    assert again == {"ran": False, "result": None}  # checked a moment ago

    monkeypatch.setattr(get_settings(), "mail_auto_sync_minutes", 0)
    later = client.post("/integrations/mail/auto-sync", headers=as_user(user)).json()
    assert later["ran"] and later["result"]["created"] == 1
