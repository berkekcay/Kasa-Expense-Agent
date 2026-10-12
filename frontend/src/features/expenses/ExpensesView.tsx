"use client";

import { type FormEvent, useMemo, useState } from "react";
import { api, type Expense } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { capitalize, normalizeAmount } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { useUserId } from "@/lib/user";
import { Alert, Async, Button, Card, ErrorText, Field, SelectField, errorMessage } from "@/components/ui";
import { ExpenseList } from "./ExpenseList";

export const CURRENCIES = ["TRY", "USD", "EUR", "GBP"] as const;
const SOURCES = ["manual", "receipt", "statement", "email"] as const;
const LIMIT = 500;

export function ExpensesView() {
  const userId = useUserId();
  const list = useApi(() => api.listExpenses(LIMIT), []);
  const [month, setMonth] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");

  const filtered = useMemo(
    () =>
      (list.data ?? []).filter(
        (e) =>
          (!month || e.expense_date.startsWith(month)) &&
          (!category || (category === "none" ? e.category === null : e.category === category)) &&
          (!source || e.source === source),
      ),
    [list.data, month, category, source],
  );
  const filtering = Boolean(month || category || source);

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
          <SelectField label="Source" value={source} onChange={(e) => setSource(e.target.value)} className="w-36">
            <option value="">All sources</option>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {capitalize(s)}
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
              }}
            >
              Clear filters
            </Button>
          )}
        </div>

        <Card title="Expenses">
          <Async {...list} label="Loading expenses">
            {(all) => (
              <>
                <p className="mb-3 text-sm text-muted" aria-live="polite">
                  {filtering ? `${filtered.length} of ${all.length} expenses match.` : `${all.length} expenses.`}
                  {all.length >= LIMIT && ` Showing the newest ${LIMIT}.`}
                </p>
                <ExpenseList
                  expenses={filtered}
                  memberName={(id) => (id === userId ? "you" : id)}
                  empty={filtering ? "Nothing matches these filters." : "No expenses yet. Add one or scan a receipt."}
                />
              </>
            )}
          </Async>
        </Card>
      </div>

      <AddExpense onSaved={list.reload} />
    </div>
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
