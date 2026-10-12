"use client";

import { type FormEvent, useState } from "react";
import { api, type Budget } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { capitalize, formatMonth, monthParam, normalizeAmount } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import { BudgetMeter } from "@/components/charts";
import { useToast } from "@/components/Toast";
import { Async, Button, Card, Empty, ErrorText, Field, SelectField, errorMessage } from "@/components/ui";

const OVERALL = "__overall__";

export function BudgetsView() {
  const [month, setMonth] = useState("");
  const status = useApi(() => api.budgets.status(monthParam(month)), [month]);
  const [editing, setEditing] = useState<Budget | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const notify = useToast();
  const shownMonth = month || status.data?.[0]?.month.slice(0, 7) || "";

  async function remove(b: Budget) {
    try {
      await api.budgets.remove(b.id);
      notify(`${b.category ? capitalize(b.category) : "Overall"} budget deleted.`, "success");
      setConfirmDelete(null);
      if (editing?.id === b.id) setEditing(null);
      status.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    }
  }

  return (
    <div className="grid items-start gap-6 lg:grid-cols-[1fr_340px]">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Month" type="month" value={shownMonth} onChange={(e) => setMonth(e.target.value)} className="w-44" />
          {month && (
            <Button variant="subtle" onClick={() => setMonth("")}>
              Back to this month
            </Button>
          )}
        </div>
        <Card title={shownMonth ? `Status for ${formatMonth(shownMonth)}` : "Status"}>
          <Async {...status} label="Loading budgets">
            {(rows) =>
              rows.length === 0 ? (
                <Empty>No budgets yet. Add one to get a warning before you overspend.</Empty>
              ) : (
                <ul className="flex flex-col gap-6">
                  {rows.map((s) => {
                    const label = s.budget.category ? capitalize(s.budget.category) : "Overall";
                    return (
                      <li key={s.budget.id}>
                        <BudgetMeter
                          status={s}
                          actions={
                            <span className="flex flex-wrap items-center justify-end gap-1 text-xs">
                              <span className="mr-auto text-muted">Alert at {s.budget.alert_threshold_pct}%</span>
                              {confirmDelete === s.budget.id ? (
                                <>
                                  <Button size="sm" variant="danger" onClick={() => remove(s.budget)}>
                                    Delete {label}
                                  </Button>
                                  <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
                                    Keep
                                  </Button>
                                </>
                              ) : (
                                <>
                                  <Button size="sm" variant="subtle" onClick={() => setEditing(s.budget)} aria-label={`Edit ${label} budget`}>
                                    Edit
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="subtle"
                                    onClick={() => setConfirmDelete(s.budget.id)}
                                    aria-label={`Delete ${label} budget`}
                                  >
                                    Delete
                                  </Button>
                                </>
                              )}
                            </span>
                          }
                        />
                      </li>
                    );
                  })}
                </ul>
              )
            }
          </Async>
        </Card>
      </div>

      <BudgetForm
        key={editing?.id ?? "new"}
        editing={editing}
        existing={status.data?.map((s) => s.budget) ?? []}
        onDone={() => {
          setEditing(null);
          status.reload();
        }}
        onCancel={() => setEditing(null)}
      />
    </div>
  );
}

function BudgetForm({
  editing,
  existing,
  onDone,
  onCancel,
}: {
  editing: Budget | null;
  existing: Budget[];
  onDone: () => void;
  onCancel: () => void;
}) {
  const notify = useToast();
  const [category, setCategory] = useState(editing ? (editing.category ?? OVERALL) : OVERALL);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const match = existing.find((b) => (b.category ?? OVERALL) === category);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const limit = normalizeAmount(String(data.get("limit") ?? ""));
    if (!limit) {
      setError("Enter a monthly limit like 3000.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await api.budgets.set({
        category: category === OVERALL ? null : category,
        limit,
        alert_threshold_pct: Number(data.get("threshold")) || 80,
      });
      notify(`${saved.category ? capitalize(saved.category) : "Overall"} budget saved.`, "success");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title={editing ? "Edit budget" : "Add a budget"} className="lg:sticky lg:top-4">
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <SelectField label="Category" value={category} onChange={(e) => setCategory(e.target.value)} disabled={Boolean(editing)}>
          <option value={OVERALL}>Overall (all spending)</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {capitalize(c)}
            </option>
          ))}
        </SelectField>
        {!editing && match && (
          <p className="text-xs text-muted">This category already has a budget. Saving replaces its limit.</p>
        )}
        <Field
          key={`limit-${category}`}
          label="Monthly limit (TRY)"
          name="limit"
          required
          inputMode="decimal"
          autoComplete="off"
          defaultValue={editing?.limit ?? match?.limit ?? ""}
          placeholder="3000"
        />
        <Field
          key={`threshold-${category}`}
          label="Warn me at (% of the limit)"
          name="threshold"
          type="number"
          min={1}
          max={100}
          required
          defaultValue={editing?.alert_threshold_pct ?? match?.alert_threshold_pct ?? 80}
        />
        <div className="flex gap-2">
          <Button type="submit" disabled={saving} className="flex-1">
            {saving ? "Saving" : editing || match ? "Update budget" : "Add budget"}
          </Button>
          {editing && (
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
        <ErrorText error={error} />
      </form>
    </Card>
  );
}
