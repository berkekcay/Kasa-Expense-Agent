import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSession } from "@/lib/auth";
import { resetAuthModeForTests } from "@/lib/authMode";
import { LoginView } from "./LoginView";
import { safeNext } from "./parts";

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }));
const search = vi.hoisted(() => ({ value: "next=/expenses" }));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(search.value),
  usePathname: () => "/login",
}));

const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

const user = {
  user_id: "acct-1",
  display_name: "Test Person",
  email: "person@example.com",
  login_email: "person@example.com",
  has_password: true,
  google_linked: false,
  totp_enabled: true,
  kind: "account",
};

function routes(overrides: Record<string, () => Response> = {}) {
  fetchMock.mockImplementation(async (input) => {
    const path = new URL(String(input)).pathname;
    if (overrides[path]) return overrides[path]();
    if (path === "/health") {
      return json({ status: "ok", agents_enabled: false, llm_provider: "", auth: "accounts", google_login: true });
    }
    if (path === "/auth/login") return json({ pending_token: "pending-1", step: "totp" });
    if (path === "/auth/login/verify") return json({ token: "ks_test_token", expires_at: "2099-01-01T00:00:00Z", user });
    return json({ detail: "not found" }, 404);
  });
}

function bodyOf(path: string): unknown {
  const call = fetchMock.mock.calls.find(([input]) => new URL(String(input)).pathname === path);
  return call ? JSON.parse(String(call[1]?.body)) : undefined;
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.localStorage.clear();
  resetAuthModeForTests();
  search.value = "next=/expenses";
});

describe("LoginView", () => {
  it("signs in with password and an authenticator code, stores the session and goes to next", async () => {
    routes();
    render(<LoginView />);

    expect(await screen.findByRole("button", { name: "Continue with Google" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: " person@example.com " } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    const code = await screen.findByLabelText("Verification code");
    expect(code).toHaveAttribute("inputmode", "numeric");
    expect(code).toHaveAttribute("autocomplete", "one-time-code");
    await waitFor(() => expect(code).toHaveFocus());
    expect(bodyOf("/auth/login")).toEqual({ email: "person@example.com", password: "correct horse battery" });

    // Six digits submit on their own; spaces from a paste are dropped.
    fireEvent.change(code, { target: { value: "123 456" } });

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/expenses"));
    expect(bodyOf("/auth/login/verify")).toEqual({ pending_token: "pending-1", code: "123456" });
    expect(getSession()).toMatchObject({ token: "ks_test_token", userId: "acct-1" });
    expect(JSON.parse(window.localStorage.getItem("kasa.session") ?? "{}")).toMatchObject({
      token: "ks_test_token",
      userId: "acct-1",
    });
  });

  it("shows a wrong password message and stays on the form", async () => {
    routes({ "/auth/login": () => json({ detail: "Wrong email or password" }, 401) });
    render(<LoginView />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "not the password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password.");
    expect(screen.queryByLabelText("Verification code")).not.toBeInTheDocument();
    expect(getSession()).toBeNull();
  });

  it("can verify with a recovery code instead", async () => {
    routes();
    search.value = "";
    render(<LoginView />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct horse battery" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.click(await screen.findByRole("button", { name: "Use a recovery code instead" }));
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: " abcd-efgh " } });
    fireEvent.click(screen.getByRole("button", { name: "Verify" }));

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(bodyOf("/auth/login/verify")).toEqual({ pending_token: "pending-1", recovery_code: "abcd-efgh" });
  });
});

describe("safeNext", () => {
  it.each([
    ["/expenses?month=2026-10", "/expenses?month=2026-10"],
    ["/invite/abc", "/invite/abc"],
    [null, "/"],
    ["https://evil.example", "/"],
    ["//evil.example/x", "/"],
    ["/\\evil.example", "/"],
    ["javascript:alert(1)", "/"],
    ["/login?next=/x", "/"],
    ["/register", "/"],
  ])("%s -> %s", (raw, expected) => {
    expect(safeNext(raw)).toBe(expected);
  });
});
