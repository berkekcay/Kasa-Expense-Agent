"""IMAP client for purchase emails without a Google Cloud OAuth client (owner: track INGEST).

Gmail, Outlook.com, Yandex and most school or work mailboxes speak IMAP. With two-step
verification on, Gmail gives an "app password" for exactly this, so a student can connect a
mailbox with nothing but that password. Standard library only (imaplib, email).

Read-only: the folder is opened with EXAMINE and bodies are fetched with BODY.PEEK, so
nothing is marked as read, moved or deleted. Email content is untrusted DATA, exactly as in
`integrations.gmail`: it goes to the email-parse agent fenced as text and is never rendered
as HTML or logged.

The server address comes from the user, so before connecting we refuse anything that is not
IMAPS (port 993) on a public address: no loopback, private, link-local or reserved targets.
"""

from __future__ import annotations

import datetime as dt
import email
import email.policy
import hashlib
import imaplib
import ipaddress
import re
import socket
import ssl
from collections.abc import Iterable
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

from app.integrations.gmail import MAX_BODY_CHARS, GmailMessage, _decode_words, _one_line, _tidy, html_to_text
from app.services.errors import InvalidInput, UpstreamError

IMAPS_PORT = 993
TIMEOUT_SECONDS = 20
# A purchase email is small; a 2 MB prefix keeps every text part and skips big attachments.
MAX_FETCH_BYTES = 2_000_000
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
# Servers without Gmail's search extension: only subjects like these reach the parser.
PURCHASE_WORDS = (
    "sipariş", "siparis", "order", "fatura", "invoice", "makbuz", "receipt", "dekont",
    "harcama", "kartınızdan", "kartinizdan", "e-arşiv", "e-arsiv", "ödeme", "odeme", "payment",
    "satın", "satin", "purchase", "bilet", "ticket", "abonelik", "subscription",
)  # fmt: skip


@dataclass
class MailLogin:
    host: str
    port: int
    username: str
    password: str
    folder: str = "INBOX"


@dataclass
class FetchResult:
    uid_validity: str
    newest_uid: int | None  # highest UID the search returned, to start after next time
    messages: list[GmailMessage] = field(default_factory=list)
    skipped: int = 0  # not purchase-like by subject (servers without Gmail search)


# --- address check ---------------------------------------------------------------------------


def check_server(host: str, port: int, *, allow_private: bool = False) -> None:
    """Refuse targets we should not connect to on the user's behalf."""
    host = (host or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", host) or ".." in host or host.startswith((".", "-")):
        raise InvalidInput("enter the mail server as a host name, e.g. imap.gmail.com")
    if port != IMAPS_PORT:
        raise InvalidInput("only IMAP over SSL (port 993) is supported")
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise InvalidInput(f"could not find the mail server {host}") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise InvalidInput("the mail server must be on the public internet")


# --- connecting and fetching ---------------------------------------------------------------


def _connect(login: MailLogin) -> imaplib.IMAP4_SSL:
    """Logged-in client. Turns protocol and network errors into domain errors."""
    try:
        client = imaplib.IMAP4_SSL(
            login.host, login.port, ssl_context=ssl.create_default_context(), timeout=TIMEOUT_SECONDS
        )
    except (OSError, imaplib.IMAP4.error) as exc:
        raise UpstreamError(f"could not reach the mail server ({type(exc).__name__})") from exc
    try:
        client.login(login.username, login.password)
    except imaplib.IMAP4.error as exc:
        _logout(client)
        raise InvalidInput(
            "the mail server refused the address or password; for Gmail use an app password"
        ) from exc
    except OSError as exc:
        _logout(client)
        raise UpstreamError(f"the mail server closed the connection ({type(exc).__name__})") from exc
    return client


def _logout(client: imaplib.IMAP4) -> None:
    try:
        client.logout()
    except (OSError, imaplib.IMAP4.error):
        pass


def _examine(client: imaplib.IMAP4, folder: str) -> str:
    """Open the folder read-only; returns its UIDVALIDITY."""
    typ, _ = client.select(_quote(folder), readonly=True)
    if typ != "OK":
        raise InvalidInput(f"the folder {folder!r} does not exist on this mail server")
    _, data = client.response("UIDVALIDITY")
    value = data[0] if data and data[0] else b""
    return value.decode() if isinstance(value, bytes) else str(value or "")


def check_login(login: MailLogin) -> None:
    """Log in and open the folder once, so a wrong password fails when connecting."""
    client = _connect(login)
    try:
        _examine(client, login.folder)
    finally:
        _logout(client)


def imap_date(day: dt.date) -> str:
    """RFC 3501 date (01-Nov-2026), independent of the machine's locale."""
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def _search(client: imaplib.IMAP4, since: dt.date, gmail_query: str) -> tuple[list[int], bool]:
    """Matching UIDs, oldest first, and whether Gmail's search did the filtering."""
    typ, caps = client.capability()
    gmail = bool(gmail_query) and typ == "OK" and b"X-GM-EXT-1" in b" ".join(c for c in caps if c)
    if gmail:
        # Gmail's own search syntax over IMAP: the same query the Gmail API sync uses.
        client.literal = gmail_query.encode("utf-8")
        typ, data = client.uid("SEARCH", "CHARSET", "UTF-8", "X-GM-RAW")
    else:
        typ, data = client.uid("SEARCH", "SINCE", imap_date(since))
    if typ != "OK":
        raise UpstreamError("the mail server could not search the folder")
    return sorted(int(uid) for uid in (data[0] or b"").split()), gmail


def fetch_new(
    login: MailLogin,
    *,
    uid_validity: str | None,
    after_uid: int | None,
    since: dt.date,
    limit: int,
    gmail_query: str = "",
) -> FetchResult:
    """The newest `limit` messages after `after_uid` (ignored when UIDVALIDITY changed)."""
    client = _connect(login)
    try:
        validity = _examine(client, login.folder)
        if uid_validity and validity != uid_validity:
            after_uid = None  # the server renumbered the folder; dedupe by Message-ID instead
        uids, filtered = _search(client, since, gmail_query)
        if after_uid is not None:
            uids = [uid for uid in uids if uid > after_uid]
        result = FetchResult(uid_validity=validity, newest_uid=uids[-1] if uids else after_uid)
        for uid in uids[-limit:]:
            typ, data = client.uid("FETCH", str(uid), f"(BODY.PEEK[]<0.{MAX_FETCH_BYTES}>)")
            raw = next((part[1] for part in data or [] if isinstance(part, tuple)), None)
            if typ != "OK" or not raw:
                continue
            message = parse_message(raw)
            if not filtered and not looks_like_purchase(message.subject):
                result.skipped += 1
                continue
            result.messages.append(message)
        return result
    except (OSError, imaplib.IMAP4.abort) as exc:
        raise UpstreamError(f"the mail server connection broke ({type(exc).__name__})") from exc
    finally:
        _logout(client)


def looks_like_purchase(subject: str) -> bool:
    lowered = subject.casefold()
    return any(word in lowered for word in PURCHASE_WORDS)


def _quote(folder: str) -> str:
    return '"' + folder.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- parsing ---------------------------------------------------------------------------------


def parse_message(raw: bytes) -> GmailMessage:
    """An RFC 822 message (IMAP fetch or an uploaded .eml file) as a GmailMessage, so the
    Gmail sync's parser prompt and inbox code work on it unchanged.

    The id is "mid:" plus the Message-ID header, so the same email arriving by IMAP and as an
    uploaded file lands in the inbox once. Without a Message-ID it is a hash of the bytes."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    assert isinstance(msg, EmailMessage)
    message_id = _one_line(str(msg.get("message-id") or "")).strip("<>")
    ref = f"mid:{message_id}" if message_id else "sha:" + hashlib.sha256(raw).hexdigest()[:40]
    plain, rich, attachments = _parts(msg.walk())
    body = next((t for t in plain if t.strip()), "") or next((html_to_text(t) for t in rich if t.strip()), "")
    body = _tidy(body)[:MAX_BODY_CHARS]
    return GmailMessage(
        id=ref[:200],
        thread_id="",
        history_id="",
        received_at=_received(msg),
        subject=_one_line(_decode_words(str(msg.get("subject") or ""))),
        sender=_one_line(_decode_words(str(msg.get("from") or ""))),
        snippet=_one_line(body[:200]),
        body_text=body,
        attachment_names=attachments,
    )


def _parts(parts: Iterable[EmailMessage]) -> tuple[list[str], list[str], list[str]]:
    plain: list[str] = []
    rich: list[str] = []
    attachments: list[str] = []
    for part in parts:
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename or part.get_content_disposition() == "attachment":
            if filename:
                attachments.append(_one_line(filename)[:200])
            continue
        kind = part.get_content_type()
        if kind not in ("text/plain", "text/html"):
            continue
        try:
            text = part.get_content()
        except (LookupError, UnicodeDecodeError, ValueError):
            payload = part.get_payload(decode=True) or b""
            text = payload.decode("cp1254", errors="replace")
        (plain if kind == "text/plain" else rich).append(str(text))
    return plain, rich, attachments


def _received(msg: EmailMessage) -> dt.datetime:
    try:
        value = parsedate_to_datetime(str(msg.get("date")))
    except (TypeError, ValueError, IndexError):
        return dt.datetime.now(dt.UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)
