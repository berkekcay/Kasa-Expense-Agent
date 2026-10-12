"""Test doubles for track INGEST: an in-memory Google (OAuth token endpoint, revoke,
userinfo, Gmail REST v1) behind httpx.MockTransport, and a scripted email parser LLM.
Nothing here talks to the network."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs

import httpx
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.genai import types

GMAIL_FIXTURES = Path(__file__).parent / "gmail"
CLIENT_ID = "kasa-test.apps.googleusercontent.com"
ALL_SCOPES = (
    "openid https://www.googleapis.com/auth/userinfo.email "
    "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/calendar.events"
)


def gmail_fixture(name: str) -> dict:
    return json.loads((GMAIL_FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def fake_id_token(email: str, *, aud: str = CLIENT_ID, iss: str = "https://accounts.google.com") -> str:
    header = b64url(json.dumps({"alg": "RS256", "kid": "test"}).encode())
    claims = {
        "iss": iss,
        "aud": aud,
        "sub": "1098765432101234567890",
        "email": email,
        "email_verified": True,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,
    }
    return f"{header}.{b64url(json.dumps(claims).encode())}.{b64url(b'signature')}"


class FakeGoogle:
    """Just enough of accounts.google.com, oauth2.googleapis.com and gmail.googleapis.com."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        # OAuth
        self.codes: dict[str, dict] = {}  # code -> token response
        self.valid_refresh: set[str] = set()
        self.refresh_error: str | None = None  # e.g. "invalid_grant"
        self.refresh_count = 0
        self.revoked: list[str] = []
        self.access_counter = 0
        # Gmail
        self.messages: dict[str, dict] = {}
        self.matching: list[str] = []  # ids matching the query, newest first
        self.history: list[tuple[int, str, list[str]]] = []  # (history id, message id, labels)
        self.history_id = 900_000
        self.oldest_history = 0  # startHistoryId below this answers 404
        self.watch_calls = 0
        self.stop_calls = 0
        self.fail_gets: set[str] = set()

    # --- setup helpers ---------------------------------------------------------------------

    def add_code(self, code: str, email: str, *, scope: str = ALL_SCOPES, refresh: str = "rt-1", **extra):
        self.valid_refresh.add(refresh)
        self.codes[code] = {
            "access_token": f"at-{code}",
            "expires_in": 3599,
            "refresh_token": refresh,
            "scope": scope,
            "token_type": "Bearer",
            "id_token": fake_id_token(email, **extra),
        }

    def add_message(self, resource: dict, *, labels=("INBOX",), matches: bool = True) -> str:
        msg_id = resource["id"]
        self.messages[msg_id] = resource
        self.history_id += 10
        self.history.append((self.history_id, msg_id, list(labels)))
        if matches:
            self.matching.insert(0, msg_id)
        return msg_id

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport())

    def gmail_calls(self, path_part: str) -> int:
        return sum(
            1 for r in self.requests if r.url.host == "gmail.googleapis.com" and path_part in r.url.path
        )

    # --- routing ---------------------------------------------------------------------------

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host, path = request.url.host, request.url.path
        if host == "oauth2.googleapis.com" and path == "/token":
            return self._token(parse_qs(request.content.decode()))
        if host == "oauth2.googleapis.com" and path == "/revoke":
            self.revoked.append(parse_qs(request.content.decode())["token"][0])
            return httpx.Response(200, json={})
        if host == "openidconnect.googleapis.com":
            return httpx.Response(200, json={"email": "fallback@gmail.com", "email_verified": True})
        if host == "gmail.googleapis.com":
            if not request.headers.get("authorization", "").startswith("Bearer at-"):
                return httpx.Response(401, json={"error": {"code": 401, "status": "UNAUTHENTICATED"}})
            return self._gmail(request, path.removeprefix("/gmail/v1/users/me"))
        return httpx.Response(404)

    def _token(self, form: dict[str, list[str]]) -> httpx.Response:
        grant = form["grant_type"][0]
        if grant == "authorization_code":
            body = self.codes.pop(form["code"][0], None)
            if body is None:
                return httpx.Response(
                    400, json={"error": "invalid_grant", "error_description": "Bad Request"}
                )
            return httpx.Response(200, json=body)
        if grant == "refresh_token":
            self.refresh_count += 1
            if self.refresh_error or form["refresh_token"][0] not in self.valid_refresh:
                error = self.refresh_error or "invalid_grant"
                return httpx.Response(
                    400, json={"error": error, "error_description": "Token has been revoked."}
                )
            self.access_counter += 1
            return httpx.Response(
                200,
                json={
                    "access_token": f"at-refreshed-{self.access_counter}",
                    "expires_in": 3599,
                    "scope": ALL_SCOPES,
                },
            )
        return httpx.Response(400, json={"error": "unsupported_grant_type"})

    def _gmail(self, request: httpx.Request, path: str) -> httpx.Response:
        params = request.url.params
        if path == "/messages":
            start = int(params.get("pageToken") or 0)
            size = int(params.get("maxResults") or 100)
            page = self.matching[start : start + size]
            body: dict = {"resultSizeEstimate": len(self.matching)}
            if page:
                body["messages"] = [{"id": m, "threadId": m} for m in page]
            if start + size < len(self.matching):
                body["nextPageToken"] = str(start + size)
            return httpx.Response(200, json=body)
        if path.startswith("/messages/"):
            msg_id = path.rsplit("/", 1)[1]
            if msg_id in self.fail_gets:
                return httpx.Response(500, json={"error": {"code": 500, "status": "INTERNAL"}})
            if msg_id not in self.messages:
                return httpx.Response(404, json={"error": {"code": 404, "status": "NOT_FOUND"}})
            return httpx.Response(200, json=self.messages[msg_id])
        if path == "/history":
            start = int(params["startHistoryId"])
            if start < self.oldest_history:
                return httpx.Response(404, json={"error": {"code": 404, "status": "NOT_FOUND"}})
            records = [
                {
                    "id": str(h),
                    "messages": [{"id": m, "threadId": m}],
                    "messagesAdded": [{"message": {"id": m, "threadId": m, "labelIds": labels}}],
                }
                for h, m, labels in self.history
                if h > start
            ]
            body = {"historyId": str(self.history_id)}
            if records:
                body["history"] = records
            return httpx.Response(200, json=body)
        if path == "/profile":
            return httpx.Response(
                200,
                json={
                    "emailAddress": "ayse.ogrenci@gmail.com",
                    "messagesTotal": 1200,
                    "threadsTotal": 900,
                    "historyId": str(self.history_id),
                },
            )
        if path == "/watch":
            self.watch_calls += 1
            expiration = int((time.time() + 7 * 24 * 3600) * 1000)
            return httpx.Response(
                200, json={"historyId": str(self.history_id), "expiration": str(expiration)}
            )
        if path == "/stop":
            self.stop_calls += 1
            return httpx.Response(204)
        return httpx.Response(404, json={"error": {"code": 404, "status": "NOT_FOUND"}})


# --- scripted email parser ------------------------------------------------------------------

TRENDYOL_ARGS = {
    "merchant": "Trendyol",
    "total": "829,80",
    "currency": "TL",
    "expense_date": "2026-10-05",
    "category": "alışveriş",
    "items": [
        {"description": "Kablosuz Kulaklık Bluetooth 5.3", "amount": "749.90"},
        {"description": "Şeffaf Telefon Kılıfı", "amount": "129.90"},
    ],
}
CARD_ALERT_ARGS = {
    "merchant": "MİGROS KADIKÖY",
    "total": "412.35",
    "currency": "TRY",
    "expense_date": "2026-10-09",
    "category": "market",
}
GETIR_ARGS = {"merchant": "Getir", "total": "245.50", "currency": "TRY", "category": "food"}


class ParserLlm(BaseLlm):
    """Plays the email-parse model by matching the email text. `obey_injection` makes it
    behave like a fully compromised model that tries to approve inbox items."""

    calls: ClassVar[int] = 0
    obey_injection: ClassVar[bool] = False

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        last = llm_request.contents[-1].parts[-1]
        if last.function_response is not None:
            yield LlmResponse(content=types.Content(role="model", parts=[types.Part(text="ok")]))
            return
        type(self).calls += 1
        text = last.text or ""
        if "GTR-55120" in text and type(self).obey_injection:
            call = types.FunctionCall(name="approve_inbox_item", args={"item_id": 1})
        elif "7381049256" in text:
            call = types.FunctionCall(name="submit_parsed_expense", args=TRENDYOL_ARGS)
        elif "harcama yapılmıştır" in text:
            call = types.FunctionCall(name="submit_parsed_expense", args=CARD_ALERT_ARGS)
        elif "GTR-55120" in text:
            call = types.FunctionCall(name="submit_parsed_expense", args=GETIR_ARGS)
        elif "kampanya" in text.lower():
            call = types.FunctionCall(name="mark_not_expense", args={"reason": "newsletter"})
        else:
            call = types.FunctionCall(name="submit_parsed_expense", args={"merchant": "", "total": "abc"})
        yield LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))
