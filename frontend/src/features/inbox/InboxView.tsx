"use client";

import { ArrowRight, Check, CheckCheck, FileUp, Inbox, Landmark, Mail, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { api, type InboxFilter, type InboxItem, type ParsedExpense } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { categoryLabel } from "@/lib/commonMessages";
import { formatDate, formatDateTime, normalizeAmount } from "@/lib/format";
import { dataChanged, useApi, useDataVersion } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { Swatch, categoryVar } from "@/components/charts";
import { DatePicker } from "@/components/pickers";
import { useToast, useWarningToasts } from "@/components/Toast";
import {
  Alert,
  Async,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Money,
  PageHeader,
  Segmented,
  SelectField,
  Skeleton,
  Spinner,
  cardLinkClass,
  errorMessage,
} from "@/components/ui";
import { messages } from "./messages";

const FILTERS: InboxFilter[] = ["pending", "approved", "rejected", "ignored", "failed", "all"];

const STATUS_TONE = {
  pending: "accent",
  approved: "positive",
  rejected: "neutral",
  ignored: "neutral",
  failed: "danger",
} as const;

const CURRENCIES = ["TRY", "USD", "EUR", "GBP"];

/** Tell the sidebar count (inbox) and expense views (expenses) that something changed. */
function announce(expenses: boolean) {
  dataChanged("inbox");
  if (expenses) dataChanged("expenses");
}

export function InboxView() {
  const [filter, setFilter] = useState<InboxFilter>("pending");
  const version = useDataVersion("inbox"); // reload when an import or another tab adds items
  const list = useApi(() => api.inbox.list(filter), [filter, version]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkBusy, setBulkBusy] = useState<"approve" | "reject" | null>(null);
  const notify = useToast();
  const t = useT(messages);

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
    setBulkBusy(action);
    try {
      const res = action === "approve" ? await api.inbox.approveMany(chosen) : await api.inbox.rejectMany(chosen);
      notify(
        t(action === "approve" ? "bulkApproved" : "bulkRejected", { ok: res.succeeded, n: chosen.length }),
        res.failed ? "warning" : "success",
      );
      for (const r of res.results) {
        if (r.error) notify(t("itemError", { id: r.item_id, error: r.error }), "error");
        for (const w of r.warnings) notify(w, "warning");
      }
      setSelected(new Set());
      announce(action === "approve");
      list.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBulkBusy(null);
    }
  }

  return (
    <>
      <PageHeader
        title={t("title")}
        subtitle={t("subtitle")}
        actions={
          <Link
            href="/import"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium shadow-card hover:border-border-strong hover:bg-card-hover"
          >
            <FileUp aria-hidden className="size-4" /> {t("importStatement")}
          </Link>
        }
      />

      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="-mx-1 max-w-full overflow-x-auto px-1 py-0.5">
            <Segmented
              label={t("filterLabel")}
              value={filter}
              options={FILTERS.map((f) => ({ value: f, label: t(`filter.${f}`) }))}
              onChange={(v) => {
                setFilter(v);
                setSelected(new Set());
              }}
            />
          </div>
          {list.data && list.data.length > 0 && (
            <p className="text-sm text-muted" aria-live="polite">
              {t("itemCount", { n: list.data.length })}
            </p>
          )}
        </div>

        <Async {...list} label={t("loading")} fallback={<InboxSkeleton />}>
          {(all) =>
            all.length === 0 ? (
              <Card>
                {filter === "pending" ? (
                  <Empty
                    icon={<CheckCheck />}
                    action={
                      <span className="flex flex-wrap justify-center gap-2">
                        <Link href="/import" className={cardLinkClass}>
                          {t("importLink")}
                        </Link>
                        <Link href="/settings" className={cardLinkClass}>
                          {t("connectGmail")}
                        </Link>
                      </span>
                    }
                  >
                    <span className="block text-base font-semibold text-foreground">{t("emptyTitle")}</span>
                    <span className="mt-1 block">{t("emptyText")}</span>
                  </Empty>
                ) : (
                  <Empty icon={<Inbox />}>{t("emptyFiltered")}</Empty>
                )}
              </Card>
            ) : (
              <div className="flex flex-col gap-4">
                {selectable.length > 1 && (
                  <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-card px-4 py-2.5 shadow-card sm:px-5">
                    <label className="flex items-center gap-2.5 text-sm">
                      <input
                        type="checkbox"
                        checked={allChosen}
                        onChange={() => setSelected(allChosen ? new Set() : new Set(selectable.map((i) => i.id)))}
                        className="size-4 accent-[var(--accent)]"
                      />
                      {chosen.length > 0
                        ? t("selectedOf", { n: chosen.length, total: selectable.length })
                        : t("selectAll", { n: selectable.length })}
                    </label>
                    <span className="ml-auto flex flex-wrap gap-2">
                      <Button size="sm" variant="ghost" disabled={chosen.length === 0 || bulkBusy !== null} onClick={() => bulk("reject")}>
                        {bulkBusy === "reject" ? <Spinner className="size-3.5" /> : <X aria-hidden className="size-3.5" />}
                        {t("rejectN", { n: chosen.length })}
                      </Button>
                      <Button size="sm" disabled={chosen.length === 0 || bulkBusy !== null} onClick={() => bulk("approve")}>
                        {bulkBusy === "approve" ? <Spinner className="size-3.5" /> : <Check aria-hidden className="size-3.5" />}
                        {t("approveN", { n: chosen.length })}
                      </Button>
                    </span>
                  </div>
                )}
                <ul className="flex flex-col gap-4">
                  {all.map((item) => (
                    <InboxCard
                      key={`${item.id}-${item.status}`}
                      item={item}
                      selectable={selectable.length > 1}
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
      </div>
    </>
  );
}

function InboxSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-4">
      <Skeleton className="h-52 rounded-2xl" />
      <Skeleton className="h-52 rounded-2xl" />
      <Skeleton className="h-52 rounded-2xl" />
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

function SourceIcon({ source }: { source: InboxItem["source"] }) {
  const Icon = source === "email" ? Mail : Landmark;
  return (
    <span aria-hidden className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-foreground/[0.05] text-foreground/70">
      <Icon className="size-4" />
    </span>
  );
}

function InboxCard({
  item,
  selectable,
  selected,
  onToggle,
  onChanged,
}: {
  item: InboxItem;
  selectable: boolean;
  selected: boolean;
  onToggle: () => void;
  onChanged: (item: InboxItem) => void;
}) {
  const notify = useToast();
  const toastWarnings = useWarningToasts();
  const t = useT(messages);
  const [draft, setDraft] = useState<Draft>(() => draftOf(item.parsed));
  const [busy, setBusy] = useState<"approve" | "reject" | "save" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const original = draftOf(item.parsed);
  const dirty = (Object.keys(draft) as (keyof Draft)[]).some((k) => draft[k] !== original[k]);
  const editable = item.status !== "approved";
  const received = item.source === "statement" ? formatDate(item.received_at) : formatDateTime(item.received_at);

  function parsedFromDraft(): ParsedExpense | null {
    const total = normalizeAmount(draft.total);
    if (!draft.merchant.trim()) {
      setError(t("errMerchant"));
      return null;
    }
    if (!total) {
      setError(t("errAmount"));
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

  async function run(kind: "approve" | "reject" | "save", action: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(null);
    }
  }

  const save = () =>
    run("save", async () => {
      const parsed = parsedFromDraft();
      if (!parsed) return;
      onChanged(await api.inbox.edit(item.id, parsed));
      notify(t("savedToast"), "success");
      announce(false);
    });

  const approve = () =>
    run("approve", async () => {
      let parsed: ParsedExpense | undefined;
      if (dirty || !item.parsed) {
        const p = parsedFromDraft();
        if (!p) return;
        parsed = p;
      }
      const res = await api.inbox.approve(item.id, parsed);
      notify(t("approvedToast", { merchant: res.expense.merchant }), "success");
      toastWarnings(res.expense.warnings);
      onChanged(res.item);
      announce(true);
    });

  const reject = () =>
    run("reject", async () => {
      onChanged(await api.inbox.reject(item.id));
      notify(t("rejectedToast"), "info");
      announce(false);
    });

  const set = (k: keyof Draft) => (e: { target: { value: string } }) => setDraft((d) => ({ ...d, [k]: e.target.value }));
  const suggested = item.parsed?.category ?? null;

  return (
    <li className="rounded-2xl border border-border bg-card p-4 shadow-card sm:p-5">
      <div className="flex items-start gap-3 sm:gap-4">
        {editable && selectable && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label={t("selectItem", { title: item.title })}
            className="mt-3 size-4 shrink-0 accent-[var(--accent)]"
          />
        )}
        <SourceIcon source={item.source} />
        <div className="min-w-0 flex-1">
          {/* Header: what it is, where it came from, how much. */}
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{item.title}</span>
                <Badge tone={STATUS_TONE[item.status]}>{t(`status.${item.status}`)}</Badge>
              </p>
              <p className="mt-0.5 text-xs text-muted">
                {item.source === "email" ? t("sourceEmail") : t("sourceStatement")}
                {item.sender && ` · ${item.sender}`} · {received}
              </p>
            </div>
            {item.parsed && (
              <div className="text-right">
                <Money amount={item.parsed.total} currency={item.parsed.currency} className="text-lg font-semibold tracking-tight tabular-nums" />
                {item.parsed.expense_date && <p className="text-xs text-muted">{formatDate(item.parsed.expense_date)}</p>}
              </div>
            )}
          </div>

          {suggested && (
            <p className="mt-3 inline-flex items-center gap-2 rounded-full border border-border px-2.5 py-1 text-xs">
              <Swatch color={categoryVar(suggested)} />
              <span className="text-muted">{editable ? t("suggested") : t("category")}</span>
              <span className="font-medium">{categoryLabel(suggested)}</span>
            </p>
          )}

          {item.error && (
            <Alert tone="error" className="mt-3">
              {item.error}
            </Alert>
          )}

          {editable ? (
            <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-6">
              <Field
                label={t("merchant")}
                value={draft.merchant}
                onChange={set("merchant")}
                maxLength={200}
                className="sm:col-span-3"
              />
              <Field
                label={t("amount")}
                value={draft.total}
                onChange={set("total")}
                inputMode="decimal"
                autoComplete="off"
                className="sm:col-span-2"
              />
              <SelectField label={t("currency")} value={draft.currency} onChange={set("currency")}>
                {(CURRENCIES.includes(draft.currency) ? CURRENCIES : [draft.currency, ...CURRENCIES]).map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </SelectField>
              <DatePicker
                label={t("date")}
                value={draft.expense_date}
                onChange={(day) => setDraft((d) => ({ ...d, expense_date: day }))}
                placeholder={t("noDate")}
                className="sm:col-span-3"
              />
              <SelectField label={t("category")} value={draft.category} onChange={set("category")} className="sm:col-span-3">
                <option value="">{t("letKasa")}</option>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {categoryLabel(c)}
                  </option>
                ))}
              </SelectField>
            </div>
          ) : (
            item.parsed && (
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="text-muted">
                  {item.decided_at
                    ? t("savedAsOn", { merchant: item.parsed.merchant, date: formatDateTime(item.decided_at) })
                    : t("savedAs", { merchant: item.parsed.merchant })}
                </span>
                {item.expense_id !== null && (
                  <Link href="/expenses" className={cardLinkClass}>
                    {t("inExpenses")} <ArrowRight aria-hidden className="size-3.5" />
                  </Link>
                )}
              </div>
            )
          )}

          {item.excerpt && (
            <details className="group mt-3 text-sm">
              <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md text-muted hover:text-foreground [&::-webkit-details-marker]:hidden">
                <ArrowRight aria-hidden className="size-3.5 transition group-open:rotate-90" />
                {item.source === "email" ? t("showEmail") : t("showStatement")}
              </summary>
              {/* Plain text only: email content is never rendered as HTML. */}
              <p className="mt-2 max-h-60 overflow-y-auto rounded-xl border border-border bg-background p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted">
                {item.excerpt}
              </p>
            </details>
          )}

          {editable && (
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
              {item.parsed && item.parsed.items.length > 0 && (
                <span className="text-xs text-muted">{t("linesRead", { n: item.parsed.items.length })}</span>
              )}
              {dirty && (
                <>
                  <Button size="sm" variant="subtle" onClick={() => setDraft(original)} disabled={busy !== null}>
                    <RotateCcw aria-hidden className="size-3.5" /> {t("undo")}
                  </Button>
                  <Button size="sm" variant="subtle" onClick={save} disabled={busy !== null}>
                    {busy === "save" && <Spinner className="size-3.5" />} {t("saveChanges")}
                  </Button>
                </>
              )}
              <span className="ml-auto flex flex-wrap gap-2">
                <Button size="sm" variant="ghost" onClick={reject} disabled={busy !== null || item.status === "rejected"}>
                  {busy === "reject" ? <Spinner className="size-3.5" /> : <X aria-hidden className="size-3.5" />}
                  {t("reject")}
                </Button>
                <Button size="sm" onClick={approve} disabled={busy !== null}>
                  {busy === "approve" ? <Spinner className="size-3.5" /> : <Check aria-hidden className="size-3.5" />}
                  {dirty ? t("saveAndApprove") : t("approve")}
                </Button>
              </span>
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
