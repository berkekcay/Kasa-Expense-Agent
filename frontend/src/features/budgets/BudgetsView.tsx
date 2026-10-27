"use client";

import { Pencil, PiggyBank, Receipt, Trash2, Wallet } from "lucide-react";
import { type FormEvent, useState } from "react";
import { api, type Budget, type BudgetStatus } from "@/lib/api";
import { CATEGORIES } from "@/lib/categories";
import { categoryLabel, common } from "@/lib/commonMessages";
import { formatMonth, fromMinor, monthParam, normalizeAmount, todayIso } from "@/lib/format";
import { useApi, useHydrated } from "@/lib/hooks";
import { translate, useT } from "@/lib/i18n";
import { BudgetMeter } from "@/components/charts";
import { MonthPicker } from "@/components/pickers";
import { useToast } from "@/components/Toast";
import {
  Async,
  Button,
  Card,
  Empty,
  ErrorText,
  Field,
  Money,
  PageHeader,
  SelectField,
  Skeleton,
  StatCard,
  errorMessage,
} from "@/components/ui";
import { BudgetChart, budgetName } from "./BudgetChart";
import { messages } from "./messages";

const OVERALL = "__overall__";

export function BudgetsView() {
  const hydrated = useHydrated();
  const [month, setMonth] = useState(""); // "" = this month (the API's default)
  const status = useApi(() => api.budgets.status(monthParam(month)), [month]);
  const [editing, setEditing] = useState<Budget | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);
  const notify = useToast();
  const t = useT(messages);
  const tc = useT(common);
  const thisMonth = hydrated ? todayIso().slice(0, 7) : undefined;
  const shownMonth = month || status.data?.[0]?.month.slice(0, 7) || thisMonth || "";

  async function remove(b: Budget) {
    try {
      await api.budgets.remove(b.id);
      notify(t("deletedToast", { name: b.category ? categoryLabel(b.category) : t("overall") }), "success");
      setConfirmDelete(null);
      if (editing?.id === b.id) setEditing(null);
      status.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    }
  }

  function edit(b: Budget) {
    setEditing(b);
    setConfirmDelete(null);
    document.getElementById("budget-form")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <>
      <PageHeader
        title={t("title")}
        subtitle={shownMonth ? t("subtitleMonth", { month: formatMonth(shownMonth) }) : t("subtitle")}
        actions={
          <>
            {month && (
              <Button variant="subtle" onClick={() => setMonth("")}>
                {t("backToThisMonth")}
              </Button>
            )}
            {shownMonth && (
              <MonthPicker value={shownMonth} align="right" onChange={(m) => setMonth(m === thisMonth ? "" : m)} />
            )}
          </>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex min-w-0 flex-col gap-6">
          <Async {...status} label={t("loading")} fallback={<BudgetsSkeleton />}>
            {(rows) =>
              rows.length === 0 ? (
                <Card>
                  <Empty icon={<PiggyBank />}>{t("empty")}</Empty>
                </Card>
              ) : (
                <div className="flex flex-col gap-6">
                  <Summary rows={rows} />
                  <Card title={t("chartTitle")} description={t("chartDesc")}>
                    <BudgetChart rows={rows} />
                  </Card>
                  <Card title={t("listTitle")} description={shownMonth ? formatMonth(shownMonth) : undefined}>
                    <ul className="flex flex-col divide-y divide-border">
                      {rows.map((s) => {
                        const label = budgetName(s);
                        return (
                          <li key={s.budget.id} className="py-5 first:pt-0 last:pb-0">
                            <BudgetMeter
                              status={s}
                              actions={
                                <div className="mt-1 flex flex-wrap items-center justify-end gap-1 text-xs">
                                  <span className="mr-auto text-muted">{t("warnsAt", { pct: s.budget.alert_threshold_pct })}</span>
                                  {confirmDelete === s.budget.id ? (
                                    <>
                                      <span className="text-muted">{t("confirmDelete")}</span>
                                      <Button size="sm" variant="danger" onClick={() => remove(s.budget)}>
                                        {t("deleteNamed", { name: label })}
                                      </Button>
                                      <Button size="sm" variant="ghost" onClick={() => setConfirmDelete(null)}>
                                        {t("keep")}
                                      </Button>
                                    </>
                                  ) : (
                                    <>
                                      <Button
                                        size="sm"
                                        variant="subtle"
                                        onClick={() => edit(s.budget)}
                                        aria-label={t("editAria", { name: label })}
                                      >
                                        <Pencil aria-hidden className="size-3.5" /> {tc("edit")}
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="subtle"
                                        className="text-muted hover:text-danger"
                                        onClick={() => setConfirmDelete(s.budget.id)}
                                        aria-label={t("deleteAria", { name: label })}
                                      >
                                        <Trash2 aria-hidden className="size-3.5" /> {tc("delete")}
                                      </Button>
                                    </>
                                  )}
                                </div>
                              }
                            />
                          </li>
                        );
                      })}
                    </ul>
                  </Card>
                </div>
              )
            }
          </Async>
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
    </>
  );
}

function BudgetsSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
      </div>
      <Skeleton className="h-56 rounded-2xl" />
      <Skeleton className="h-72 rounded-2xl" />
    </div>
  );
}

/**
 * Totals for the stat row. With an overall budget, that budget is the total (category
 * budgets are slices of the same spending, so adding them up would count twice). Without
 * one, the category budgets are added up in integer minor units.
 */
function totals(rows: BudgetStatus[]) {
  const overall = rows.find((r) => r.budget.category === null);
  if (overall) {
    return {
      currency: overall.budget.currency,
      limit: overall.budget.limit,
      spent: overall.spent,
      remaining: overall.remaining,
      remainingMinor: overall.remaining_minor,
      pct: overall.pct_used,
      scope: translate(messages, "scopeOverall"),
    };
  }
  const currency = rows[0].budget.currency;
  const same = rows.filter((r) => r.budget.currency === currency);
  const limit = same.reduce((s, r) => s + r.budget.limit_minor, 0);
  const spent = same.reduce((s, r) => s + r.spent_minor, 0);
  return {
    currency,
    limit: fromMinor(limit),
    spent: fromMinor(spent),
    remaining: fromMinor(limit - spent),
    remainingMinor: limit - spent,
    pct: limit > 0 ? Math.round((spent * 100) / limit) : 0,
    scope: translate(messages, "scopeCategories", { n: same.length }),
  };
}

function Summary({ rows }: { rows: BudgetStatus[] }) {
  const tr = useT(messages);
  const t = totals(rows);
  const over = t.remainingMinor < 0;
  const needLook = rows.filter((r) => r.level !== "ok").length;
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <StatCard icon={<PiggyBank />} label={tr("budgeted")} value={<Money amount={t.limit} currency={t.currency} />} footer={t.scope} />
      <StatCard
        icon={<Receipt />}
        label={tr("spent")}
        value={<Money amount={t.spent} currency={t.currency} />}
        footer={tr("pctOfLimit", { pct: t.pct })}
      />
      <StatCard
        icon={<Wallet />}
        label={over ? tr("overBy") : tr("left")}
        value={
          <Money amount={t.remaining.replace(/^-/, "")} currency={t.currency} className={over ? "text-danger" : undefined} />
        }
        footer={needLook === 0 ? tr("allOnTrack") : tr("needLook", { n: needLook })}
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
  const t = useT(messages);
  const tc = useT(common);
  const [category, setCategory] = useState(editing ? (editing.category ?? OVERALL) : OVERALL);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const match = existing.find((b) => (b.category ?? OVERALL) === category);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const limit = normalizeAmount(String(data.get("limit") ?? ""));
    if (!limit) {
      setError(t("errLimit"));
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
      notify(t("savedToast", { name: saved.category ? categoryLabel(saved.category) : t("overall") }), "success");
      onDone();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const name = editing ? (editing.category ? categoryLabel(editing.category) : t("overall")) : null;

  return (
    <Card
      id="budget-form"
      title={name ? t("editTitle", { name }) : t("addTitle")}
      description={editing ? t("editDesc") : t("addDesc")}
      className="lg:sticky lg:top-6"
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <SelectField label={t("category")} value={category} onChange={(e) => setCategory(e.target.value)} disabled={Boolean(editing)}>
          <option value={OVERALL}>{t("overallOption")}</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </SelectField>
        {!editing && match && (
          <p className="-mt-2 text-xs text-muted">{t("existsHint")}</p>
        )}
        <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
          <Field
            key={`limit-${category}`}
            label={t("limitLabel")}
            name="limit"
            required
            inputMode="decimal"
            autoComplete="off"
            defaultValue={editing?.limit ?? match?.limit ?? ""}
            placeholder="3000"
          />
          <Field
            key={`threshold-${category}`}
            label={t("warnLabel")}
            name="threshold"
            type="number"
            min={1}
            max={100}
            required
            defaultValue={editing?.alert_threshold_pct ?? match?.alert_threshold_pct ?? 80}
          />
        </div>
        <p className="-mt-2 text-xs text-muted">{t("warnHint")}</p>
        <div className="flex gap-2 pt-1">
          <Button type="submit" disabled={saving} className="flex-1">
            {saving ? tc("saving") : editing || match ? t("updateBudget") : t("addBudget")}
          </Button>
          {editing && (
            <Button variant="ghost" onClick={onCancel}>
              {tc("cancel")}
            </Button>
          )}
        </div>
        <ErrorText error={error} />
      </form>
    </Card>
  );
}
