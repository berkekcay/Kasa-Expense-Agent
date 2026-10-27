import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { House, HouseInvite } from "@/lib/api";
import { setLocale } from "@/lib/i18n";
import { ToastProvider } from "@/components/Toast";
import { InviteCard } from "./InviteCard";

vi.mock("@/lib/auth", () => ({ authHeader: vi.fn().mockResolvedValue(null) }));
vi.mock("@/lib/user", () => ({ useUserId: () => "invite-test-user" }));

const house: House = { id: 42, name: "Test House", currency: "TRY", created_by: "host", members: [] };
const invite: HouseInvite = {
  id: 1, code: "test-invite", url: "https://kasa.example/invite/test-invite", created_by: "host",
  created_at: "2026-10-27T00:00:00Z", expires_at: "2099-01-01T00:00:00Z", max_uses: 10, uses: 0,
};
const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown) => new Response(JSON.stringify(body));

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  setLocale("en");
});

it("focuses and selects the labelled link after creation, including a replacement link", async () => {
  let links: HouseInvite[] = [];
  fetchMock.mockImplementation(async (_input, init) => {
    if (init?.method === "POST") {
      const next = { ...invite, id: links.length + 1, url: `${invite.url}-${links.length + 1}` };
      links = [next, ...links];
      return json(next);
    }
    return json(links);
  });
  render(<ToastProvider><InviteCard house={house} /></ToastProvider>);
  await screen.findByText("No active links yet. Create one and send it to your flatmates.");
  fireEvent.click(screen.getByRole("button", { name: "Create invite link" }));
  const field = await screen.findByRole("textbox", { name: "Invite link" });
  await waitFor(() => expect(field).toHaveFocus());
  expect(field).toHaveValue(`${invite.url}-1`);
  expect(field).toHaveAccessibleDescription(/for up to 10 people/);
  expect((field as HTMLInputElement).selectionEnd).toBe(`${invite.url}-1`.length);
  fireEvent.click(screen.getByRole("button", { name: "New link" }));
  await waitFor(() => expect(screen.getByRole("textbox", { name: "Invite link" })).toHaveValue(`${invite.url}-2`));
  expect(screen.getByRole("textbox", { name: "Invite link" })).toHaveFocus();
});

it.each([true, false])("announces clipboard success=%s and offers manual copying on failure", async (success) => {
  fetchMock.mockResolvedValue(json([invite]));
  const writeText = success ? vi.fn().mockResolvedValue(undefined) : vi.fn().mockRejectedValue(new Error("Denied"));
  vi.stubGlobal("navigator", { clipboard: { writeText } });
  render(<ToastProvider><InviteCard house={house} /></ToastProvider>);
  const field = await screen.findByRole("textbox", { name: "Invite link" });
  expect(screen.getByRole("button", { name: "Cancel invite link test-invite" })).toBeInTheDocument();
  const copy = screen.getByRole("button", { name: "Copy" });
  copy.focus();
  fireEvent.click(copy);
  expect(await screen.findByRole("status")).toHaveTextContent(success
    ? "Link copied." : "Could not copy. Select the link and copy it by hand.");
  expect(writeText).toHaveBeenCalledWith(invite.url);
  if (!success) {
    expect(field).toHaveFocus();
    expect((field as HTMLInputElement).selectionEnd).toBe(invite.url.length);
  }
});
