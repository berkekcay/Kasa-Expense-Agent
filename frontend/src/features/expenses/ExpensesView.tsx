"use client";

import { type FormEvent, useEffect, useState } from "react";
import { api, type Expense } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { useUserId } from "@/lib/user";
import { Button, Card, ErrorText, Field, errorMessage } from "@/components/ui";
import { ExpenseList } from "./ExpenseList";

export function ExpensesView() {
  const userId = useUserId();
  const [expenses, setExpenses] = useState<Expense[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .listExpenses()
      .then((data) => {
        if (cancelled) return;
        setExpenses(data);
        setLoadError(null);
      })
      .catch((e) => {
        if (!cancelled) setLoadError(errorMessage(e));
      });
    return () => {
      cancelled = true;
    };
  }, [userId, reload]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    setSaving(true);
    setFormError(null);
    try {
      await api.createExpense({
        merchant: String(data.get("merchant")),
        total: String(data.get("total")).replace(",", "."),
        expense_date: String(data.get("expense_date")) || undefined,
        currency: String(data.get("currency")) || "TRY",
        category: String(data.get("category")) || undefined,
      });
      form.reset();
      setReload((n) => n + 1);
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      <Card title="Recent expenses">
        {loadError ? (
          <ErrorText error={loadError} />
        ) : expenses === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : (
          <ExpenseList expenses={expenses} empty="No expenses yet. Add one or upload a receipt." />
        )}
      </Card>

      <Card title="Add expense">
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <Field label="Merchant" name="merchant" required maxLength={200} placeholder="Migros" />
          <div className="grid grid-cols-[1fr_88px] gap-3">
            <Field label="Total" name="total" required inputMode="decimal" pattern="\d+([.,]\d{1,2})?" placeholder="84.90" />
            <Field label="Currency" name="currency" defaultValue="TRY" maxLength={3} />
          </div>
          <Field label="Date" name="expense_date" type="date" />
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Category</span>
            <select name="category" className="h-9 rounded-lg border border-border bg-background px-2">
              <option value="">—</option>
              {CATEGORIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : "Add expense"}
          </Button>
          <ErrorText error={formError} />
        </form>
      </Card>
    </div>
  );
}
