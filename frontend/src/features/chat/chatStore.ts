"use client";

// The chat conversation lives here, outside React, so a question keeps running while the
// user looks at another page and the answer is waiting when they come back. Pages stay
// mounted but hidden across navigations, and a hidden page's effects are cleaned up, so a
// request owned by the chat component would be cancelled the moment the user left.
// Messages are also saved in sessionStorage: they survive reloads in this tab and are
// separate per tab and per user. A request in flight does not survive a reload.
//
// Conversations are also saved on the server (GET /chat/conversations): the chat page lists
// them, and opening one loads its messages. sessionStorage only remembers the open one.
//
// A turn is streamed (POST /chat/stream): while it runs, `steps` lists which agent took
// over and which tools ran, so the user sees the work instead of a spinner. Cards under an
// answer (an expense saved, a file import ready) carry their own small state (undone,
// confirmed) in `cardState`.

import { useSyncExternalStore } from "react";
import { type ChartSpec, type ChatCard, type ChatFile, api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { dataChanged } from "@/lib/hooks";
import { getLocale } from "@/lib/i18n";

export type Attachment =
  | { kind: "sheet"; file: ChatFile }
  | { kind: "image"; file: File; name: string };

export type CardState =
  | { status: "busy" }
  | { status: "undone" }
  | { status: "confirmed"; created: number; duplicates: number }
  | { status: "error"; error: string };

export type Message = {
  id?: number; // server id of a saved answer, for card state
  role: "user" | "assistant";
  text: string;
  chart?: ChartSpec | null;
  agent?: string | null;
  cards?: ChatCard[];
  cardState?: Record<number, CardState>;
  files?: { name: string; kind: "sheet" | "image" }[];
};

export type Step = { kind: "agent" | "tool"; name: string; done: boolean; failed?: boolean };

export type ChatState = {
  conversationId: string | null;
  loading: boolean; // opening a saved conversation
  sessionId: string | null;
  messages: Message[];
  busy: boolean;
  startedAt: number | null; // ms timestamp of the question in flight
  steps: Step[];
  error: string | null;
};

const EMPTY: ChatState = {
  conversationId: null,
  loading: false,
  sessionId: null,
  messages: [],
  busy: false,
  startedAt: null,
  steps: [],
  error: null,
};
const states = new Map<string, ChatState>();
const controllers = new Map<string, AbortController>();
const listeners = new Set<() => void>();

const storageKey = (userId: string) => `kasa.chat.${userId}`;

function load(userId: string): ChatState {
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ChatState>;
      if (Array.isArray(parsed.messages)) {
        return {
          ...EMPTY,
          conversationId: parsed.conversationId ?? null,
          sessionId: parsed.sessionId ?? null,
          messages: parsed.messages,
        };
      }
    }
  } catch {
    // storage unavailable or corrupt; start fresh
  }
  return EMPTY;
}

function get(userId: string): ChatState {
  let s = states.get(userId);
  if (!s) {
    s = typeof window === "undefined" ? EMPTY : load(userId);
    states.set(userId, s);
  }
  return s;
}

function set(userId: string, update: (s: ChatState) => ChatState) {
  const next = update(get(userId));
  states.set(userId, next);
  try {
    window.sessionStorage.setItem(
      storageKey(userId),
      JSON.stringify({ conversationId: next.conversationId, sessionId: next.sessionId, messages: next.messages }),
    );
  } catch {
    // storage full or unavailable; the chat still works for this page view
  }
  for (const l of listeners) l();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useChat(userId: string): ChatState {
  return useSyncExternalStore(
    subscribe,
    () => get(userId),
    () => EMPTY,
  );
}

/** True while any question for this user is waiting for an answer (for the nav dot). */
export function useChatBusy(userId: string): boolean {
  return useSyncExternalStore(
    subscribe,
    () => get(userId).busy,
    () => false,
  );
}

function addStep(userId: string, step: Step) {
  set(userId, (s) => {
    const last = s.steps.at(-1);
    if (step.kind === "agent" && last?.kind === "agent" && last.name === step.name) return s;
    return { ...s, steps: [...s.steps.map((x) => (x.kind === "agent" ? { ...x, done: true } : x)), step] };
  });
}

function finishTool(userId: string, name: string, status: string) {
  set(userId, (s) => {
    const steps = [...s.steps];
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i].kind === "tool" && steps[i].name === name && !steps[i].done) {
        steps[i] = { ...steps[i], done: true, failed: status === "error" || status === "rejected" };
        break;
      }
    }
    return { ...s, steps };
  });
}

/** Send a question, with optional attachments. Images are read as receipts; spreadsheets
 *  go to the file agent with the question. */
export async function sendMessage(userId: string, text: string, attachments: Attachment[] = []): Promise<void> {
  const message = text.trim();
  const current = get(userId);
  if ((!message && attachments.length === 0) || current.busy) return;
  const controller = new AbortController();
  controllers.set(userId, controller);
  set(userId, (s) => ({
    ...s,
    messages: [
      ...s.messages,
      {
        role: "user",
        text: message,
        files: attachments.map((a) => ({ kind: a.kind, name: a.kind === "sheet" ? a.file.filename : a.name })),
      },
    ],
    busy: true,
    startedAt: Date.now(),
    // The coordinator reads the question first; the first event only arrives after its
    // model call, so show that step right away.
    steps: [{ kind: "agent", name: "kasa_coordinator", done: false }],
    error: null,
  }));
  try {
    const images = attachments.filter((a) => a.kind === "image");
    for (const image of images) {
      addStep(userId, { kind: "agent", name: "receipt_agent", done: false });
      addStep(userId, { kind: "tool", name: "save_expense", done: false });
      const reply = await api.chatReceipt(image.file, get(userId).conversationId);
      finishTool(userId, "save_expense", "saved");
      set(userId, (s) => ({
        ...s,
        conversationId: reply.conversation_id ?? s.conversationId,
        messages: [
          ...s.messages,
          { id: reply.message_id ?? undefined, role: "assistant", text: reply.text, agent: reply.agent, cards: reply.cards ?? [] },
        ],
      }));
      dataChanged("expenses");
      dataChanged("chats");
    }
    const sheets = attachments.filter((a) => a.kind === "sheet").map((a) => a.file.file_id);
    if (message || sheets.length > 0) {
      const reply = await api.chatStream(
        {
          message: message || (getLocale() === "tr" ? "Bu dosyaya bak." : "Look at this file."),
          session_id: get(userId).sessionId,
          conversation_id: get(userId).conversationId,
          file_ids: sheets,
          locale: getLocale(),
        },
        (event) => {
          if (event.type === "conversation") {
            set(userId, (s) => ({ ...s, conversationId: event.conversation_id }));
            dataChanged("chats");
          } else if (event.type === "agent") addStep(userId, { kind: "agent", name: event.agent, done: false });
          else if (event.type === "tool") addStep(userId, { kind: "tool", name: event.name, done: false });
          else if (event.type === "tool_done") finishTool(userId, event.name, event.status);
        },
        controller.signal,
      );
      set(userId, (s) => ({
        ...s,
        sessionId: reply.session_id,
        conversationId: reply.conversation_id ?? s.conversationId,
        messages: [
          ...s.messages,
          {
            id: reply.message_id ?? undefined,
            role: "assistant",
            text: reply.text,
            chart: reply.chart,
            agent: reply.agent,
            cards: reply.cards ?? [],
          },
        ],
      }));
      dataChanged("chats");
      if (reply.cards?.some((c) => c.kind === "expense" || c.kind === "payment")) dataChanged("expenses");
    }
  } catch (err) {
    const stopped = err instanceof DOMException && err.name === "AbortError";
    set(userId, (s) => ({ ...s, error: stopped ? "stopped" : errorMessage(err) }));
  } finally {
    controllers.delete(userId);
    set(userId, (s) => ({ ...s, busy: false, startedAt: null }));
  }
}

function setCard(userId: string, messageIndex: number, cardIndex: number, state: CardState) {
  set(userId, (s) => ({
    ...s,
    messages: s.messages.map((m, i) =>
      i === messageIndex ? { ...m, cardState: { ...m.cardState, [cardIndex]: state } } : m,
    ),
  }));
  // Remember finished states on the server too, so a reopened conversation shows them.
  const id = get(userId).messages[messageIndex]?.id;
  if (id && (state.status === "undone" || state.status === "confirmed")) {
    api.setCardState(id, cardIndex, state).catch(() => {
      // best effort; the card still shows the state in this tab
    });
  }
}

/** Undo an expense the assistant saved. */
export async function undoExpense(userId: string, messageIndex: number, cardIndex: number, expenseId: number) {
  setCard(userId, messageIndex, cardIndex, { status: "busy" });
  try {
    await api.deleteExpense(expenseId);
    setCard(userId, messageIndex, cardIndex, { status: "undone" });
    dataChanged("expenses");
  } catch (err) {
    setCard(userId, messageIndex, cardIndex, { status: "error", error: errorMessage(err) });
  }
}

/** Confirm a file import: the prepared rows become inbox items. */
export async function confirmImport(userId: string, messageIndex: number, cardIndex: number, draftId: string) {
  setCard(userId, messageIndex, cardIndex, { status: "busy" });
  try {
    const result = await api.confirmChatImport(draftId);
    setCard(userId, messageIndex, cardIndex, { status: "confirmed", ...result });
    dataChanged("inbox");
  } catch (err) {
    setCard(userId, messageIndex, cardIndex, { status: "error", error: errorMessage(err) });
  }
}

export function stopWaiting(userId: string) {
  controllers.get(userId)?.abort();
}

export function dismissError(userId: string) {
  set(userId, (s) => ({ ...s, error: null }));
}

export function newConversation(userId: string) {
  if (get(userId).busy) return;
  set(userId, () => EMPTY);
}

/** Open a saved conversation from the server. */
export async function openConversation(userId: string, conversationId: string) {
  if (get(userId).busy) return;
  set(userId, (s) => ({ ...s, loading: true, error: null }));
  try {
    const detail = await api.getConversation(conversationId);
    set(userId, () => ({
      ...EMPTY,
      conversationId: detail.id,
      messages: detail.messages.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
        chart: m.chart,
        agent: m.agent,
        cards: m.cards,
        files: m.files,
        cardState: Object.fromEntries(Object.entries(m.card_state).map(([k, v]) => [Number(k), v as CardState])),
      })),
    }));
  } catch (err) {
    set(userId, (s) => ({ ...s, loading: false, error: errorMessage(err) }));
  }
}

/** Delete a saved conversation; if it is open, start a new one. */
export async function removeConversation(userId: string, conversationId: string) {
  await api.deleteConversation(conversationId);
  if (get(userId).conversationId === conversationId && !get(userId).busy) set(userId, () => EMPTY);
  dataChanged("chats");
}
