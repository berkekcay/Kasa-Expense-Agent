// Encrypted API channel: every call goes to POST /secure/tunnel as an AES-GCM envelope, so the
// network tab, proxies and access logs see one opaque endpoint instead of URLs, the session
// token and bodies. Protocol and reasoning: backend/app/secure_channel.py. WebCrypto only.
//
// One channel per tab, made on the first call: a fresh ECDH P-256 key pair (private key not
// extractable), HKDF-SHA256 over a transcript of the handshake, AES-256-GCM. The server sends
// 412 + x-kasa-channel: reset when it forgot the channel (e.g. it restarted); we shake hands
// again and retry the call once. A server with the channel off answers the handshake with 404
// and we send plain calls from then on.

const VERSION = "kasa-secure-v1";
const META = 0;
const DATA_GZIP = 2;
const END = 3;
const NULL_BODY = new Set([101, 204, 205, 304]);
const RESET = Symbol("reset");

const encoder = new TextEncoder();
const decoder = new TextDecoder();

type Channel = { id: string; key: CryptoKey; seq: number };

let channel: Promise<Channel | null> | null = null;

export function b64(data: ArrayBuffer | Uint8Array): string {
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  let text = "";
  for (const b of bytes) text += String.fromCharCode(b);
  return btoa(text);
}

export function unb64(text: string): Uint8Array<ArrayBuffer> {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
}

function concat(...parts: Uint8Array[]): Uint8Array<ArrayBuffer> {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) {
    out.set(p, at);
    at += p.length;
  }
  return out;
}

export function transcript(id: string, client: string, server: string, nonce: string, ts: number, exp: number): string {
  return `${VERSION}|${id}|${client}|${server}|${nonce}|${ts}|${exp}`;
}

/** HKDF-SHA256(shared, salt = SHA-256(transcript), info = "kasa-secure-v1|id") -> AES-256-GCM. */
export async function deriveKey(
  shared: ArrayBuffer | Uint8Array<ArrayBuffer>,
  text: string,
  id: string,
  extractable = false,
): Promise<CryptoKey> {
  const salt = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  const base = await crypto.subtle.importKey("raw", shared, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt, info: encoder.encode(`${VERSION}|${id}`) },
    base,
    { name: "AES-GCM", length: 256 },
    extractable,
    ["encrypt", "decrypt"],
  );
}

export const requestAad = (id: string, seq: number) => encoder.encode(`kasa-v1|req|${id}|${seq}`);
export const responseAad = (id: string, seq: number, index: number) => encoder.encode(`kasa-v1|res|${id}|${seq}|${index}`);

async function handshake(base: string): Promise<Channel | null> {
  const pair = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]);
  const client = b64(await crypto.subtle.exportKey("spki", pair.publicKey));
  const nonce = b64(crypto.getRandomValues(new Uint8Array(16)));
  const ts = Date.now();
  const res = await fetch(`${base}/secure/handshake`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client, nonce, ts }),
  });
  if (res.status === 404) return null; // the server has the channel off
  if (!res.ok) throw new Error(`secure handshake failed (${res.status})`);
  const out = (await res.json()) as { id: string; server: string; exp: number };
  const server = await crypto.subtle.importKey("spki", unb64(out.server), { name: "ECDH", namedCurve: "P-256" }, false, []);
  const shared = await crypto.subtle.deriveBits({ name: "ECDH", public: server }, pair.privateKey, 256);
  const key = await deriveKey(shared, transcript(out.id, client, out.server, nonce, ts, out.exp), out.id);
  return { id: out.id, key, seq: 0 };
}

function getChannel(base: string): Promise<Channel | null> {
  channel ??= handshake(base).catch((err: unknown) => {
    channel = null; // try again on the next call
    throw err;
  });
  return channel;
}

/** Forget the channel (tests, sign-out). */
export function resetChannel() {
  channel = null;
}

/** `fetch(base + path, init)`, through the encrypted channel when the server has it on. */
export async function secureFetch(base: string, path: string, init: RequestInit = {}): Promise<Response> {
  // Off in unit tests (their fetch mocks know nothing of the handshake), and without WebCrypto
  // (a page served over plain http from another machine is not a secure context).
  if (process.env.NEXT_PUBLIC_SECURE_CHANNEL === "off" || !globalThis.crypto?.subtle) {
    return fetch(`${base}${path}`, init);
  }
  for (let attempt = 0; attempt < 2; attempt++) {
    const ch = await getChannel(base);
    if (!ch) return fetch(`${base}${path}`, init);
    const res = await tunnel(base, ch, path, init);
    if (res !== RESET) return res;
    channel = null;
  }
  throw new Error("the secure channel could not be set up");
}

async function tunnel(base: string, ch: Channel, path: string, init: RequestInit): Promise<Response | typeof RESET> {
  const seq = ++ch.seq;
  const method = (init.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {};
  new Headers(init.headers).forEach((value, name) => {
    headers[name] = value;
  });
  let body = new Uint8Array(0);
  if (init.body != null) {
    // Request serialises any body (a JSON string, FormData with files) and, for FormData,
    // names the multipart boundary in its content type.
    const probe = new Request("http://kasa.invalid/", { method: "POST", body: init.body });
    body = new Uint8Array(await probe.arrayBuffer());
    if (!headers["content-type"]) headers["content-type"] = probe.headers.get("content-type") ?? "application/octet-stream";
  }
  const meta = encoder.encode(JSON.stringify({ m: method, p: path, h: headers, t: Date.now() }) + "\n");
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const sealed = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: requestAad(ch.id, seq) },
    ch.key,
    concat(meta, body),
  );
  const res = await fetch(`${base}/secure/tunnel`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream", "x-kasa-channel": ch.id, "x-kasa-seq": String(seq) },
    body: concat(iv, new Uint8Array(sealed)),
    signal: init.signal,
  });
  if (res.status === 412 && res.headers.get("x-kasa-channel") === "reset") return RESET;
  if (!res.ok) return res; // a channel error (400, 409, 413, 429): plain JSON with a detail
  return openAnswer(res, ch.key, ch.id, seq);
}

async function gunzip(data: Uint8Array<ArrayBuffer>): Promise<Uint8Array<ArrayBuffer>> {
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("gzip"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** Turn the framed, encrypted answer back into the Response the route gave. Resolves when the
 * head frame arrives; the body streams frame by frame (the chat's live steps keep working). */
export async function openAnswer(res: Response, key: CryptoKey, id: string, seq: number): Promise<Response> {
  const reader = res.body!.getReader();
  let buffer = new Uint8Array(0);
  let index = 0;

  async function next(): Promise<{ kind: number; payload: Uint8Array<ArrayBuffer> } | null> {
    for (;;) {
      if (buffer.length >= 4) {
        const length = new DataView(buffer.buffer, buffer.byteOffset, 4).getUint32(0);
        if (buffer.length >= 4 + length) {
          const sealed = buffer.slice(4, 4 + length);
          buffer = buffer.slice(4 + length);
          const plain = new Uint8Array(
            await crypto.subtle.decrypt(
              { name: "AES-GCM", iv: sealed.slice(0, 12), additionalData: responseAad(id, seq, index++) },
              key,
              sealed.slice(12),
            ),
          );
          return { kind: plain[0], payload: plain.slice(1) };
        }
      }
      const { done, value } = await reader.read();
      if (done) return null;
      buffer = concat(buffer, value);
    }
  }

  const head = await next();
  if (!head || head.kind !== META) throw new Error("the secure answer had no head");
  const meta = JSON.parse(decoder.decode(head.payload)) as { s: number; h: Record<string, string> };
  const piece = async (part: { kind: number; payload: Uint8Array<ArrayBuffer> }) =>
    part.kind === DATA_GZIP ? gunzip(part.payload) : part.payload;
  if (!(meta.h["content-type"] ?? "").includes("ndjson")) {
    // A whole answer: read it to the end now, so a cut-off answer fails here and the browser
    // sees the network response finished.
    const parts: Uint8Array[] = [];
    for (let part = await next(); part?.kind !== END; part = await next()) {
      if (!part) throw new Error("the secure answer was cut off");
      parts.push(await piece(part));
    }
    while (!(await reader.read()).done);
    return new Response(NULL_BODY.has(meta.s) ? null : concat(...parts), { status: meta.s, headers: meta.h });
  }
  const body = new ReadableStream<Uint8Array>({
    async pull(controller) {
      const part = await next();
      if (!part) controller.error(new Error("the secure answer was cut off"));
      else if (part.kind === END) {
        // Read the network stream to its end too, so the browser does not report it aborted.
        while (!(await reader.read()).done);
        controller.close();
      }
      else controller.enqueue(await piece(part));
    },
    cancel(reason) {
      return reader.cancel(reason);
    },
  });
  return new Response(NULL_BODY.has(meta.s) ? null : body, { status: meta.s, headers: meta.h });
}
