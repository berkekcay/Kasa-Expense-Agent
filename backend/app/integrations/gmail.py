"""Gmail API v1 client (owner: track INGEST). Read-only scope; plain REST over httpx with the
access token from `google_oauth.credentials_for_user`. Raises UpstreamError on API failures
and NotFound for 404 (e.g. a history id that is too old).

Email content is untrusted DATA: it is shown to the email-parse agent as text, never as
instructions, and never rendered as HTML anywhere. Bodies are never logged.

Message bodies: `messages.get?format=full` returns the MIME tree in `payload`; every leaf has
`body.data`, the part's bytes after Gmail undid the Content-Transfer-Encoding (base64 or
quoted-printable), themselves encoded as base64url. The bytes keep the part's charset.
"""

from __future__ import annotations

import base64
import datetime as dt
import html
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from html.parser import HTMLParser

import httpx
from google.oauth2.credentials import Credentials

from app.services.errors import NotFound, UpstreamError

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"
MAX_BODY_CHARS = 20_000
_HISTORY_MAX_PAGES = 20
# Labels whose new messages are not mail the user received.
_SKIP_LABELS = {"SPAM", "TRASH", "DRAFT", "SENT", "CHAT"}


def http_client() -> httpx.Client:
    """HTTP client for every Gmail call. Tests monkeypatch this."""
    return httpx.Client(timeout=httpx.Timeout(20.0))


@dataclass
class GmailMessage:
    id: str
    thread_id: str
    history_id: str
    received_at: dt.datetime  # internalDate, UTC
    subject: str
    sender: str
    snippet: str
    body_text: str  # text/plain part, or HTML converted to plain text; trimmed to ~20k chars
    attachment_names: list[str] = field(default_factory=list)


def _request(creds: Credentials, method: str, path: str, *, params=None, json=None) -> dict:
    headers = {"Authorization": f"Bearer {creds.token}", "Accept": "application/json"}
    try:
        with http_client() as client:
            r = client.request(method, GMAIL_API + path, params=params, json=json, headers=headers)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"Gmail API unreachable ({type(exc).__name__})") from exc
    what = path.split("/")[1] if "/" in path else path
    if r.status_code == 404:
        raise NotFound(f"Gmail {what}: not found")
    if r.status_code >= 400:
        reason = ""
        try:
            reason = str(r.json().get("error", {}).get("status") or "")
        except (ValueError, AttributeError):
            pass
        raise UpstreamError(f"Gmail {what} failed: HTTP {r.status_code} {reason}".strip())
    if not r.content:
        return {}
    try:
        return r.json()
    except ValueError as exc:
        raise UpstreamError(f"Gmail {what} returned invalid JSON") from exc


# --- listing -------------------------------------------------------------------------------


def list_message_ids(creds: Credentials, query: str, *, max_results: int = 50) -> list[str]:
    """Ids of the newest messages matching a Gmail search query (newest first)."""
    ids: list[str] = []
    page_token = None
    while len(ids) < max_results:
        params = {"q": query, "maxResults": min(500, max_results - len(ids))}
        if page_token:
            params["pageToken"] = page_token
        data = _request(creds, "GET", "/messages", params=params)
        ids.extend(m["id"] for m in data.get("messages") or [] if m.get("id"))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return list(dict.fromkeys(ids))[:max_results]


def list_history(creds: Credentials, start_history_id: str) -> tuple[list[str], str]:
    """Message ids added since `start_history_id` and the new latest history id.
    Raise NotFound when Google says the start id is too old (caller falls back to a query)."""
    ids: list[str] = []
    latest = start_history_id
    page_token = None
    for _ in range(_HISTORY_MAX_PAGES):
        params = {"startHistoryId": start_history_id, "historyTypes": "messageAdded", "maxResults": 500}
        if page_token:
            params["pageToken"] = page_token
        data = _request(creds, "GET", "/history", params=params)
        latest = str(data.get("historyId") or latest)
        for record in data.get("history") or []:
            for added in record.get("messagesAdded") or []:
                message = added.get("message") or {}
                if message.get("id") and not _SKIP_LABELS.intersection(message.get("labelIds") or []):
                    ids.append(message["id"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return list(dict.fromkeys(ids)), latest


def profile_history_id(creds: Credentials) -> str:
    """The mailbox's current history id (users.getProfile)."""
    return str(_request(creds, "GET", "/profile").get("historyId") or "")


def watch(creds: Credentials, topic: str) -> tuple[str, dt.datetime]:
    """users.watch on INBOX to the Pub/Sub topic; returns (history_id, expiration UTC)."""
    data = _request(
        creds,
        "POST",
        "/watch",
        json={"topicName": topic, "labelIds": ["INBOX"], "labelFilterBehavior": "INCLUDE"},
    )
    try:
        expires = dt.datetime.fromtimestamp(int(data["expiration"]) / 1000, dt.UTC)
        return str(data["historyId"]), expires
    except (KeyError, ValueError, TypeError) as exc:
        raise UpstreamError("Gmail watch returned an unexpected answer") from exc


def stop_watch(creds: Credentials) -> None:
    _request(creds, "POST", "/stop")


# --- one message ---------------------------------------------------------------------------


def get_message(creds: Credentials, message_id: str) -> GmailMessage:
    data = _request(creds, "GET", f"/messages/{message_id}", params={"format": "full"})
    return message_from_api(data)


def message_from_api(data: dict) -> GmailMessage:
    """Turn a users.messages.get (format=full) resource into a GmailMessage."""
    payload = data.get("payload") or {}
    headers = _headers(payload)
    try:
        received = dt.datetime.fromtimestamp(int(data.get("internalDate") or 0) / 1000, dt.UTC)
    except (TypeError, ValueError):
        received = dt.datetime.now(dt.UTC)
    plain: list[str] = []
    rich: list[str] = []
    attachments: list[str] = []
    _walk(payload, plain, rich, attachments)
    body = next((t for t in plain if t.strip()), "") or next((t for t in rich if t.strip()), "")
    return GmailMessage(
        id=str(data.get("id") or ""),
        thread_id=str(data.get("threadId") or ""),
        history_id=str(data.get("historyId") or ""),
        received_at=received,
        subject=_one_line(_decode_words(headers.get("subject", ""))),
        sender=_one_line(_decode_words(headers.get("from", ""))),
        snippet=_one_line(html.unescape(data.get("snippet") or "")),
        body_text=_tidy(body)[:MAX_BODY_CHARS],
        attachment_names=attachments,
    )


def _headers(part: dict) -> dict[str, str]:
    return {h.get("name", "").lower(): h.get("value", "") for h in part.get("headers") or []}


def _walk(part: dict, plain: list[str], rich: list[str], attachments: list[str]) -> None:
    mime = (part.get("mimeType") or "").lower()
    headers = _headers(part)
    filename = part.get("filename") or ""
    is_attachment = bool(filename) or headers.get("content-disposition", "").lower().startswith("attachment")
    if mime.startswith("multipart/") or part.get("parts"):
        for child in part.get("parts") or []:
            _walk(child, plain, rich, attachments)
        return
    if is_attachment:
        if filename:
            attachments.append(_one_line(filename)[:200])
        return
    data = (part.get("body") or {}).get("data")
    if not data or mime not in ("text/plain", "text/html"):
        return
    text = decode_body(data, _charset(headers.get("content-type", "")))
    if mime == "text/plain":
        plain.append(text)
    else:
        rich.append(html_to_text(text))


def _charset(content_type: str) -> str | None:
    match = re.search(r'charset\s*=\s*"?([A-Za-z0-9._:-]+)', content_type, re.IGNORECASE)
    return match.group(1) if match else None


def decode_body(data: str, charset: str | None) -> str:
    """base64url body data -> text. Valid UTF-8 wins (Gmail sometimes re-encodes); otherwise
    the declared charset, otherwise Windows-1254 (Turkish) with replacement characters."""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    for encoding in (charset, "cp1254"):
        if not encoding:
            continue
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("cp1254", errors="replace")


class _TextExtractor(HTMLParser):
    _SKIP = frozenset({"script", "style", "head", "title", "noscript", "template", "svg"})
    _BLOCK = frozenset(
        {"p", "div", "br", "tr", "li", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6", "hr"}
    )
    _CELL = frozenset({"td", "th"})
    _VOID = frozenset({"br", "hr", "img", "meta", "link", "input", "col", "area", "base", "wbr", "source"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[tuple[str, bool]] = []  # (tag, hides its content)

    def _hidden(self) -> bool:
        return any(hide for _tag, hide in self.stack)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        style = (dict(attrs).get("style") or "").replace(" ", "").lower()
        hides = (
            tag in self._SKIP
            or "display:none" in style
            or "visibility:hidden" in style
            or any(k == "hidden" for k, _ in attrs)
        )
        if tag in self._BLOCK:
            self.out.append("\n")
        elif tag in self._CELL:
            self.out.append("  ")
        if tag not in self._VOID:
            self.stack.append((tag, hides))

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in self._BLOCK and tag not in ("tr", "li"):  # rows: the newline before is enough
            self.out.append("\n")

    def handle_data(self, data):
        if not self._hidden():
            self.out.append(data)


def html_to_text(markup: str) -> str:
    """Visible text of an HTML email (scripts, styles and hidden elements dropped)."""
    parser = _TextExtractor()
    try:
        parser.feed(markup)
        parser.close()
    except Exception:  # noqa: BLE001 - malformed markup: fall back to stripping tags
        return re.sub(r"<[^>]+>", " ", markup)
    return "".join(parser.out)


def _tidy(text: str) -> str:
    lines = [" ".join(line.replace(" ", " ").split()) for line in text.replace("\r", "").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _decode_words(value: str) -> str:
    """Gmail usually returns decoded header values; decode RFC 2047 words if any are left."""
    if "=?" not in value:
        return value
    try:
        return str(make_header(decode_header(value)))
    except (ValueError, LookupError, UnicodeDecodeError):
        return value


def _one_line(text: str) -> str:
    return " ".join(text.split())
