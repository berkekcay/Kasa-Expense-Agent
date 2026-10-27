"use client";

import { History, MessageSquareText, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useApi, useDataVersion } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { newConversation, openConversation, removeConversation } from "./chatStore";
import { messages } from "./messages";

/** Saved conversations: a column beside the chat on wide screens, a fold-out list on phones. */
export function ConversationList({ userId, current, busy }: { userId: string; current: string | null; busy: boolean }) {
  const t = useT(messages);
  const version = useDataVersion("chats");
  const list = useApi(() => api.listConversations(), [version]);
  const [confirming, setConfirming] = useState<string | null>(null);
  const items = list.data ?? [];

  const body = (
    <div className="flex min-h-0 flex-col gap-2">
      <button
        type="button"
        disabled={busy}
        onClick={() => newConversation(userId)}
        className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-border bg-card text-sm font-medium shadow-card hover:bg-card-hover disabled:opacity-50"
      >
        <Plus aria-hidden className="size-4" /> {t("newConversation")}
      </button>
      {list.data !== null && items.length === 0 && <p className="px-1 py-2 text-xs text-muted">{t("noHistory")}</p>}
      <ul className="flex max-h-[60vh] flex-col gap-0.5 overflow-y-auto">
        {items.map((c) => {
          const active = c.id === current;
          return (
            <li key={c.id} className="group relative">
              <button
                type="button"
                disabled={busy}
                aria-current={active ? "true" : undefined}
                onClick={() => void openConversation(userId, c.id)}
                className={`flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 pr-9 text-left text-sm transition disabled:opacity-60 ${
                  active ? "bg-accent-soft text-accent" : "hover:bg-foreground/5"
                }`}
              >
                <MessageSquareText aria-hidden className="mt-0.5 size-4 shrink-0 opacity-70" />
                <span className="min-w-0">
                  <span className={`block truncate ${active ? "font-medium" : ""}`}>{c.title}</span>
                  <span className="block text-xs text-muted">{formatDateTime(c.updated_at)}</span>
                </span>
              </button>
              {confirming === c.id ? (
                <span className="absolute inset-y-1 right-1 flex items-center gap-1 rounded-md bg-card px-1 shadow-card">
                  <button
                    type="button"
                    onClick={() => {
                      setConfirming(null);
                      void removeConversation(userId, c.id);
                    }}
                    className="rounded px-1.5 py-0.5 text-xs font-medium text-danger hover:bg-danger/10"
                  >
                    {t("deleteChat")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(null)}
                    className="rounded px-1.5 py-0.5 text-xs text-muted hover:bg-foreground/5"
                  >
                    {t("keep")}
                  </button>
                </span>
              ) : (
                <button
                  type="button"
                  aria-label={t("deleteNamed", { title: c.title })}
                  onClick={() => setConfirming(c.id)}
                  className="absolute top-1/2 right-1.5 inline-flex size-7 -translate-y-1/2 items-center justify-center rounded-md text-muted opacity-0 transition group-hover:opacity-100 hover:bg-foreground/5 hover:text-danger focus-visible:opacity-100"
                >
                  <Trash2 className="size-3.5" />
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );

  return (
    <>
      <aside aria-label={t("history")} className="hidden lg:block">
        <div className="sticky top-6 rounded-2xl border border-border bg-card p-3 shadow-card">
          <p className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold tracking-wider text-muted uppercase">
            <History aria-hidden className="size-3.5" /> {t("history")}
          </p>
          {body}
        </div>
      </aside>
      <details className="rounded-2xl border border-border bg-card p-3 shadow-card lg:hidden">
        <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium">
          <History aria-hidden className="size-4 text-muted" /> {t("history")}
          {items.length > 0 && <span className="text-xs text-muted">({items.length})</span>}
        </summary>
        <div className="mt-3">{body}</div>
      </details>
    </>
  );
}
