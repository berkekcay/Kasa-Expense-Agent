"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type Dashboard } from "@/lib/api";
import { useApi, useDataVersion } from "@/lib/hooks";
import { capitalize, formatDate, formatMonth, monthParam } from "@/lib/format";
import { BudgetMeter, CategoryBars, TrendChart } from "@/components/charts";
import { Async, Badge, Card, Empty, Field, Money } from "@/components/ui";

export function DashboardView() {
  const [month, setMonth] = useState(""); // "" = this month (the API's default)
  const changed = useDataVersion("expenses"); // reload after an expense is added, edited or deleted
  const dash = useApi(() => api.dashboard.get(monthParam(month)), [month, changed]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end gap-3">
        <Field
          label="Month"
          type="month"
          value={month || (dash.data ? dash.data.month.slice(0, 7) : "")}
          onChange={(e) => setMonth(e.target.value)}
          className="w-44"
        />
        {month && (
          <button type="button" onClick={() => setMonth("")} className="h-9 rounded-lg px-2 text-sm text-accent hover:underline">
            Back to this month
          </button>
        )}
      </div>
      <Async {...dash} label="Loading your dashboard">
        {(d) => <DashboardBody d={d} />}
      </Async>
    </div>
  );
}

function DashboardBody({ d }: { d: Dashboard }) {
  const prevMonth = d.trend.length >= 2 ? d.trend[d.trend.length - 2].month : null;
  return (
    <div className="flex flex-col gap-6">
      {d.pending_inbox > 0 && (
        <Link
          href="/inbox"
          className="flex items-center justify-between gap-3 rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-sm hover:bg-accent/15"
        >
          <span>
            <strong className="font-semibold">{d.pending_inbox}</strong>{" "}
            {d.pending_inbox === 1 ? "expense is" : "expenses are"} waiting for review in your inbox.
          </span>
          <span className="whitespace-nowrap font-medium text-accent">Review →</span>
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="sm:col-span-2">
          <p className="text-sm text-muted">Spent in {formatMonth(d.month)}</p>
          <p className="mt-1 text-4xl font-semibold tracking-tight sm:text-5xl">
            <Money amount={d.total} currency={d.currency} />
          </p>
          <MonthDelta d={d} prevMonth={prevMonth} />
        </Card>
        <Card>
          <p className="text-sm text-muted">Inbox</p>
          <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
            {d.pending_inbox}
            <span className="text-sm font-normal text-muted">pending</span>
          </p>
          <Link href="/inbox" className="mt-2 inline-block text-sm text-accent hover:underline">
            {d.pending_inbox > 0 ? "Review them" : "Open inbox"}
          </Link>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="By category">
          {d.by_category.length === 0 ? (
            <Empty
              action={
                <Link href="/expenses" className="text-accent hover:underline">
                  Add an expense
                </Link>
              }
            >
              No spending in {formatMonth(d.month)} yet.
            </Empty>
          ) : (
            <CategoryBars rows={d.by_category} currency={d.currency} />
          )}
        </Card>
        <Card title="Last 6 months">
          {d.trend.every((p) => p.total_minor === 0) ? (
            <Empty>No spending in the last six months.</Empty>
          ) : (
            <TrendChart points={d.trend} currency={d.currency} />
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Budgets"
          actions={
            <Link href="/budgets" className="text-sm text-accent hover:underline">
              Manage
            </Link>
          }
        >
          {d.budgets.length === 0 ? (
            <Empty
              action={
                <Link href="/budgets" className="text-accent hover:underline">
                  Set a budget
                </Link>
              }
            >
              No budgets yet.
            </Empty>
          ) : (
            <div className="flex flex-col gap-5">
              {d.budgets.map((b) => (
                <BudgetMeter key={b.budget.id} status={b} />
              ))}
            </div>
          )}
        </Card>

        <Card
          title="House balances"
          actions={
            <Link href="/houses" className="text-sm text-accent hover:underline">
              Open
            </Link>
          }
        >
          {d.house_balances.length === 0 ? (
            <Empty>You are not in a shared house yet.</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {d.house_balances.map((h) => (
                <li key={h.house_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5 first:pt-0 last:pb-0">
                  <span className="font-medium">{h.house_name}</span>
                  {h.balance_minor === 0 ? (
                    <span className="text-muted">All settled</span>
                  ) : h.balance_minor > 0 ? (
                    <span>
                      You are owed <Money amount={h.balance} currency={h.currency} className="font-semibold text-positive" />
                    </span>
                  ) : (
                    <span>
                      You owe{" "}
                      <Money amount={h.balance.replace(/^-/, "")} currency={h.currency} className="font-semibold text-danger" />
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card
          title="Upcoming charges"
          actions={
            <Link href="/subscriptions" className="text-sm text-accent hover:underline">
              All subscriptions
            </Link>
          }
        >
          {d.upcoming_subscriptions.length === 0 ? (
            <Empty>No subscription charges expected in the next 30 days.</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {d.upcoming_subscriptions.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{s.display_name}</span>
                    <span className="text-muted">
                      {formatDate(s.next_expected_date)} · {s.period}
                    </span>
                  </span>
                  <Money amount={s.amount} currency={s.currency} className="tabular-nums" />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title="Recent expenses"
          actions={
            <Link href="/expenses" className="text-sm text-accent hover:underline">
              All expenses
            </Link>
          }
        >
          {d.recent_expenses.length === 0 ? (
            <Empty>No expenses yet.</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {d.recent_expenses.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="truncate font-medium">{e.merchant}</span>
                      {e.house_id !== null && <Badge>house</Badge>}
                    </span>
                    <span className="text-muted">
                      {formatDate(e.expense_date)}
                      {e.category && ` · ${capitalize(e.category)}`}
                    </span>
                  </span>
                  <span className="text-right">
                    <Money amount={e.my_amount} currency={e.currency} className="tabular-nums" />
                    {e.house_id !== null && e.my_amount_minor !== e.total_minor && (
                      <span className="block text-xs text-muted">
                        your share of <Money amount={e.total} currency={e.currency} />
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function MonthDelta({ d, prevMonth }: { d: Dashboard; prevMonth: string | null }) {
  const cur = d.total_minor;
  const prev = d.previous_month_total_minor;
  const prevLabel = prevMonth ? formatMonth(prevMonth) : "last month";
  if (prev === 0) {
    return (
      <p className="mt-2 text-sm text-muted">
        Nothing spent in {prevLabel}.
      </p>
    );
  }
  // A percentage of two integer totals; display only.
  const pct = Math.round(((cur - prev) * 100) / prev);
  const word = pct > 0 ? "more" : "less";
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-2 text-sm text-muted">
      {pct !== 0 && (
        <span className={`font-medium ${pct > 0 ? "text-danger" : "text-positive"}`}>
          <span aria-hidden>{pct > 0 ? "▲" : "▼"} </span>
          {Math.abs(pct)}% {word}
        </span>
      )}
      {pct === 0 && <span className="font-medium">About the same</span>}
      <span>
        {pct === 0 ? "as" : "than"} {prevLabel} (<Money amount={d.previous_month_total} currency={d.currency} />)
      </span>
    </p>
  );
}
