"use client";

import { type FormEvent, useState } from "react";
import { api, type ChartSpec } from "@/lib/api";
import { Button, Card, ErrorText, errorMessage } from "@/components/ui";
import { ChartView } from "./ChartView";

type Message = { role: "user" | "assistant"; text: string; chart?: ChartSpec | null };

const EXAMPLES = [
  "How much did I spend per category?",
  "Show my spending by month as a line chart",
  "Who owes whom in my house?",
];

export function ChatView() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    setMessages((m) => [...m, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    setError(null);
    try {
      const reply = await api.chat(message, sessionId);
      setSessionId(reply.session_id);
      setMessages((m) => [...m, { role: "assistant", text: reply.text, chart: reply.chart }]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  return (
    <Card className="flex min-h-[60vh] flex-col">
      <div className="flex flex-1 flex-col gap-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="flex flex-col items-start gap-2 text-sm">
            <p className="text-muted">Ask about your money. Try:</p>
            {EXAMPLES.map((q) => (
              <button key={q} onClick={() => void send(q)} className="rounded-full border border-border px-3 py-1 hover:bg-foreground/5">
                {q}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-xl px-4 py-2 text-sm whitespace-pre-wrap ${
              m.role === "user" ? "self-end bg-accent text-accent-foreground" : "w-full self-start border border-border"
            }`}
          >
            {m.text}
            {m.chart && <ChartView spec={m.chart} />}
          </div>
        ))}
        {busy && <p className="text-sm text-muted">Kasa is thinking…</p>}
      </div>
      <ErrorText error={error} />
      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. How much did I spend on groceries this month?"
          maxLength={4000}
          className="h-10 flex-1 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent/30"
        />
        <Button type="submit" disabled={busy || !input.trim()} className="h-10">
          Send
        </Button>
      </form>
    </Card>
  );
}
