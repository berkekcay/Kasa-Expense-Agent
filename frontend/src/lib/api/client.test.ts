import { beforeEach, describe, expect, it, vi } from "vitest";
import { API_URL, ApiError, request, requestBlob, requestPage } from "./client";

vi.mock("@/lib/auth", () => ({ authHeader: vi.fn().mockResolvedValue(null) }));

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("API error handling", () => {
  it.each([
    ["detail", JSON.stringify({ detail: "Expense not found" }), "Expense not found"],
    ["validation errors", JSON.stringify({ detail: [{ msg: "Required" }, { msg: "Invalid amount" }] }), "Required; Invalid amount"],
    ["non-JSON", "Service unavailable", "503 Service Unavailable"],
    ["missing detail", JSON.stringify({ error: "Unavailable" }), "503 Service Unavailable"],
  ])("uses the expected message for %s", async (_label, body, message) => {
    fetchMock.mockResolvedValue(new Response(body, { status: 503, statusText: "Service Unavailable" }));
    const error = await request("/expenses").catch((error: unknown) => error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, message });
  });

  it.each([request, requestPage, requestBlob])("reports network failures for %s", async (load) => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(load("/expenses")).rejects.toMatchObject({
      status: 0,
      message: `Cannot reach the API at ${API_URL}. Is the backend running?`,
    });
  });

  it("preserves cancellation instead of reporting an API outage", async () => {
    const abort = new DOMException("Aborted", "AbortError");
    fetchMock.mockRejectedValue(abort);
    await expect(request("/expenses")).rejects.toBe(abort);
  });
});
