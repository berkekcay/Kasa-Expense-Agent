// Shared fetch client for the Kasa FastAPI backend. Feature modules in this folder build on it.
// Money arrives as decimal strings ("123.45") plus exact *_minor integers; never use floats for sums.

import { authHeader } from "@/lib/auth";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await send(path, init);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** A list plus the X-Total-Count header (the number of matching rows on the server). */
export type Page<T> = { items: T[]; total: number };

export async function requestPage<T>(path: string, init: RequestInit = {}): Promise<Page<T>> {
  const res = await send(path, init);
  const items = (await res.json()) as T[];
  const header = Number(res.headers.get("X-Total-Count"));
  return { items, total: Number.isFinite(header) && res.headers.has("X-Total-Count") ? header : items.length };
}

async function send(path: string, init: RequestInit): Promise<Response> {
  const headers = new Headers(init.headers);
  const auth = await authHeader();
  if (auth) headers.set(auth[0], auth[1]);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the backend running?`);
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      // non-JSON error body; keep the status text
    }
    throw new ApiError(res.status, message);
  }
  return res;
}

export const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
export const put = (body: unknown): RequestInit => ({ method: "PUT", body: JSON.stringify(body) });
export const patch = (body: unknown): RequestInit => ({ method: "PATCH", body: JSON.stringify(body) });
export const del: RequestInit = { method: "DELETE" };

export function upload(file: File): RequestInit {
  const form = new FormData();
  form.append("file", file);
  return { method: "POST", body: form };
}

export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export type Health = { status: string; agents_enabled: boolean; llm_provider: string; auth: "firebase" | "dev" };
export const health = () => request<Health>("/health");
