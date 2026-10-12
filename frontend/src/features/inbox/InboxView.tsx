"use client";

import Link from "next/link";
import { type ReactNode, useState } from "react";
import { api, type InboxFilter, type InboxItem, type ParsedExpense } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { capitalize, formatDate, formatDateTime, normalizeAmount } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useToast, useWarningToasts } from "@/components/Toast";
import { Async, Badge, Button, Card, Empty, Money, controlClass, errorMessage } from "@/components/ui";

const FILTERS: { value: InboxFilter; label: string }[] = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "ignored", label: "Ignored" },
  { value: "failed", label: "Failed" },
  { value: "all", label: "All" },
];

const STATUS_TONE = {
  pending: "accent",
  approved: "positive",
  rejected: "neutral",
  ignored: "neutral",
  failed: "danger",
} as const;

const CURRENCIES = ["TRY", "USD", "EUR", "GBP"];

export function InboxView() {
  const [filter, setFilter] = useState<InboxFilter>("pending");
  const list = useApi(() => api.inbox.list(filter), [filter]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const notify = useToast();

  const items = list.data ?? [];
  const selectable = items.filter((i) => i.status !== "approved");
  const chosen = selectable.filter((i) => selected.has(i.id)).map((i) => i.id);
  const allChosen = selectable.length > 0 && chosen.length === selectable.length;

  function replace(updated: InboxItem) {
    list.setData((prev) =>
      (prev ?? [])
        .map((i) => (i.id === updated.id ? updated : i))
        .filter((i) => filter === "all" || i.status === filter),
    );
    setSelected((s) => {
      const next = new Set(s);
      next.delete(updated.id);
      return next;
    });
  }

  async function bulk(action: "approve" | "reject") {
    if (chosen.length === 0) return;
    setBulkBusy(true);
    try {
      const res = action === "approve" ? await api.inbox.approveMany(chosen) : await api.inbox.rejectMany(chosen);
      const verb = action === "approve" ? "Approved" : "Rejected";
      notify(`${verb} ${res.succeeded} of ${chosen.length}.`, res.failed ? "warning" : "success");
      for (const r of res.results) {
        if (r.error) notify(`Item ${r.item_id}: ${r.error}`, "error");
        for (const w of r.warnings) notify(w, "warning");
      }
      setSelected(new Set());
      list.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-1" role="group" aria-label="Show items by status">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            aria-pressed={filter === f.value}
            onClick={() => {
              setFilter(f.value);
              setSelected(new Set());
            }}
            className={`h-9 rounded-lg px-3 text-sm ${
              filter === f.value ? "bg-accent/15 font-medium text-accent" : "text-muted hover:bg-foreground/5 hover:text-foreground"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <Card>
        <Async {...list} label="Loading the inbox">
          {(all) =>
            all.length === 0 ? (
              <Empty
                action={
                  filter === "pending" ? (
                    <span className="flex flex-wrap gap-3">
                      <Link href="/import" className="text-accent hover:underline">
                        Import a statement
                      </Link>
                      <Link href="/settings" className="text-accent hover:underline">
                        Connect Gmail
                      </Link>
                    </span>
                  ) : undefined
                }
              >
                {filter === "pending" ? "Nothing to review. New items from Gmail and statements show up here." : "No items with this status."}
              </Empty>
            ) : (
              <div className="flex flex-col gap-4">
                {selectable.length > 0 && (
                  <div className="flex flex-wrap items-center gap-3 border-b border-border pb-3">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={allChosen}
                        onChange={() => setSelected(allChosen ? new Set() : new Set(selectable.map((i) => i.id)))}
                        className="size-4 accent-[var(--accent)]"
                      />
                      Select all ({selectable.length})
                    </label>
                    <span className="ml-auto flex flex-wrap gap-2">
                      <Button size="sm" disabled={chosen.length === 0 || bulkBusy} onClick={() => bulk("approve")}>
                        Approve {chosen.length || ""}
                      </Button>
                      <Button size="sm" variant="ghost" disabled={chosen.length === 0 || bulkBusy} onClick={() => bulk("reject")}>
                        Reject {chosen.length || ""}
                      </Button>
                    </span>
                  </div>
                )}
                <ul className="flex flex-col gap-4">
                  {all.map((item) => (
                    <InboxRow
                      key={`${item.id}-${item.status}`}
                      item={item}
                      selected={selected.has(item.id)}
                      onToggle={() =>
                        setSelected((s) => {
                          const next = new Set(s);
                          if (next.has(item.id)) next.delete(item.id);
                          else next.add(item.id);
                          return next;
                        })
                      }
                      onChanged={replace}
                    />
                  ))}
                </ul>
              </div>
            )
          }
        </Async>
      </Card>
    </div>
  );
}

type Draft = { merchant: string; expense_date: string; total: string; currency: string; category: string };

function draftOf(p: ParsedExpense | null): Draft {
  return {
    merchant: p?.merchant ?? "",
    expense_date: p?.expense_date ?? "",
    total: p?.total ?? "",
    currency: p?.currency ?? "TRY",
    category: p?.category ?? "",
  };
}

function InboxRow({
  item,
  selected,
  onToggle,
  onChanged,
}: {
  item: InboxItem;
  selected: boolean;
  onToggle: () => void;
  onChanged: (item: InboxItem) => void;
}) {
  const notify = useToast();
  const toastWarnings = useWarningToasts();
  const [draft, setDraft] = useState<Draft>(() => draftOf(item.parsed));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const original = draftOf(item.parsed);
  const dirty = (Object.keys(draft) as (keyof Draft)[]).some((k) => draft[k] !== original[k]);
  const editable = item.status !== "approved";
  const fid = (name: string) => `inbox-${item.id}-${name}`;

  function parsedFromDraft(): ParsedExpense | null {
    const total = normalizeAmount(draft.total);
    if (!draft.merchant.trim()) {
      setError("Enter the merchant.");
      return null;
    }
    if (!total) {
      setError("Enter an amount like 84,90.");
      return null;
    }
    return {
      merchant: draft.merchant.trim(),
      total,
      currency: draft.currency,
      expense_date: draft.expense_date || null,
      category: draft.category || null,
      items: item.parsed?.items ?? [],
    };
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      const parsed = parsedFromDraft();
      if (!parsed) return;
      onChanged(await api.inbox.edit(item.id, parsed));
      notify("Changes saved.", "success");
    });

  const approve = () =>
    run(async () => {
      let parsed: ParsedExpense | undefined;
      if (dirty || !item.parsed) {
        const p = parsedFromDraft();
        if (!p) return;
        parsed = p;
      }
      const res = await api.inbox.approve(item.id, parsed);
      notify(`Saved ${res.expense.merchant} as an expense.`, "success");
      toastWarnings(res.expense.warnings);
      onChanged(res.item);
    });

  const reject = () =>
    run(async () => {
      onChanged(await api.inbox.reject(item.id));
      notify("Rejected.", "info");
    });

  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [k]: e.target.value }));

  return (
    <li className="rounded-lg border border-border p-3 sm:p-4">
      <div className="flex items-start gap-3">
        {editable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label={`Select ${item.title}`}
            className="mt-1 size-4 shrink-0 accent-[var(--accent)]"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={item.source === "email" ? "accent" : "neutral"}>{item.source === "email" ? "Email" : "Statement"}</Badge>
            <Badge tone={STATUS_TONE[item.status]}>{capitalize(item.status)}</Badge>
            <span className="text-xs text-muted">
              {item.source === "statement" ? formatDate(item.received_at) : formatDateTime(item.received_at)}
            </span>
          </div>
          <p className="mt-1.5 font-medium">{item.title}</p>
          {item.sender && <p className="text-sm text-muted">{item.sender}</p>}
          {item.error && <p className="mt-1 text-sm text-danger">{item.error}</p>}

          {editable ? (
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-[2fr_1fr_1fr_88px_1fr]">
              <InlineField id={fid("merchant")} label="Merchant" className="col-span-2 sm:col-span-1">
                <input id={fid("merchant")} value={draft.merchant} onChange={set("merchant")} maxLength={200} className={controlClass} />
              </InlineField>
              <InlineField id={fid("date")} label="Date">
                <input id={fid("date")} type="date" value={draft.expense_date} onChange={set("expense_date")} className={controlClass} />
              </InlineField>
              <InlineField id={fid("total")} label="Amount">
                <input
                  id={fid("total")}
                  value={draft.total}
                  onChange={set("total")}
                  inputMode="decimal"
                  autoComplete="off"
                  className={controlClass}
                />
              </InlineField>
              <InlineField id={fid("currency")} label="Currency">
                <select id={fid("currency")} value={draft.currency} onChange={set("currency")} className={`${controlClass} px-2`}>
                  {(CURRENCIES.includes(draft.currency) ? CURRENCIES : [draft.currency, ...CURRENCIES]).map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </InlineField>
              <InlineField id={fid("category")} label="Category">
                <select id={fid("category")} value={draft.category} onChange={set("category")} className={`${controlClass} px-2`}>
                  <option value="">Let Kasa decide</option>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {capitalize(c)}
                    </option>
                  ))}
                </select>
              </InlineField>
            </div>
          ) : (
            item.parsed && (
              <p className="mt-2 text-sm">
                {item.parsed.merchant} · <Money amount={item.parsed.total} currency={item.parsed.currency} />
                {item.parsed.expense_date && ` · ${formatDate(item.parsed.expense_date)}`}
                {item.parsed.category && ` · ${capitalize(item.parsed.category)}`}
                {item.expense_id !== null && (
                  <>
                    {" "}
                    ·{" "}
                    <Link href="/expenses" className="text-accent hover:underline">
                      in your expenses
                    </Link>
                  </>
                )}
              </p>
            )
          )}

          {item.parsed && item.parsed.items.length > 0 && (
            <p className="mt-2 text-xs text-muted">{item.parsed.items.length} lines read from this item.</p>
          )}

          {item.excerpt && (
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer text-muted hover:text-foreground">
                {item.source === "email" ? "Show the email text" : "Show the statement line"}
              </summary>
              {/* Plain text only: email content is never rendered as HTML. */}
              <p className="mt-2 max-h-60 overflow-y-auto rounded-lg border border-border bg-background p-3 whitespace-pre-wrap text-muted">
                {item.excerpt}
              </p>
            </details>
          )}

          {editable && (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={approve} disabled={busy}>
                {dirty ? "Save and approve" : "Approve"}
              </Button>
              <Button size="sm" variant="ghost" onClick={reject} disabled={busy || item.status === "rejected"}>
                Reject
              </Button>
              {dirty && (
                <>
                  <Button size="sm" variant="subtle" onClick={save} disabled={busy}>
                    Save changes
                  </Button>
                  <Button size="sm" variant="subtle" onClick={() => setDraft(original)} disabled={busy}>
                    Undo changes
                  </Button>
                </>
              )}
            </div>
          )}
          <div aria-live="polite">
            {error && (
              <p role="alert" className="mt-2 text-sm text-danger">
                {error}
              </p>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function InlineField({
  id,
  label,
  className = "",
  children,
}: {
  id: string;
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={`flex min-w-0 flex-col gap-1 text-sm ${className}`}>
      <label htmlFor={id} className="text-xs text-muted">
        {label}
      </label>
      {children}
    </div>
  );
}
