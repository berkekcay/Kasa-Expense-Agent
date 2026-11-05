"""Encrypted API channel (app/secure_channel.py): handshake, tunnelled calls, gzip, streaming,
replay, tampering and the required mode. `TunnelClient` is a reference client in Python; the
web app's client (frontend/src/lib/api/secure.ts) follows the same steps, and both test the
same key derivation vector."""

from __future__ import annotations

import gzip
import json
import secrets
import struct
import time

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from app import secure_channel as sc
from app.config import get_settings

# Shared with frontend/src/lib/api/secure.test.ts: same inputs, same key, same frame.
VECTOR = {
    "shared": "6b" * 32,
    "id": "test-channel",
    "client": "Y2xpZW50",
    "server": "c2VydmVy",
    "nonce": "bm9uY2Utbm9uY2Utbm9uY2U=",
    "ts": 1793900000000,
    "exp": 1793943200,
    "key": "de35774beeb0bd8e02478d148081bf59b58127e3b8526e95848defae7580dd59",
    "iv": "000102030405060708090a0b",
    "plaintext": '{"m":"GET","p":"/health","h":{},"t":1793900000000}\n',
    "sealed": "c26f57db5f6824c0eae57a931e3b535d56ff9dc274b6a2669bac0587d1175c95a2d8498cbf7b9b2632be16c5f6632336925983fc373b7574d9f7dc34161b3c8f7c2bca",
}


class TunnelClient:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        private = ec.generate_private_key(ec.SECP256R1())
        public = sc.b64(
            private.public_key().public_bytes(
                serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
        nonce, ts = sc.b64(secrets.token_bytes(16)), int(time.time() * 1000)
        r = client.post("/secure/handshake", json={"client": public, "nonce": nonce, "ts": ts})
        assert r.status_code == 200, r.text
        out = r.json()
        server = serialization.load_der_public_key(sc.unb64(out["server"]))
        shared = private.exchange(ec.ECDH(), server)
        transcript = sc.transcript_of(out["id"], public, out["server"], nonce, ts, out["exp"])
        self.id = out["id"]
        self.aes = AESGCM(sc.derive_key(shared, transcript, self.id))
        self.seq = 0

    def seal(self, method: str, target: str, headers: dict, body: bytes, seq: int) -> bytes:
        meta = {"m": method, "p": target, "h": headers, "t": int(time.time() * 1000)}
        iv = secrets.token_bytes(12)
        plaintext = json.dumps(meta).encode() + b"\n" + body
        return iv + self.aes.encrypt(iv, plaintext, sc.request_aad(self.id, seq))

    def call(self, method: str, target: str, *, json_body=None, headers=None, body=b"", ctype=None):
        self.seq += 1
        headers = dict(headers or {})
        if json_body is not None:
            body, ctype = json.dumps(json_body).encode(), "application/json"
        if ctype:
            headers["content-type"] = ctype
        envelope = self.seal(method, target, headers, body, self.seq)
        r = self.post(envelope, self.seq)
        return self.open(r, self.seq)

    def post(self, envelope: bytes, seq: int) -> httpx.Response:
        return self.client.post(
            sc.TUNNEL_PATH,
            content=envelope,
            headers={
                "x-kasa-channel": self.id,
                "x-kasa-seq": str(seq),
                "content-type": "application/octet-stream",
            },
        )

    def open(self, r: httpx.Response, seq: int):
        assert r.status_code == 200, r.text
        assert r.headers["content-type"] == "application/octet-stream"
        data, pos, index, frames = r.content, 0, 0, []
        while pos < len(data):
            (length,) = struct.unpack(">I", data[pos : pos + 4])
            sealed = data[pos + 4 : pos + 4 + length]
            plain = self.aes.decrypt(sealed[:12], sealed[12:], sc.response_aad(self.id, seq, index))
            frames.append((plain[0], plain[1:]))
            pos, index = pos + 4 + length, index + 1
        assert frames[0][0] == sc.META and frames[-1] == (sc.END, b""), "head first, end last"
        meta = json.loads(frames[0][1])
        body = b"".join(gzip.decompress(p) if k == sc.DATA_GZIP else p for k, p in frames[1:-1])
        return meta["s"], meta["h"], body, [k for k, _ in frames]


@pytest.fixture
def secure(monkeypatch):
    monkeypatch.setattr(get_settings(), "api_encryption", "optional")
    sc.channels.clear()
    yield
    sc.channels.clear()


def as_user(user: str) -> dict[str, str]:
    return {"x-user-id": user}


def test_key_derivation_vector():
    """The browser's WebCrypto derivation must give the same key and frame as Python."""
    v = VECTOR
    transcript = sc.transcript_of(v["id"], v["client"], v["server"], v["nonce"], v["ts"], v["exp"])
    key = sc.derive_key(bytes.fromhex(v["shared"]), transcript, v["id"])
    sealed = AESGCM(key).encrypt(bytes.fromhex(v["iv"]), v["plaintext"].encode(), sc.request_aad(v["id"], 7))
    assert key.hex() == v["key"]
    assert sealed.hex() == v["sealed"]


def test_off_by_default(client):
    r = client.post("/secure/handshake", json={"client": "x" * 60, "nonce": "y" * 20, "ts": 0})
    assert r.status_code == 404


def test_json_calls_go_through_the_tunnel(client, secure):
    tunnel = TunnelClient(client)
    status, headers, body, _ = tunnel.call(
        "POST",
        "/expenses",
        json_body={"merchant": "Kahve Dünyası", "total": "85.50", "category": "food"},
        headers=as_user("secure-user"),
    )
    assert status == 201, body
    assert json.loads(body)["merchant"] == "Kahve Dünyası"
    status, headers, body, _ = tunnel.call("GET", "/expenses?limit=5", headers=as_user("secure-user"))
    assert status == 200 and headers["x-total-count"] == "1"
    assert [e["merchant"] for e in json.loads(body)] == ["Kahve Dünyası"]
    # The other user sees nothing: the inner request carries its own identity.
    _, _, other, _ = tunnel.call("GET", "/expenses", headers=as_user("secure-stranger"))
    assert json.loads(other) == []


def test_big_answers_are_gzipped_and_errors_come_back_inside(client, secure):
    tunnel = TunnelClient(client)
    for i in range(15):
        tunnel.call(
            "POST",
            "/expenses",
            json_body={"merchant": f"Market {i}", "total": "10.00", "category": "groceries"},
            headers=as_user("secure-gzip"),
        )
    status, _, body, kinds = tunnel.call("GET", "/expenses?limit=50", headers=as_user("secure-gzip"))
    assert status == 200 and len(json.loads(body)) == 15
    assert kinds == [sc.META, sc.DATA_GZIP, sc.END]
    status, _, body, kinds = tunnel.call("DELETE", "/expenses/999999", headers=as_user("secure-gzip"))
    assert status == 404 and "detail" in json.loads(body)
    assert kinds == [sc.META, sc.DATA, sc.END]


def test_multipart_upload_travels_inside(client, secure):
    tunnel = TunnelClient(client)
    built = httpx.Request(
        "POST", "http://x/imports/statement", files={"file": ("a.txt", b"hello", "text/plain")}
    )
    status, _, _, _ = tunnel.call(
        "POST",
        "/imports/statement",
        body=built.read(),
        ctype=built.headers["content-type"],
        headers=as_user("secure-upload"),
    )
    assert status == 422  # reached the route with the file: "no header row"


def test_replay_tamper_and_unknown_channel(client, secure):
    tunnel = TunnelClient(client)
    envelope = tunnel.seal("GET", "/expenses", as_user("secure-replay"), b"", 1)
    assert tunnel.post(envelope, 1).status_code == 200
    assert tunnel.post(envelope, 1).status_code == 409  # the same call again
    tampered = bytearray(tunnel.seal("GET", "/expenses", as_user("secure-replay"), b"", 2))
    tampered[-1] ^= 1
    assert tunnel.post(bytes(tampered), 2).status_code == 400
    assert tunnel.post(tunnel.seal("GET", "/expenses", {}, b"", 3), 4).status_code == 400  # wrong seq in aad
    # Failed decryptions do not close the channel.
    assert tunnel.post(tunnel.seal("GET", "/health", {}, b"", 5), 5).status_code == 200
    sc.channels.clear()  # e.g. the server restarted
    r = tunnel.post(tunnel.seal("GET", "/health", {}, b"", 6), 6)
    assert r.status_code == 412 and r.headers["x-kasa-channel"] == "reset"


def test_required_mode_refuses_plain_calls(client, secure, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_encryption", "required")
    r = client.get("/expenses", headers=as_user("secure-required"))
    assert r.status_code == 412 and r.headers["x-kasa-channel"] == "reset"
    assert client.get("/health").status_code == 200
    assert client.options("/expenses").status_code != 412
    tunnel = TunnelClient(client)
    status, _, _, _ = tunnel.call("GET", "/expenses", headers=as_user("secure-required"))
    assert status == 200


def test_streamed_answers_are_framed_per_chunk(secure):
    app = FastAPI()
    app.include_router(sc.router)

    @app.get("/stream")
    def stream():
        return StreamingResponse((f'{{"step": {i}}}\n' for i in range(3)), media_type="application/x-ndjson")

    app.add_middleware(sc.SecureTunnelMiddleware)
    with TestClient(app) as client:
        tunnel = TunnelClient(client)
        status, headers, body, kinds = tunnel.call("GET", "/stream")
    assert status == 200 and headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(line)["step"] for line in body.decode().splitlines()] == [0, 1, 2]
    assert kinds[0] == sc.META and kinds[-1] == sc.END and kinds.count(sc.DATA) >= 3


def test_an_error_inside_comes_back_encrypted(secure):
    app = FastAPI()
    app.include_router(sc.router)

    @app.get("/boom")
    def boom():
        raise RuntimeError("bug")

    app.add_middleware(sc.SecureTunnelMiddleware)
    with TestClient(app, raise_server_exceptions=False) as client:
        status, _, body, _ = TunnelClient(client).call("GET", "/boom")
    assert status == 500 and json.loads(body) == {"detail": "internal error"}
