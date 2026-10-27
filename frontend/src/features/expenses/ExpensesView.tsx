"use client";

import { CalendarDays, ChevronDown, Download, FilterX, House, Pencil, Plus, ScanLine, Trash2, X } from "lucide-react";
import Link from "next/link";
import { type ButtonHTMLAttributes, type FormEvent, type ReactNode, useState } from "react";
import { api, saveBlob, type Expense, type ExpenseChanges, type ExpenseFilters } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { categoryLabel, common } from "@/lib/commonMessages";
import { formatMonth, fromMinor, normalizeAmount, todayIso } from "@/lib/format";
import { dataChanged, useApi } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { useUserId } from "@/lib/user";
import { useToast } from "@/components/Toast";
import { DatePicker, MonthPicker } from "@/components/pickers";
import {
  Alert,
  Async,
  Button,
  Card,
  ErrorText,
  Field,
  Money,
  PageHeader,
  SelectField,
  Skeleton,
  errorMessage,
} from "@/components/ui";
import { ExpenseList } from "./ExpenseList";
import { messages } from "./messages";

export const CURRENCIES = ["TRY", "USD", "EUR", "GBP"] as const;
const SOURCES = ["manual", "receipt", "statement", "email"] as const;
const SCOPES = ["all", "personal", "house"] as const;
const PAGE = 50;

type Scope = NonNullable<ExpenseFilters["scope"]>;

const ICON_BUTTON =
  "inline-flex size-8 items-center justify-center rounded-lg text-muted transition hover:bg-foreground/5 hover:text-foreground disabled:pointer-events-none disabled:opacity-40 [&>svg]:size-4";

function IconButton({ label, className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button type="button" aria-label={label} className={`${ICON_BUTTON} ${className}`} {...props} />;
}

/** A compact select for the filter bar. The label is for screen readers; the options say what it filters. */
function FilterSelect({
  label,
  value,
  active,
  onChange,
  children,
}: {
  label: string;
  value: string;
  active: boolean;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="relative inline-flex min-w-0">
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`h-9 max-w-full min-w-0 appearance-none truncate rounded-lg border pr-8 pl-3 text-sm shadow-card outline-none transition hover:border-border-strong focus-visible:border-accent ${
          active ? "border-accent/40 bg-accent-soft font-medium text-accent" : "border-border bg-card"
        }`}
      >
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute top-1/2 right-2.5 size-4 -translate-y-1/2 text-muted" />
    </label>
  );
}

function ListSkeleton() {
  return (
    <div aria-hidden className="flex flex-col divide-y divide-border">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="flex items-center gap-3 py-3 first:pt-0">
          <Skeleton className="size-9 shrink-0 rounded-lg" />
          <div className="flex flex-1 flex-col gap-1.5">
            <Skeleton className="h-3.5 w-40 max-w-full" />
            <Skeleton className="h-3 w-28" />
          </div>
          <Skeleton className="h-4 w-20" />
        </div>
      ))}
    </div>
  );
}

/** The page header. A client component so its text follows the chosen language. */
export function ExpensesHeader() {
  const t = useT(messages);
  return (
    <PageHeader
      title={t("pageTitle")}
      subtitle={t("pageSubtitle")}
      actions={
        <>
          <Link
            href="/receipts"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium shadow-card hover:bg-card-hover"
          >
            <ScanLine aria-hidden className="size-4" /> {t("scanReceipt")}
          </Link>
          <a
            href="#add"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
          >
            <Plus aria-hidden className="size-4" /> {t("addExpense")}
          </a>
        </>
      }
    />
  );
}

export function ExpensesView() {
  const t = useT(messages);
  const tc = useT(common);
  const userId = useUserId();
  const notify = useToast();
  const [month, setMonth] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState<ExpenseFilters["source"]>("");
  const [scope, setScope] = useState<Scope>("all");
  const filters: ExpenseFilters = { month, category, source, scope };
  const first = useApi(() => api.listExpensePage({ ...filters, limit: PAGE }), [month, category, source, scope]);

  // Pages after the first, kept for the current filters only.
  const filterKey = JSON.stringify([userId, month, category, source, scope]);
  const [more, setMore] = useState<{ key: string; items: Expense[] }>({ key: "", items: [] });
  const extra = more.key === filterKey ? more.items : [];
  const [loadingMore, setLoadingMore] = useState(false);
  const [editing, setEditing] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const [busy, setBusy] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);

  const filtering = Boolean(month || category || source || scope !== "all");

  function clearFilters() {
    setMonth("");
    setCategory("");
    setSource("");
    setScope("all");
  }

  async function exportCsv() {
    setExporting(true);
    try {
      const blob = await api.exportExpensesCsv(filters);
      saveBlob(blob, month ? `kasa-expenses-${month}.csv` : "kasa-expenses.csv");
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setExporting(false);
    }
  }

  async function loadMore() {
    if (!first.data) return;
    setLoadingMore(true);
    try {
      const page = await api.listExpensePage({ ...filters, limit: PAGE, offset: first.data.items.length + extra.length });
      setMore({ key: filterKey, items: [...extra, ...page.items] });
      first.setData((p) => p && { ...p, total: page.total });
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setLoadingMore(false);
    }
  }

  function replaceRow(updated: Expense) {
    const swap = (rows: Expense[]) => rows.map((e) => (e.id === updated.id ? updated : e));
    first.setData((p) => p && { ...p, items: swap(p.items) });
    setMore((m) => ({ ...m, items: swap(m.items) }));
  }

  async function remove(e: Expense) {
    setBusy(e.id);
    try {
      await api.deleteExpense(e.id);
      const drop = (rows: Expense[]) => rows.filter((x) => x.id !== e.id);
      first.setData((p) => p && { items: drop(p.items), total: Math.max(0, p.total - 1) });
      setMore((m) => ({ ...m, items: drop(m.items) }));
      setConfirmDelete(null);
      notify(t("deletedToast", { merchant: e.merchant }), "success");
      dataChanged("expenses");
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  function rowButtons(e: Expense) {
    if (editing === e.id) return null;
    return (
      <>
        <IconButton
          label={t("editLabel", { merchant: e.merchant })}
          title={tc("edit")}
          onClick={() => {
            setEditing(e.id);
            setConfirmDelete(null);
          }}
        >
          <Pencil aria-hidden />
        </IconButton>
        {e.house_id === null ? (
          <IconButton
            label={t("deleteLabel", { merchant: e.merchant })}
            title={tc("delete")}
            aria-expanded={confirmDelete === e.id}
            onClick={() => setConfirmDelete(confirmDelete === e.id ? null : e.id)}
            className="hover:bg-danger/10 hover:text-danger"
          >
            <Trash2 aria-hidden />
          </IconButton>
        ) : (
          <Link
            href="/houses"
            aria-label={t("sharedBillLabel", { merchant: e.merchant })}
            title={t("sharedBillTitle")}
            className={ICON_BUTTON}
          >
            <House aria-hidden />
          </Link>
        )}
      </>
    );
  }

  function confirmStrip(e: Expense) {
    if (confirmDelete !== e.id || editing === e.id) return null;
    return (
      <div className="flex w-full flex-wrap items-center gap-2 rounded-xl border border-danger/30 bg-danger/[0.06] px-3 py-2">
        <span className="mr-auto text-sm">{t("deleteConfirm", { merchant: e.merchant })}</span>
        <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
          {t("keep")}
        </Button>
        <Button size="sm" variant="danger" onClick={() => remove(e)} disabled={busy === e.id}>
          <Trash2 aria-hidden className="size-3.5" />
          {busy === e.id ? t("deleting") : t("deleteExpense")}
        </Button>
      </div>
    );
  }

  const page = first.data;
  const rows = page ? [...page.items, ...extra] : [];
  const countText = !page
    ? ""
    : page.total === 0
      ? ""
      : rows.length < page.total
        ? t("showing", { shown: rows.length, total: page.total })
        : t("count", { n: page.total });
  // A total only when every matching row is loaded and they share one currency. Integer sum.
  const currencies = new Set(rows.map((r) => r.currency));
  const total =
    page && rows.length > 0 && rows.length === page.total && currencies.size === 1
      ? { amount: fromMinor(rows.reduce((s, r) => s + r.total_minor, 0)), currency: rows[0].currency }
      : null;

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Card
        title={month ? t("transactionsIn", { month: formatMonth(month) }) : t("transactions")}
        description={
          <span aria-live="polite" className="block min-h-5">
            {countText}
          </span>
        }
        actions={
          total && (
            <div className="text-right">
              <p className="text-xs text-muted">{tc("total")}</p>
              <Money amount={total.amount} currency={total.currency} className="text-lg font-semibold tracking-tight tabular-nums" />
            </div>
          )
        }
      >
        <div
          role="group"
          aria-label={t("filters")}
          className="-mx-5 mb-5 flex flex-wrap items-center gap-2 border-y border-border bg-foreground/[0.02] px-5 py-3 sm:-mx-6 sm:px-6"
        >
          {month ? (
            <span className="inline-flex items-center gap-1">
              <MonthPicker value={month} onChange={setMonth} label={tc("month")} />
              <IconButton label={t("showAllMonths")} title={t("showAllMonths")} onClick={() => setMonth("")}>
                <X aria-hidden />
              </IconButton>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => setMonth(todayIso().slice(0, 7))}
              aria-label={t("monthAll")}
              className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm shadow-card transition hover:border-border-strong"
            >
              <CalendarDays aria-hidden className="size-4 text-muted" />
              {tc("allMonths")}
              <ChevronDown aria-hidden className="size-3.5 text-muted" />
            </button>
          )}
          <FilterSelect label={t("category")} value={category} active={category !== ""} onChange={setCategory}>
            <option value="">{t("allCategories")}</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {categoryLabel(c)}
              </option>
            ))}
            <option value="none">{t("noCategory")}</option>
          </FilterSelect>
          <FilterSelect
            label={t("source")}
            value={source ?? ""}
            active={Boolean(source)}
            onChange={(v) => setSource(v as ExpenseFilters["source"])}
          >
            <option value="">{t("allSources")}</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`sourceOption.${s}`)}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect label={t("show")} value={scope} active={scope !== "all"} onChange={(v) => setScope(v as Scope)}>
            {SCOPES.map((s) => (
              <option key={s} value={s}>
                {t(`scope.${s}`)}
              </option>
            ))}
          </FilterSelect>
          {filtering && (
            <Button variant="subtle" onClick={clearFilters}>
              <FilterX aria-hidden className="size-4" />
              {t("clearFilters")}
            </Button>
          )}
          <Button
            variant="ghost"
            className="ml-auto"
            onClick={exportCsv}
            disabled={exporting || first.data?.total === 0}
            title={t("exportTitle")}
          >
            <Download aria-hidden className="size-4" />
            {exporting ? t("exporting") : t("exportCsv")}
          </Button>
        </div>

        <Async {...first} label={t("loadingExpenses")} fallback={<ListSkeleton />}>
          {(p) => (
            <>
              <ExpenseList
                expenses={rows}
                groupByMonth={!month}
                showHouse
                memberName={(id) => (id === userId ? t("you") : id)}
                empty={filtering ? t("emptyFiltered") : t("empty")}
                emptyAction={
                  filtering ? (
                    <Button variant="subtle" size="sm" onClick={clearFilters}>
                      {t("clearFilters")}
                    </Button>
                  ) : (
                    <div className="flex flex-wrap justify-center gap-2">
                      <a href="#add" className="text-sm font-medium text-accent hover:underline">
                        {t("addAnExpense")}
                      </a>
                      <Link href="/receipts" className="text-sm font-medium text-accent hover:underline">
                        {t("scanAReceipt")}
                      </Link>
                    </div>
                  )
                }
                trailing={rowButtons}
                actions={confirmStrip}
                extra={(e) =>
                  editing === e.id && (
                    <EditExpense
                      expense={e}
                      onCancel={() => setEditing(null)}
                      onSaved={(updated) => {
                        replaceRow(updated);
                        setEditing(null);
                        notify(t("savedToast", { merchant: updated.merchant }), "success");
                        dataChanged("expenses");
                      }}
                    />
                  )
                }
              />
              {rows.length < p.total && (
                <div className="mt-5 flex justify-center border-t border-border pt-4">
                  <Button variant="ghost" onClick={loadMore} disabled={loadingMore}>
                    {loadingMore ? tc("loading") : t("loadMore", { n: Math.min(PAGE, p.total - rows.length) })}
                  </Button>
                </div>
              )}
            </>
          )}
        </Async>
      </Card>

      <AddExpense
        onSaved={() => {
          setMore({ key: "", items: [] });
          first.reload();
          dataChanged("expenses");
        }}
      />
    </div>
  );
}

function CategoryOptions({ none }: { none: string }) {
  return (
    <>
      <option value="">{none}</option>
      {CATEGORIES.map((c) => (
        <option key={c} value={c}>
          {categoryLabel(c)}
        </option>
      ))}
    </>
  );
}

function EditExpense({
  expense,
  onSaved,
  onCancel,
}: {
  expense: Expense;
  onSaved: (e: Expense) => void;
  onCancel: () => void;
}) {
  const t = useT(messages);
  const tc = useT(common);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const changes: ExpenseChanges = {};
    const merchant = String(d.get("merchant") ?? "").trim();
    const date = String(d.get("expense_date") ?? "");
    const category = String(d.get("category") ?? "") || null;
    const note = String(d.get("note") ?? "").trim() || null;
    if (merchant !== expense.merchant) changes.merchant = merchant;
    if (date && date !== expense.expense_date) changes.expense_date = date;
    if (category !== expense.category) changes.category = category;
    if (note !== (expense.note ?? null)) changes.note = note;
    if (Object.keys(changes).length === 0) {
      onCancel();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.updateExpense(expense.id, changes));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      aria-label={t("editLabel", { merchant: expense.merchant })}
      className="mt-3 flex flex-col gap-4 rounded-xl border border-border bg-foreground/[0.02] p-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("merchant")} name="merchant" required maxLength={200} defaultValue={expense.merchant} />
        <DatePicker label={t("date")} name="expense_date" required defaultValue={expense.expense_date} />
        <SelectField label={t("category")} name="category" defaultValue={expense.category ?? ""}>
          <CategoryOptions none={t("noCategory")} />
        </SelectField>
        <Field label={t("note")} name="note" maxLength={500} defaultValue={expense.note ?? ""} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-xs text-muted">{t("amountLocked")}</p>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          {tc("cancel")}
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? tc("saving") : t("saveChanges")}
        </Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

function AddExpense({ onSaved }: { onSaved: () => void }) {
  const t = useT(messages);
  const tc = useT(common);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Expense | null>(null);
  const [amountInvalid, setAmountInvalid] = useState(false);
  // Bumped after a save so the form (and the date picker's own state) starts fresh.
  const [formKey, setFormKey] = useState(0);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const total = normalizeAmount(String(data.get("total") ?? ""));
    setAmountInvalid(!total);
    if (!total) {
      setError(t("amountError"));
      return;
    }
    setSaving(true);
    setError(null);
    setSaved(null);
    try {
      const expense = await api.createExpense({
        merchant: String(data.get("merchant")).trim(),
        total,
        expense_date: String(data.get("expense_date")) || undefined,
        currency: String(data.get("currency")) || "TRY",
        category: String(data.get("category")) || undefined,
        note: String(data.get("note") ?? "").trim() || undefined,
      });
      setFormKey((k) => k + 1);
      setSaved(expense);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card
      id="add"
      title={t("addExpense")}
      description={t("addDescription")}
      className="scroll-mt-20 lg:scroll-mt-8 xl:sticky xl:top-8"
    >
      <form key={formKey} onSubmit={onSubmit} className="@container flex flex-col gap-4">
        <div className="grid gap-4 @lg:grid-cols-2">
          <Field label={t("merchant")} name="merchant" required maxLength={200} placeholder={t("merchantPlaceholder")} />
          <div className="flex flex-col gap-1">
            <div className="grid grid-cols-[1fr_96px] gap-3">
              <Field
                label={t("amount")}
                name="total"
                required
                inputMode="decimal"
                placeholder="84,90"
                autoComplete="off"
                aria-invalid={amountInvalid}
                onChange={() => setAmountInvalid(false)}
                className="[&_input]:tabular-nums"
              />
              <SelectField label={t("currency")} name="currency" defaultValue="TRY">
                {CURRENCIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </SelectField>
            </div>
            <p className="text-xs text-muted">{t("fxHint")}</p>
          </div>
          <DatePicker label={t("date")} name="expense_date" placeholder={tc("today")} hint={t("dateHint")} />
          <SelectField label={t("category")} name="category" defaultValue="">
            <CategoryOptions none={t("letKasaDecide")} />
          </SelectField>
          <Field label={t("noteOptional")} name="note" maxLength={500} className="@lg:col-span-2" />
        </div>
        <Button type="submit" disabled={saving} className="h-10 @lg:self-end">
          {saving ? tc("saving") : t("addExpense")}
        </Button>
        <ErrorText error={error} />
      </form>
      <div aria-live="polite" className="flex flex-col gap-2 [&:not(:empty)]:mt-4">
        {saved && (
          <Alert tone="success" onDismiss={() => setSaved(null)}>
            {t("saved", { merchant: saved.merchant })}
            {saved.warnings
              .filter((w) => w.startsWith("Converted"))
              .map((w) => (
                <span key={w} className="mt-1 block text-muted">
                  {w}
                </span>
              ))}
          </Alert>
        )}
        {saved?.warnings
          .filter((w) => !w.startsWith("Converted"))
          .map((w) => (
            <Alert key={w} tone="warning">
              {w}
            </Alert>
          ))}
      </div>
    </Card>
  );
}
