"""Encrypted API channel on top of HTTPS: every call of the web app travels through one
endpoint as an opaque, encrypted envelope (owner: track SECURITY).

HTTPS already protects the wire. This layer adds what HTTPS does not: the URL, the session
token and the body of each call are not visible in the browser's network tab, in proxy or
server access logs, or to a TLS-inspecting middlebox; a captured call cannot be replayed;
and a response belongs to exactly one request. It does not hide anything from the user's own
browser (the page holds the key), and it is not a replacement for HTTPS.

Handshake, `POST /secure/handshake` (plain JSON):
    client -> {client: SPKI of a fresh ECDH P-256 key, nonce: 16 random bytes, ts: ms}
    server -> {id, server: SPKI of its own fresh ECDH P-256 key, exp, v: 1}
    shared = ECDH x-coordinate; key = HKDF-SHA256(shared, salt=SHA-256(transcript),
             info="kasa-secure-v1|<id>", 32 bytes) -> AES-256-GCM.
    transcript = "kasa-secure-v1|id|client|server|nonce|ts|exp". Both private keys are thrown
    away after the derivation (forward secrecy); the server only keeps the AES key.

Call, `POST /secure/tunnel`, headers x-kasa-channel: <id>, x-kasa-seq: <n>:
    body  = iv(12) | AES-GCM(plaintext, aad="kasa-v1|req|<id>|<n>")
    plaintext = JSON {m: method, p: path?query, h: {header: value}, t: ms} + "\\n" + raw body
    The inner request (method, path, Authorization, content type, multipart uploads too) is
    rebuilt from the plaintext and runs through the normal routes.

Answer: 200, application/octet-stream, a sequence of frames [u32 length][iv | ciphertext],
    frame i encrypted with aad="kasa-v1|res|<id>|<n>|<i>", so it only decrypts as the answer
    to request n, in order. Plaintext first byte: 0 meta JSON {s: status, h: headers},
    1 body bytes, 2 gzip-compressed body bytes, 3 end. Streamed answers (the chat's live steps)
    become one frame per chunk; whole answers over 1 KB are gzipped first. A missing end frame
    means the answer was cut off.

Replay: n must be new and within the last 256 of the channel. Unknown or expired channel:
412 with x-kasa-channel: reset, and the client shakes hands again. Failed decryptions are
answered with 400 and do not close the channel (a stranger who saw the id cannot kill it).

API_ENCRYPTION: off (no endpoints), optional (the app uses it, plain calls still work),
required (plain calls get 412 except health, the handshake, OAuth callbacks and internal jobs).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import logging
import secrets
import struct
import threading
import time
from collections import OrderedDict, deque
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import get_settings

log = logging.getLogger(__name__)

VERSION = "kasa-secure-v1"
TUNNEL_PATH = "/secure/tunnel"
CHANNEL_HEADER = "x-kasa-channel"
SEQ_HEADER = "x-kasa-seq"
LIFETIME_S = 12 * 3600
IDLE_S = 60 * 60
CLOCK_SKEW_MS = 5 * 60 * 1000
REPLAY_WINDOW = 256
MAX_CHANNELS = 10_000
MAX_BODY = 25 * 1024 * 1024
GZIP_MIN = 1024
HANDSHAKES_PER_MINUTE = 60

META, DATA, DATA_GZIP, END = 0, 1, 2, 3
# Plain calls that stay allowed when the channel is required: no user data in them, or the
# caller is not our web app (Google's redirects, Cloud Scheduler and Pub/Sub).
PLAIN_ALLOWED = ("/health", "/secure/handshake", "/docs", "/redoc", "/openapi.json", "/internal/")
PLAIN_ALLOWED_EXACT = ("/integrations/google/callback", "/auth/google/callback")
# Inner request headers the client may set; everything else comes from the outer request.
INNER_HEADERS = {"authorization", "x-user-id", "content-type", "accept", "accept-language"}
# Answer headers worth carrying back.
OUTER_HEADERS = {"content-type", "content-disposition", "x-total-count", "location", "retry-after"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def unb64(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def derive_key(shared: bytes, transcript: str, channel_id: str) -> bytes:
    salt = hashlib.sha256(transcript.encode("utf-8")).digest()
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=f"{VERSION}|{channel_id}".encode())
    return hkdf.derive(shared)


def transcript_of(channel_id: str, client: str, server: str, nonce: str, ts: int, exp: int) -> str:
    return f"{VERSION}|{channel_id}|{client}|{server}|{nonce}|{ts}|{exp}"


def request_aad(channel_id: str, seq: int) -> bytes:
    return f"kasa-v1|req|{channel_id}|{seq}".encode()


def response_aad(channel_id: str, seq: int, index: int) -> bytes:
    return f"kasa-v1|res|{channel_id}|{seq}|{index}".encode()


def frame(aes: AESGCM, aad: bytes, kind: int, payload: bytes) -> bytes:
    iv = secrets.token_bytes(12)
    sealed = iv + aes.encrypt(iv, bytes([kind]) + payload, aad)
    return struct.pack(">I", len(sealed)) + sealed


# --- channels --------------------------------------------------------------------------------


@dataclass
class Channel:
    id: str
    aes: AESGCM
    expires: float
    last_used: float = field(default_factory=time.time)
    newest: int = 0
    seen: set[int] = field(default_factory=set)

    def accept(self, seq: int) -> bool:
        """True the first time a sequence number within the replay window is used."""
        if seq <= 0 or seq <= self.newest - REPLAY_WINDOW or seq in self.seen:
            return False
        self.seen.add(seq)
        if seq > self.newest:
            self.newest = seq
            self.seen = {s for s in self.seen if s > seq - REPLAY_WINDOW}
        return True


class ChannelStore:
    """Channels in memory. A restart forgets them; clients then shake hands again (412)."""

    def __init__(self) -> None:
        self._channels: OrderedDict[str, Channel] = OrderedDict()
        self._lock = threading.Lock()
        self._handshakes: dict[str, deque[float]] = {}

    def add(self, channel: Channel) -> None:
        with self._lock:
            self._channels[channel.id] = channel
            while len(self._channels) > MAX_CHANNELS:
                self._channels.popitem(last=False)

    def get(self, channel_id: str) -> Channel | None:
        now = time.time()
        with self._lock:
            channel = self._channels.get(channel_id)
            if channel is None:
                return None
            if now > channel.expires or now - channel.last_used > IDLE_S:
                del self._channels[channel_id]
                return None
            channel.last_used = now
            self._channels.move_to_end(channel_id)
            return channel

    def allow_handshake(self, client_ip: str) -> bool:
        now = time.time()
        with self._lock:
            recent = self._handshakes.setdefault(client_ip, deque())
            while recent and now - recent[0] > 60:
                recent.popleft()
            if len(recent) >= HANDSHAKES_PER_MINUTE:
                return False
            recent.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._channels.clear()
            self._handshakes.clear()


channels = ChannelStore()


# --- handshake -------------------------------------------------------------------------------


class HandshakeIn(BaseModel):
    client: str = Field(min_length=40, max_length=400)  # base64 SPKI, ECDH P-256
    nonce: str = Field(min_length=16, max_length=64)
    ts: int


class HandshakeOut(BaseModel):
    id: str
    server: str
    exp: int
    v: int = 1


router = APIRouter(prefix="/secure", tags=["security"])


@router.post("/handshake", response_model=HandshakeOut)
def handshake(body: HandshakeIn, request: Request) -> HandshakeOut:
    if get_settings().api_encryption == "off":
        raise HTTPException(status_code=404, detail="the encrypted channel is off")
    if not channels.allow_handshake(request.client.host if request.client else "?"):
        raise HTTPException(status_code=429, detail="too many handshakes, try again in a minute")
    if abs(time.time() * 1000 - body.ts) > CLOCK_SKEW_MS:
        raise HTTPException(status_code=400, detail="the computer's clock is off by more than 5 minutes")
    try:
        client_key = serialization.load_der_public_key(unb64(body.client))
        unb64(body.nonce)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="invalid handshake") from exc
    if not isinstance(client_key, ec.EllipticCurvePublicKey) or not isinstance(
        client_key.curve, ec.SECP256R1
    ):
        raise HTTPException(status_code=400, detail="the handshake needs an ECDH P-256 key")

    server_private = ec.generate_private_key(ec.SECP256R1())
    server_public = b64(
        server_private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    shared = server_private.exchange(ec.ECDH(), client_key)
    channel_id = secrets.token_urlsafe(18)
    exp = int(time.time()) + LIFETIME_S
    transcript = transcript_of(channel_id, body.client, server_public, body.nonce, body.ts, exp)
    channels.add(Channel(channel_id, AESGCM(derive_key(shared, transcript, channel_id)), expires=exp))
    return HandshakeOut(id=channel_id, server=server_public, exp=exp)


# --- the tunnel (ASGI middleware) ------------------------------------------------------------


def _plain(status: int, detail: str, *, reset: bool = False):
    headers = [(b"content-type", b"application/json"), (b"cache-control", b"no-store")]
    if reset:
        headers.append((CHANNEL_HEADER.encode(), b"reset"))
    body = json.dumps({"detail": detail}).encode()

    async def respond(send) -> None:
        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    return respond


def _plain_allowed(path: str) -> bool:
    return path in PLAIN_ALLOWED_EXACT or any(
        path == p or (p.endswith("/") and path.startswith(p)) for p in PLAIN_ALLOWED
    )


class SecureTunnelMiddleware:
    """Opens `POST /secure/tunnel` envelopes, runs the inner request, seals the answer."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        mode = get_settings().api_encryption
        if mode == "off":
            await self.app(scope, receive, send)
            return
        if scope["path"] == TUNNEL_PATH and scope["method"] == "POST":
            await self._tunnel(scope, receive, send)
            return
        if mode == "required" and scope["method"] != "OPTIONS" and not _plain_allowed(scope["path"]):
            await _plain(412, "this server only accepts encrypted calls", reset=True)(send)
            return
        await self.app(scope, receive, send)

    async def _tunnel(self, scope, receive, send) -> None:
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        channel = channels.get(headers.get(CHANNEL_HEADER, ""))
        if channel is None:
            await _plain(412, "unknown or expired channel", reset=True)(send)
            return
        try:
            seq = int(headers.get(SEQ_HEADER, ""))
        except ValueError:
            await _plain(400, "missing sequence number")(send)
            return

        body = bytearray()
        while True:
            message = await receive()
            body += message.get("body", b"")
            if len(body) > MAX_BODY:
                await _plain(413, "the call is too large")(send)
                return
            if not message.get("more_body"):
                break
        try:
            plaintext = channel.aes.decrypt(bytes(body[:12]), bytes(body[12:]), request_aad(channel.id, seq))
        except (InvalidTag, ValueError):
            await _plain(400, "the call could not be decrypted")(send)
            return
        if not channel.accept(seq):
            await _plain(409, "this call was already made (replay)")(send)
            return
        head, _, inner_body = plaintext.partition(b"\n")
        try:
            meta = json.loads(head)
            method, target = str(meta["m"]).upper(), str(meta["p"])
            if abs(time.time() * 1000 - int(meta["t"])) > CLOCK_SKEW_MS:
                raise ValueError("clock")
            if not target.startswith("/") or target.startswith(TUNNEL_PATH):
                raise ValueError("target")
        except (ValueError, KeyError, TypeError):
            await _plain(400, "invalid call")(send)
            return

        path, _, query = target.partition("?")
        inner_headers = [
            (k, v)
            for k, v in scope["headers"]
            if k.decode("latin-1").lower()
            not in INNER_HEADERS | {"content-length", CHANNEL_HEADER, SEQ_HEADER}
        ]
        for name, value in (meta.get("h") or {}).items():
            if name.lower() in INNER_HEADERS:
                inner_headers.append((name.lower().encode("latin-1"), str(value).encode("latin-1")))
        inner_headers.append((b"content-length", str(len(inner_body)).encode()))
        inner_scope = {
            **scope,
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": query.encode("utf-8"),
            "headers": inner_headers,
            "kasa_secure": True,
        }

        sent = False

        async def inner_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(inner_body), "more_body": False}
            return await receive()  # waits for the client to disconnect, like a real request

        await self._run(inner_scope, inner_receive, send, channel, seq)

    async def _run(self, scope, receive, send, channel: Channel, seq: int) -> None:
        index = 0
        start: dict | None = None
        streaming = False

        def seal(kind: int, payload: bytes) -> bytes:
            nonlocal index
            sealed = frame(channel.aes, response_aad(channel.id, seq, index), kind, payload)
            index += 1
            return sealed

        def meta_frame() -> bytes:
            assert start is not None
            carried = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in start.get("headers", [])
                if k.decode("latin-1").lower() in OUTER_HEADERS
            }
            return seal(META, json.dumps({"s": start["status"], "h": carried}).encode())

        async def outer_start() -> None:
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/octet-stream"),
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                    ],
                }
            )

        async def inner_send(message) -> None:
            nonlocal start, streaming
            if message["type"] == "http.response.start":
                start = message
                return
            if message["type"] != "http.response.body":
                return
            chunk = message.get("body", b"")
            more = message.get("more_body", False)
            if not streaming and not more:  # the whole answer at once
                kind, payload = DATA, chunk
                if len(chunk) >= GZIP_MIN:
                    kind, payload = DATA_GZIP, gzip.compress(chunk, compresslevel=6)
                frames = meta_frame() + (seal(kind, payload) if chunk else b"") + seal(END, b"")
                await outer_start()
                await send({"type": "http.response.body", "body": frames})
                return
            out = b""
            if not streaming:  # first chunk of a streamed answer: send the head now
                streaming = True
                await outer_start()
                out += meta_frame()
            if chunk:
                out += seal(DATA, chunk)
            if not more:
                out += seal(END, b"")
            await send({"type": "http.response.body", "body": out, "more_body": more})

        try:
            await self.app(scope, receive, inner_send)
        except Exception:
            log.exception("error inside a tunnelled call to %s", scope["path"])
            if streaming:
                return  # no end frame: the client reports the answer as cut off
            start = {"status": 500, "headers": [(b"content-type", b"application/json")]}
            await outer_start()
            detail = json.dumps({"detail": "internal error"}).encode()
            await send(
                {"type": "http.response.body", "body": meta_frame() + seal(DATA, detail) + seal(END, b"")}
            )
