import { beforeEach, expect, it, vi } from "vitest";
import { newConversation, sendMessage, stopWaiting } from "./chatStore";

vi.mock("@/lib/auth", () => ({ authHeader: vi.fn().mockResolvedValue(null) }));

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  window.sessionStorage.clear();
});

const saved = (user: string) => JSON.parse(window.sessionStorage.getItem(`kasa.chat.${user}`) ?? "null");

const ndjson = (...lines: object[]) => new Response(lines.map((l) => JSON.stringify(l)).join("\n") + "\n");

it("keeps the question and the streamed answer without any component mounted", async () => {
  const reply = {
    session_id: "s1",
    text: "Ayşe owes you",
    chart: null,
    agent: "house_agent",
    cards: [],
    conversation_id: "c1",
    message_id: 7,
  };
  fetchMock.mockResolvedValue(
    ndjson(
      { type: "conversation", conversation_id: "c1" },
      { type: "agent", agent: "house_agent" },
      { type: "tool", name: "get_house_balances" },
      { type: "tool_done", name: "get_house_balances", status: "ok" },
      { type: "final", reply },
    ),
  );
  await sendMessage("chat-a", "Evde kim kime borçlu?");
  const [url, init] = fetchMock.mock.calls[0];
  expect(String(url)).toMatch(/\/chat\/stream$/);
  expect(JSON.parse(String(init?.body))).toMatchObject({ message: "Evde kim kime borçlu?", file_ids: [], locale: "en" });
  expect(saved("chat-a")).toEqual({
    conversationId: "c1",
    sessionId: "s1",
    messages: [
      { role: "user", text: "Evde kim kime borçlu?", files: [] },
      { id: 7, role: "assistant", text: "Ayşe owes you", chart: null, agent: "house_agent", cards: [] },
    ],
  });
  newConversation("chat-a");
  expect(saved("chat-a")).toEqual({ conversationId: null, sessionId: null, messages: [] });
});

it("only stops waiting when the user asks", async () => {
  fetchMock.mockImplementation(
    (_url, init) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      }),
  );
  const pending = sendMessage("chat-b", "Am I over any budget?");
  await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
  stopWaiting("chat-b");
  await pending;
  expect(saved("chat-b").messages).toEqual([{ role: "user", text: "Am I over any budget?", files: [] }]);
});
