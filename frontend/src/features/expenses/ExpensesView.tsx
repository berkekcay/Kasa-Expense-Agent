"use client";

import Link from "next/link";
import { type FormEvent, useState } from "react";
import { api, type Expense, type ExpenseChanges, type ExpenseFilters } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { capitalize, normalizeAmount } from "@/lib/format";
import { dataChanged, useApi } from "@/lib/hooks";
import { useUserId } from "@/lib/user";
import { useToast } from "@/components/Toast";
import { Alert, Async, Button, Card, ErrorText, Field, SelectField, errorMessage } from "@/components/ui";
import { ExpenseList } from "./ExpenseList";

export const CURRENCIES = ["TRY", "USD", "EUR", "GBP"] as const;
const SOURCES = ["manual", "receipt", "statement", "email"] as const;
const SCOPES = [
  { value: "all", label: "Personal and house" },
  { value: "personal", label: "Personal only" },
  { value: "house", label: "House bills I paid" },
] as const;
const PAGE = 50;

type Scope = NonNullable<ExpenseFilters["scope"]>;

export function ExpensesView() {
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

  const filtering = Boolean(month || category || source || scope !== "all");

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
      notify(`Deleted ${e.merchant}.`, "success");
      dataChanged("expenses");
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusy(null);
    }
  }

  function rowActions(e: Expense) {
    if (editing === e.id) return null;
    if (confirmDelete === e.id) {
      return (
        <>
          <span className="text-xs text-muted">Delete {e.merchant} for good?</span>
          <Button size="sm" variant="danger" onClick={() => remove(e)} disabled={busy === e.id}>
            {busy === e.id ? "Deleting" : "Delete expense"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
            Keep
          </Button>
        </>
      );
    }
    return (
      <>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            setEditing(e.id);
            setConfirmDelete(null);
          }}
          aria-label={`Edit ${e.merchant}`}
        >
          Edit
        </Button>
        {e.house_id === null ? (
          <Button size="sm" variant="subtle" onClick={() => setConfirmDelete(e.id)} aria-label={`Delete ${e.merchant}`}>
            Delete
          </Button>
        ) : (
          <span className="text-xs text-muted">
            Shared bill: delete it on the{" "}
            <Link href="/houses" className="text-accent underline">
              House page
            </Link>
            .
          </span>
        )}
      </>
    );
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3" role="group" aria-label="Filters">
          <Field label="Month" type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-44" />
          <SelectField label="Category" value={category} onChange={(e) => setCategory(e.target.value)} className="w-40">
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {capitalize(c)}
              </option>
            ))}
            <option value="none">No category</option>
          </SelectField>
          <SelectField
            label="Source"
            value={source}
            onChange={(e) => setSource(e.target.value as ExpenseFilters["source"])}
            className="w-36"
          >
            <option value="">All sources</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {capitalize(s)}
              </option>
            ))}
          </SelectField>
          <SelectField label="Show" value={scope} onChange={(e) => setScope(e.target.value as Scope)} className="w-48">
            {SCOPES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </SelectField>
          {filtering && (
            <Button
              variant="subtle"
              onClick={() => {
                setMonth("");
                setCategory("");
                setSource("");
                setScope("all");
              }}
            >
              Clear filters
            </Button>
          )}
        </div>

        <Card title="Expenses">
          <Async {...first} label="Loading expenses">
            {(page) => {
              const rows = [...page.items, ...extra];
              return (
                <>
                  <p className="mb-3 text-sm text-muted" aria-live="polite">
                    {page.total === 0
                      ? ""
                      : rows.length < page.total
                        ? `Showing ${rows.length} of ${page.total} expenses.`
                        : `${page.total} ${page.total === 1 ? "expense" : "expenses"}.`}
                  </p>
                  <ExpenseList
                    expenses={rows}
                    memberName={(id) => (id === userId ? "you" : id)}
                    empty={filtering ? "Nothing matches these filters." : "No expenses yet. Add one or scan a receipt."}
                    actions={rowActions}
                    extra={(e) =>
                      editing === e.id && (
                        <EditExpense
                          expense={e}
                          onCancel={() => setEditing(null)}
                          onSaved={(updated) => {
                            replaceRow(updated);
                            setEditing(null);
                            notify(`Saved ${updated.merchant}.`, "success");
                            dataChanged("expenses");
                          }}
                        />
                      )
                    }
                  />
                  {rows.length < page.total && (
                    <Button variant="ghost" className="mt-4" onClick={loadMore} disabled={loadingMore}>
                      {loadingMore ? "Loading" : "Load more"}
                    </Button>
                  )}
                </>
              );
            }}
          </Async>
        </Card>
      </div>

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

function EditExpense({
  expense,
  onSaved,
  onCancel,
}: {
  expense: Expense;
  onSaved: (e: Expense) => void;
  onCancel: () => void;
}) {
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
      aria-label={`Edit ${expense.merchant}`}
      className="mt-2 flex flex-col gap-3 rounded-lg border border-border p-3"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Merchant" name="merchant" required maxLength={200} defaultValue={expense.merchant} />
        <Field label="Date" name="expense_date" type="date" required defaultValue={expense.expense_date} />
        <SelectField label="Category" name="category" defaultValue={expense.category ?? ""}>
          <option value="">No category</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {capitalize(c)}
            </option>
          ))}
        </SelectField>
        <Field label="Note" name="note" maxLength={500} defaultValue={expense.note ?? ""} />
      </div>
      <p className="text-xs text-muted">The amount cannot be edited. To fix it, delete the expense and add it again.</p>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "Saving" : "Save changes"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
      <ErrorText error={error} />
    </form>
  );
}

function AddExpense({ onSaved }: { onSaved: () => void }) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Expense | null>(null);
  const [amountInvalid, setAmountInvalid] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const total = normalizeAmount(String(data.get("total") ?? ""));
    setAmountInvalid(!total);
    if (!total) {
      setError("Enter an amount like 84,90.");
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
      form.reset();
      setSaved(expense);
      onSaved();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="Add expense" className="lg:sticky lg:top-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <Field label="Merchant" name="merchant" required maxLength={200} placeholder="Migros" />
        <div className="grid grid-cols-[1fr_96px] gap-3">
          <Field
            label="Amount"
            name="total"
            required
            inputMode="decimal"
            placeholder="84,90"
            autoComplete="off"
            aria-invalid={amountInvalid}
            onChange={() => setAmountInvalid(false)}
          />
          <SelectField label="Currency" name="currency" defaultValue="TRY">
            {CURRENCIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </SelectField>
        </div>
        <p className="-mt-1 text-xs text-muted">Other currencies are converted to TRY at the TCMB rate for the date.</p>
        <Field label="Date" name="expense_date" type="date" hint="Empty means today." />
        <SelectField label="Category" name="category" defaultValue="">
          <option value="">Let Kasa decide</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {capitalize(c)}
            </option>
          ))}
        </SelectField>
        <Field label="Note (optional)" name="note" maxLength={500} />
        <Button type="submit" disabled={saving}>
          {saving ? "Saving" : "Add expense"}
        </Button>
        <div aria-live="polite" className="flex flex-col gap-2">
          {saved && (
            <Alert tone="success" onDismiss={() => setSaved(null)}>
              Saved {saved.merchant}.
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
        <ErrorText error={error} />
      </form>
    </Card>
  );
}
