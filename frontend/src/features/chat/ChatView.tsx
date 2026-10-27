"use client";

import {
  ArrowRight,
  ArrowUp,
  BarChart3,
  Check,
  Coffee,
  FileSpreadsheet,
  Home,
  ImageIcon,
  Inbox,
  Loader2,
  Paperclip,
  PiggyBank,
  ShoppingBasket,
  SquarePen,
  Undo2,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { type DragEvent, type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";
import { Logo } from "@/components/Logo";
import { Alert, Badge, Loading, Money, PageHeader } from "@/components/ui";
import { type ChatCard, api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatDate } from "@/lib/format";
import { useApi, useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUserId } from "@/lib/user";
import { ChartView } from "./ChartView";
import { ConversationList } from "./ConversationList";
import { Markdown } from "./Markdown";
import {
  type Attachment,
  type CardState,
  type Step,
  confirmImport,
  dismissError,
  newConversation,
  sendMessage,
  stopWaiting,
  undoExpense,
  useChat,
} from "./chatStore";
import { messages } from "./messages";

type T = ReturnType<typeof useT<(typeof messages)["en"]>>;

const EXAMPLES = [
  { key: "ex1", icon: BarChart3 },
  { key: "ex2", icon: Wallet },
  { key: "ex3", icon: Home },
  { key: "ex4", icon: ShoppingBasket },
  { key: "ex5", icon: Coffee },
  { key: "ex6", icon: PiggyBank },
] as const;

const SHEET = /\.(xlsx|xlsm|csv|txt)$/i;

export function ChatHeader() {
  const t = useT(messages);
  return <PageHeader title={t("title")} subtitle={t("subtitle")} />;
}

export function ChatView() {
  const t = useT(messages);
  const hydrated = useHydrated();
  const userId = useUserId();
  if (!hydrated) {
    return (
      <section className="rounded-2xl border border-border bg-card p-6 shadow-card">
        <Loading label={t("opening")} />
      </section>
    );
  }
  return <Chat userId={userId} />;
}

/** Seconds since `startedAt`, ticking while it is set. */
function useSince(startedAt: number | null): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (startedAt === null) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [startedAt]);
  return startedAt === null ? 0 : Math.max(0, Math.floor((now - startedAt) / 1000));
}

function agentName(t: T, agent: string | null | undefined): string | null {
  if (!agent) return null;
  const key = `agent.${agent}` as Parameters<T>[0];
  return key in messages.en ? t(key) : null;
}

function toolName(t: T, tool: string): string {
  if (tool.startsWith("add_house_expense")) return t("tool.add_house_expense");
  const key = `tool.${tool}` as Parameters<T>[0];
  return key in messages.en ? t(key) : t("tool");
}

function Chat({ userId }: { userId: string }) {
  const t = useT(messages);
  const health = useApi(() => api.health(), []);
  const chat = useChat(userId);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const elapsed = useSince(chat.startedAt);
  const bottom = useRef<HTMLDivElement | null>(null);
  const field = useRef<HTMLTextAreaElement | null>(null);
  const picker = useRef<HTMLInputElement | null>(null);
  const agentsOff = health.data?.agents_enabled === false;

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [chat.messages.length, chat.busy, chat.steps.length]);

  // Grow the box with its text, up to about six lines.
  useEffect(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 168)}px`;
  }, [input]);

  async function attach(files: FileList | File[]) {
    setFileError(null);
    for (const file of Array.from(files).slice(0, 5)) {
      if (file.type.startsWith("image/")) {
        setAttachments((a) => [...a, { kind: "image", file, name: file.name }]);
      } else if (SHEET.test(file.name) || file.type.includes("sheet") || file.type.includes("csv")) {
        setUploading(file.name);
        try {
          const uploaded = await api.uploadChatFile(file);
          setAttachments((a) => [...a, { kind: "sheet", file: uploaded }]);
        } catch (err) {
          setFileError(errorMessage(err));
        } finally {
          setUploading(null);
        }
      } else {
        setFileError(t("unsupported"));
      }
    }
    field.current?.focus();
  }

  function send(text: string) {
    if ((!text.trim() && attachments.length === 0) || chat.busy || uploading) return;
    const files = attachments;
    setInput("");
    setAttachments([]);
    void sendMessage(userId, text, files);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    send(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send(input);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) void attach(e.dataTransfer.files);
  }

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
    <ConversationList userId={userId} current={chat.conversationId} busy={chat.busy} />
    <section
      className="relative flex min-h-[calc(100dvh-14rem)] min-w-0 flex-col rounded-2xl border border-border bg-card shadow-card"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={onDrop}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-2 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-accent bg-accent-soft/80 text-sm font-medium text-accent">
          {t("dropHere")}
        </div>
      )}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 sm:px-6">
        <p className="flex items-center gap-2 text-sm text-muted">
          <span aria-hidden className={`size-2 rounded-full ${agentsOff ? "bg-[var(--status-warning)]" : "bg-[var(--status-good)]"}`} />
          {agentsOff ? t("modelOff") : t("privacy")}
        </p>
        {chat.messages.length > 0 && (
          <button
            type="button"
            disabled={chat.busy}
            onClick={() => newConversation(userId)}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg px-2.5 text-sm text-muted hover:bg-foreground/5 hover:text-foreground disabled:opacity-40"
          >
            <SquarePen aria-hidden className="size-4" /> {t("newConversation")}
          </button>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-5 px-4 py-5 sm:px-6" role="log" aria-live="polite" aria-relevant="additions">
        {agentsOff && (
          <Alert tone="warning" title={t("chatOff")}>
            {t("chatOffBody")}
          </Alert>
        )}
        {chat.loading && <Loading label={t("loadingChat")} />}
        {!chat.loading && chat.messages.length === 0 && (
          <div className="m-auto flex w-full max-w-2xl flex-col items-center gap-6 py-6 text-center">
            <Logo className="size-12" />
            <div>
              <p className="text-lg font-semibold">{t("emptyTitle")}</p>
              <p className="mt-1 text-sm text-muted">{t("emptyBody")}</p>
            </div>
            <div className="grid w-full gap-2 sm:grid-cols-2">
              {EXAMPLES.map((q) => {
                const Icon = q.icon;
                return (
                  <button
                    key={q.key}
                    type="button"
                    disabled={chat.busy || agentsOff}
                    onClick={() => send(t(q.key))}
                    className="flex items-center gap-3 rounded-xl border border-border px-3.5 py-3 text-left text-sm transition hover:border-border-strong hover:bg-card-hover disabled:opacity-50"
                  >
                    <Icon aria-hidden className="size-4 shrink-0 text-muted" />
                    {t(q.key)}
                  </button>
                );
              })}
            </div>
          </div>
        )}
        {chat.messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex max-w-[85%] flex-col items-end gap-1.5 self-end">
              {m.files && m.files.length > 0 && (
                <div className="flex flex-wrap justify-end gap-1.5">
                  {m.files.map((f, k) => (
                    <FileChip key={k} name={f.name} kind={f.kind} />
                  ))}
                </div>
              )}
              {m.text && (
                <div className="rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm whitespace-pre-wrap text-accent-foreground">
                  <span className="sr-only">{t("you")}: </span>
                  {m.text}
                </div>
              )}
            </div>
          ) : (
            <div key={i} className="flex w-full gap-3 self-start">
              <Logo className="mt-5 size-7 shrink-0" />
              <div className="min-w-0 flex-1 text-sm">
                <p className="mb-1 flex items-center gap-2 text-xs text-muted">
                  <span className="font-medium text-foreground">{t("kasa")}</span>
                  {agentName(t, m.agent) && m.agent !== "kasa_coordinator" && <Badge>{agentName(t, m.agent)}</Badge>}
                </p>
                <span className="sr-only">{t("kasa")}: </span>
                <div className="rounded-2xl rounded-tl-md bg-foreground/[0.04] px-4 py-3">
                  {m.text && <Markdown text={m.text} />}
                  {m.chart && <ChartView spec={m.chart} />}
                  {m.cards?.map((card, k) => (
                    <CardView
                      key={k}
                      card={card}
                      state={m.cardState?.[k]}
                      onUndo={(id) => void undoExpense(userId, i, k, id)}
                      onConfirm={(id) => void confirmImport(userId, i, k, id)}
                    />
                  ))}
                </div>
              </div>
            </div>
          ),
        )}
        {chat.busy && (
          <div className="flex gap-3">
            <Logo className="mt-1 size-7 shrink-0" />
            <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md bg-foreground/[0.04] px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-3 text-muted">
                <Loader2 aria-hidden className="size-4 animate-spin text-accent motion-reduce:animate-none" />
                <span className="font-medium text-foreground">{t("thinking")}</span>
                <span className="tabular-nums">{t("seconds", { n: elapsed })}</span>
                <button
                  type="button"
                  onClick={() => stopWaiting(userId)}
                  className="ml-auto rounded-md px-2 py-0.5 text-xs font-medium text-foreground hover:bg-foreground/5"
                >
                  {t("stop")}
                </button>
              </div>
              <StepList steps={chat.steps} />
              <p className="mt-2 text-xs text-muted">{t("canLeave")}</p>
            </div>
          </div>
        )}
        {chat.error && (
          <Alert tone="error" onDismiss={() => dismissError(userId)}>
            {chat.error === "stopped" ? t("stopped") : chat.error}
          </Alert>
        )}
        <div ref={bottom} />
      </div>

      <form onSubmit={onSubmit} className="sticky bottom-0 rounded-b-2xl border-t border-border bg-card p-3 sm:p-4">
        {(attachments.length > 0 || uploading || fileError) && (
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            {attachments.map((a, k) => (
              <FileChip
                key={k}
                name={a.kind === "sheet" ? a.file.filename : a.name}
                kind={a.kind}
                detail={a.kind === "sheet" ? t("rows", { n: a.file.sheets.reduce((s, x) => s + x.rows, 0) }) : undefined}
                removeLabel={t("removeFile", { name: a.kind === "sheet" ? a.file.filename : a.name })}
                onRemove={() => setAttachments((list) => list.filter((_, j) => j !== k))}
              />
            ))}
            {uploading && (
              <span className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-xs text-muted">
                <Loader2 aria-hidden className="size-3.5 animate-spin" /> {t("uploading", { name: uploading })}
              </span>
            )}
            {fileError && <span className="text-xs text-danger">{fileError}</span>}
          </div>
        )}
        <div className="flex items-end gap-2 rounded-xl border border-border bg-background p-1.5 transition focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/25">
          <input
            ref={picker}
            type="file"
            hidden
            multiple
            accept=".xlsx,.xlsm,.csv,image/*"
            onChange={(e) => {
              if (e.target.files) void attach(e.target.files);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            title={t("attach")}
            aria-label={t("attach")}
            disabled={chat.busy || agentsOff}
            onClick={() => picker.current?.click()}
            className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg text-muted transition hover:bg-foreground/5 hover:text-foreground disabled:opacity-40"
          >
            <Paperclip className="size-4" />
          </button>
          <label htmlFor="chat-input" className="sr-only">
            {t("yourQuestion")}
          </label>
          <textarea
            id="chat-input"
            ref={field}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={attachments.some((a) => a.kind === "sheet") ? t("placeholderFile") : t("placeholder")}
            maxLength={4000}
            className="max-h-42 min-h-9 min-w-0 flex-1 resize-none bg-transparent py-2 text-sm outline-none focus-visible:outline-none"
          />
          <button
            type="submit"
            aria-label={t("send")}
            disabled={chat.busy || Boolean(uploading) || (!input.trim() && attachments.length === 0) || agentsOff}
            className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground transition hover:brightness-110 disabled:opacity-40"
          >
            <ArrowUp className="size-4" />
          </button>
        </div>
        <p className="mt-2 px-1 text-xs text-muted">{t("hint")}</p>
      </form>
    </section>
    </div>
  );
}

function FileChip({
  name,
  kind,
  detail,
  removeLabel,
  onRemove,
}: {
  name: string;
  kind: "sheet" | "image";
  detail?: string;
  removeLabel?: string;
  onRemove?: () => void;
}) {
  const Icon = kind === "sheet" ? FileSpreadsheet : ImageIcon;
  return (
    <span className="inline-flex max-w-64 items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-xs">
      <Icon aria-hidden className={`size-3.5 shrink-0 ${kind === "sheet" ? "text-positive" : "text-muted"}`} />
      <span className="truncate font-medium">{name}</span>
      {detail && <span className="shrink-0 text-muted">{detail}</span>}
      {onRemove && (
        <button
          type="button"
          aria-label={removeLabel}
          onClick={onRemove}
          className="-mr-1 inline-flex size-5 items-center justify-center rounded text-muted hover:bg-foreground/5 hover:text-foreground"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  );
}

/** What the agents did so far in this turn: who took over, which tools ran. */
function StepList({ steps }: { steps: Step[] }) {
  const t = useT(messages);
  const visible = steps;
  if (visible.length === 0) return null;
  return (
    <ol className="mt-3 flex flex-col gap-1.5 border-l border-border pl-3">
      {visible.map((s, k) => (
        <li key={k} className="flex items-center gap-2 text-xs">
          {s.done ? (
            <Check aria-hidden className={`size-3.5 ${s.failed ? "text-warning" : "text-positive"}`} />
          ) : (
            <Loader2 aria-hidden className="size-3.5 animate-spin text-accent motion-reduce:animate-none" />
          )}
          <span className={s.done ? "text-muted" : "text-foreground"}>
            {s.kind === "agent" && s.name === "kasa_coordinator"
              ? t("reading")
              : s.kind === "agent"
                ? t("routed", { agent: agentName(t, s.name) ?? s.name })
                : toolName(t, s.name)}
          </span>
        </li>
      ))}
    </ol>
  );
}

function CardView({
  card,
  state,
  onUndo,
  onConfirm,
}: {
  card: ChatCard;
  state?: CardState;
  onUndo: (expenseId: number) => void;
  onConfirm: (draftId: string) => void;
}) {
  const t = useT(messages);
  const busy = state?.status === "busy";
  const box = "mt-3 rounded-xl border border-border bg-card p-3.5";
  if (card.kind === "expense") {
    const d = card.data;
    if (state?.status === "undone") return <p className={`${box} text-muted`}>{t("undone")}</p>;
    return (
      <div className={`${box} flex flex-wrap items-center gap-3`}>
        <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-positive/10 text-positive">
          <Check className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs text-muted">{d.house ? t("savedHouse") : t("saved")}</span>
          <span className="block truncate font-medium">{d.merchant}</span>
          {d.date && <span className="block text-xs text-muted">{formatDate(d.date)}</span>}
        </span>
        <Money amount={d.total} currency={d.currency} className="font-semibold tabular-nums" />
        <span className="flex w-full flex-wrap gap-2 sm:w-auto">
          {d.house ? (
            <Link href="/houses" className="inline-flex h-8 items-center gap-1 rounded-lg px-2.5 text-xs font-medium text-accent hover:bg-accent/10">
              {t("openHouse")} <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          ) : (
            <>
              <button
                type="button"
                disabled={busy}
                onClick={() => onUndo(d.expense_id)}
                className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium hover:bg-foreground/5 disabled:opacity-50"
              >
                <Undo2 aria-hidden className="size-3.5" /> {t("undo")}
              </button>
              <Link href="/expenses" className="inline-flex h-8 items-center gap-1 rounded-lg px-2.5 text-xs font-medium text-accent hover:bg-accent/10">
                {t("openExpenses")}
              </Link>
            </>
          )}
        </span>
        {state?.status === "error" && <p className="w-full text-xs text-danger">{state.error}</p>}
      </div>
    );
  }
  if (card.kind === "payment") {
    const d = card.data;
    return (
      <div className={`${box} flex items-center gap-3`}>
        <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-positive/10 text-positive">
          <Check className="size-4" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-xs text-muted">{t("payment")}</span>
          <span className="block truncate font-medium">{t("paymentLine", { from: d.from, to: d.to })}</span>
        </span>
        <Money amount={d.amount} currency={d.currency} className="font-semibold tabular-nums" />
      </div>
    );
  }
  const d = card.data;
  return (
    <div className={box}>
      <div className="flex items-start gap-3">
        <span aria-hidden className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent">
          <FileSpreadsheet className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-medium">{t("importTitle", { file: d.file })}</p>
          <p className="text-xs text-muted">
            {t("importBody", { n: d.count, first: formatDate(d.first), last: formatDate(d.last) })}
          </p>
        </div>
        <div className="text-right">
          {d.totals.map((x) => (
            <Money key={x.currency} amount={x.total} currency={x.currency} className="block font-semibold tabular-nums" />
          ))}
        </div>
      </div>
      <ul className="mt-3 divide-y divide-border rounded-lg border border-border text-xs">
        {d.sample.map((row, k) => (
          <li key={k} className="flex items-center justify-between gap-3 px-3 py-1.5">
            <span className="min-w-0 truncate">
              <span className="text-muted">{formatDate(row.date)}</span> · {row.description}
            </span>
            <Money amount={row.amount} currency={row.currency} className="tabular-nums" />
          </li>
        ))}
      </ul>
      {d.skipped > 0 && <p className="mt-2 text-xs text-muted">{t("importSkipped", { n: d.skipped })}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {state?.status === "confirmed" ? (
          <>
            <span className="inline-flex items-center gap-1.5 text-sm text-positive">
              <Check aria-hidden className="size-4" />
              {t("importDone", { created: state.created, duplicates: state.duplicates })}
            </span>
            <Link href="/inbox" className="inline-flex h-8 items-center gap-1 rounded-lg px-2.5 text-xs font-medium text-accent hover:bg-accent/10">
              <Inbox aria-hidden className="size-3.5" /> {t("openInbox")}
            </Link>
          </>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => onConfirm(d.draft_id)}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground hover:brightness-110 disabled:opacity-50"
          >
            {busy ? <Loader2 aria-hidden className="size-4 animate-spin" /> : <Inbox aria-hidden className="size-4" />}
            {t("importConfirm")}
          </button>
        )}
        {state?.status === "error" && <span className="text-xs text-danger">{state.error}</span>}
      </div>
    </div>
  );
}
