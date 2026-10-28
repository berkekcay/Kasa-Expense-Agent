import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { InvitePreview } from "@/lib/api";
import { setLocale } from "@/lib/i18n";
import { InviteView } from "./InviteView";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));
vi.mock("@/lib/auth", () => ({ authHeader: vi.fn().mockResolvedValue(null), onUnauthorized: vi.fn() }));
vi.mock("@/lib/user", () => ({ useUserId: () => "invite-test-user" }));

const code = "test-invite";
const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const preview: InvitePreview = {
  code, house_name: "Test House", invited_by: "Test Host", expires_at: "2099-01-01T00:00:00Z",
  usable: true, reason: null, message: null, already_member: false, house_id: null,
};

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setLocale("en");
});

describe("InviteView", () => {
  it("shows the house and inviter, accepts the invite with POST, and opens houses", async () => {
    fetchMock.mockImplementation(async (input, init) => {
      const path = new URL(String(input)).pathname;
      if (path === `/invites/${code}`) return json(preview);
      if (path === `/invites/${code}/accept` && init?.method === "POST") {
        return json({ id: 42, name: "Test House", currency: "TRY", created_by: "host", members: [] });
      }
      throw new Error(`Unexpected request: ${init?.method ?? "GET"} ${path}`);
    });
    render(<InviteView code={code} />);
    expect(await screen.findByRole("heading", { name: "Test House" })).toBeInTheDocument();
    expect(screen.getByText("Invited by Test Host")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Join the house" }));
    await waitFor(() => expect(router.push).toHaveBeenCalledWith("/houses"));
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining(`/invites/${code}/accept`),
      expect.objectContaining({ method: "POST" }));
  });

  it.each([
    ["revoked", "This link was cancelled. Ask your flatmate for a new one."],
    ["expired", "This link has expired. Ask your flatmate for a new one."],
    ["used_up", "This link has been used as many times as allowed. Ask your flatmate for a new one."],
  ] as const)("shows why a %s link cannot be used", async (reason, message) => {
    fetchMock.mockResolvedValue(json({ ...preview, usable: false, reason }));
    render(<InviteView code={code} />);
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Join the house" })).not.toBeInTheDocument();
    expect(router.push).not.toHaveBeenCalled();
  });

  it.each(["preview", "accept"])("redirects a 401 from %s to login with the invite return path", async (stage) => {
    fetchMock.mockImplementation(async (input) => {
      const path = new URL(String(input)).pathname;
      return stage === "accept" && path === `/invites/${code}`
        ? json(preview) : json({ detail: "Sign in required" }, 401);
    });
    render(<InviteView code={code} />);
    if (stage === "accept") fireEvent.click(await screen.findByRole("button", { name: "Join the house" }));
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/login?next=%2Finvite%2Ftest-invite"));
    expect(router.push).not.toHaveBeenCalled();
  });
});
