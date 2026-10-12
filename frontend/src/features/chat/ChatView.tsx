"use client";

import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { api, type ChartSpec } from "@/lib/api";
import { useApi, useElapsed, useHydrated } from "@/lib/hooks";
import { useUserId } from "@/lib/user";
import { Alert, Button, Card, Loading, Spinner, errorMessage } from "@/components/ui";
import { ChartView } from "./ChartView";
import { Markdown } from "./Markdown";

type Message = { role: "user" | "assistant"; text: string; chart?: ChartSpec | null };
type Saved = { sessionId: string | null; messages: Message[] };

const EXAMPLES = [
  "Bu ay kategorilere göre ne kadar harcadım?",
  "Son 6 ayın harcamalarını çizgi grafik olarak göster",
  "Evde kim kime borçlu?",
  "How much did I spend on groceries this month?",
  "Which subscriptions do I pay for?",
  "Am I over any budget?",
];

// The conversation lives in sessionStorage: it survives reloads in this tab and is separate per
// tab and per user.
const storageKey = (userId: string) => `kasa.chat.${userId}`;

function load(userId: string): Saved {
  try {
    const raw = window.sessionStorage.getItem(storageKey(userId));
    if (raw) {
      const parsed = JSON.parse(raw) as Saved;
      if (Array.isArray(parsed.messages)) return parsed;
    }
  } catch {
    // storage unavailable or corrupt; start fresh
  }
  return { sessionId: null, messages: [] };
}

function save(userId: string, value: Saved) {
  try {
    window.sessionStorage.setItem(storageKey(userId), JSON.stringify(value));
  } catch {
    // storage full or unavailable; the chat still works for this page view
  }
}

export function ChatView() {
  const hydrated = useHydrated();
  const userId = useUserId();
  if (!hydrated) {
    return (
      <Card>
        <Loading label="Opening the chat" />
      </Card>
    );
  }
  return <Chat key={userId} userId={userId} />;
}

function Chat({ userId }: { userId: string }) {
  const health = useApi(() => api.health(), []);
  const [state, setState] = useState<Saved>(() => load(userId));
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const elapsed = useElapsed(busy);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const agentsOff = health.data?.agents_enabled === false;

  useEffect(() => {
    save(userId, state);
  }, [userId, state]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [state.messages.length, busy]);

  useEffect(() => () => abort.current?.abort(), []);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setState((s) => ({ ...s, messages: [...s.messages, { role: "user", text: message }] }));
    setInput("");
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    abort.current = controller;
    try {
      const reply = await api.chat(message, state.sessionId, controller.signal);
      setState((s) => ({
        sessionId: reply.session_id,
        messages: [...s.messages, { role: "assistant", text: reply.text, chart: reply.chart }],
      }));
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") setError("Stopped waiting. Ask again when you are ready.");
      else setError(errorMessage(err));
    } finally {
      abort.current = null;
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void send(input);
    }
  }

  return (
    <Card className="flex min-h-[60vh] flex-col">
      {agentsOff && (
        <Alert tone="warning" title="Chat is off" className="mb-4">
          The server has no AI model configured, so Kasa cannot answer right now.
        </Alert>
      )}
      <div className="flex flex-1 flex-col gap-4" role="log" aria-live="polite" aria-relevant="additions">
        {state.messages.length === 0 && (
          <div className="flex flex-col items-start gap-2 text-sm">
            <p className="text-muted">Ask about your money in Turkish or English. Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={busy || agentsOff}
                  onClick={() => void send(q)}
                  className="rounded-full border border-border px-3 py-1.5 text-left hover:bg-foreground/5 disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {state.messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="max-w-[85%] self-end rounded-xl bg-accent px-4 py-2 text-sm whitespace-pre-wrap text-accent-foreground">
              <span className="sr-only">You: </span>
              {m.text}
            </div>
          ) : (
            <div key={i} className="w-full self-start rounded-xl border border-border px-4 py-3 text-sm">
              <span className="sr-only">Kasa: </span>
              <Markdown text={m.text} />
              {m.chart && <ChartView spec={m.chart} />}
            </div>
          ),
        )}
        {busy && (
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted">
            <Spinner />
            <span>
              Kasa is thinking. Answers can take 30 to 120 seconds on the dev server.
              <span aria-hidden className="ml-1 tabular-nums">
                ({elapsed} s)
              </span>
            </span>
            <Button size="sm" variant="ghost" onClick={() => abort.current?.abort()}>
              Stop waiting
            </Button>
          </div>
        )}
        {error && (
          <Alert tone="error" onDismiss={() => setError(null)}>
            {error}
          </Alert>
        )}
        <div ref={bottom} />
      </div>
      <form onSubmit={onSubmit} className="mt-4 flex items-end gap-2">
        <label htmlFor="chat-input" className="sr-only">
          Your question
        </label>
        <textarea
          id="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Ask Kasa something"
          maxLength={4000}
          className="max-h-40 min-h-10 min-w-0 flex-1 resize-y rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
        />
        <Button type="submit" disabled={busy || !input.trim() || agentsOff} className="h-10">
          Send
        </Button>
      </form>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>Enter sends, Shift+Enter adds a line.</span>
        {state.messages.length > 0 && (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setState({ sessionId: null, messages: [] });
              setError(null);
            }}
            className="text-accent hover:underline disabled:opacity-50"
          >
            New conversation
          </button>
        )}
      </div>
    </Card>
  );
}
