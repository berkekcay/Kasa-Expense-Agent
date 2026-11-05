// @vitest-environment node
// The browser half of the encrypted API channel. The key derivation vector is the same as in
// backend/tests/test_secure_channel.py, so Python and WebCrypto must agree byte for byte.
import { describe, expect, it } from "vitest";
import { deriveKey, openAnswer, requestAad, responseAad, transcript } from "./secure";

const VECTOR = {
  shared: "6b".repeat(32),
  id: "test-channel",
  client: "Y2xpZW50",
  server: "c2VydmVy",
  nonce: "bm9uY2Utbm9uY2Utbm9uY2U=",
  ts: 1793900000000,
  exp: 1793943200,
  key: "de35774beeb0bd8e02478d148081bf59b58127e3b8526e95848defae7580dd59",
  iv: "000102030405060708090a0b",
  plaintext: '{"m":"GET","p":"/health","h":{},"t":1793900000000}\n',
  sealed:
    "c26f57db5f6824c0eae57a931e3b535d56ff9dc274b6a2669bac0587d1175c95a2d8498cbf7b9b2632be16c5f6632336925983fc373b7574d9f7dc34161b3c8f7c2bca",
};

const hex = (data: ArrayBuffer) => Array.from(new Uint8Array(data), (b) => b.toString(16).padStart(2, "0")).join("");
const fromHex = (text: string) => Uint8Array.from(text.match(/../g)!, (h) => parseInt(h, 16));
const encoder = new TextEncoder();

async function vectorKey(extractable = false) {
  const v = VECTOR;
  return deriveKey(fromHex(v.shared), transcript(v.id, v.client, v.server, v.nonce, v.ts, v.exp), v.id, extractable);
}

async function sealFrame(key: CryptoKey, seq: number, index: number, kind: number, payload: Uint8Array) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const plain = new Uint8Array([kind, ...payload]);
  const sealed = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: responseAad(VECTOR.id, seq, index) }, key, plain),
  );
  const out = new Uint8Array(4 + 12 + sealed.length);
  new DataView(out.buffer).setUint32(0, 12 + sealed.length);
  out.set(iv, 4);
  out.set(sealed, 16);
  return out;
}

async function gzip(text: string) {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** An answer whose bytes arrive in small pieces, like a network stream. */
function answer(...frames: Uint8Array[]) {
  const all = new Uint8Array(frames.reduce((n, f) => n + f.length, 0));
  let at = 0;
  for (const f of frames) {
    all.set(f, at);
    at += f.length;
  }
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < all.length; i += 7) controller.enqueue(all.slice(i, i + 7));
      controller.close();
    },
  });
  return new Response(body, { headers: { "content-type": "application/octet-stream" } });
}

describe("secure channel", () => {
  it("derives the same key and ciphertext as the Python server", async () => {
    const key = await vectorKey(true);
    expect(hex(await crypto.subtle.exportKey("raw", key))).toBe(VECTOR.key);
    const sealed = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: fromHex(VECTOR.iv), additionalData: requestAad(VECTOR.id, 7) },
      key,
      encoder.encode(VECTOR.plaintext),
    );
    expect(hex(sealed)).toBe(VECTOR.sealed);
  });

  it("opens a framed answer: status, headers, gzip and streamed parts", async () => {
    const key = await vectorKey();
    const meta = encoder.encode(JSON.stringify({ s: 201, h: { "content-type": "application/json", "x-total-count": "2" } }));
    const res = await openAnswer(
      answer(
        await sealFrame(key, 3, 0, 0, meta),
        await sealFrame(key, 3, 1, 2, await gzip('{"merchant":')),
        await sealFrame(key, 3, 2, 1, encoder.encode('"Kahve"}')),
        await sealFrame(key, 3, 3, 3, new Uint8Array()),
      ),
      key,
      VECTOR.id,
      3,
    );
    expect(res.status).toBe(201);
    expect(res.headers.get("x-total-count")).toBe("2");
    expect(await res.json()).toEqual({ merchant: "Kahve" });
  });

  it("refuses an answer meant for another request or cut off before its end", async () => {
    const key = await vectorKey();
    const meta = encoder.encode(JSON.stringify({ s: 200, h: {} }));
    await expect(openAnswer(answer(await sealFrame(key, 4, 0, 0, meta)), key, VECTOR.id, 5)).rejects.toThrow();

    await expect(
      openAnswer(answer(await sealFrame(key, 6, 0, 0, meta), await sealFrame(key, 6, 1, 1, encoder.encode("par"))), key, VECTOR.id, 6),
    ).rejects.toThrow(/cut off/);

    const streamed = encoder.encode(JSON.stringify({ s: 200, h: { "content-type": "application/x-ndjson" } }));
    const cut = await openAnswer(
      answer(await sealFrame(key, 8, 0, 0, streamed), await sealFrame(key, 8, 1, 1, encoder.encode('{"step":1}\n'))),
      key,
      VECTOR.id,
      8,
    );
    await expect(cut.text()).rejects.toThrow(/cut off/);
  });
});
