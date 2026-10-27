"use client";

import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarClock, Home, Inbox, PiggyBank, Plus, Receipt, ScanLine, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  BudgetMeter,
  CategoryChange,
  CategoryDonut,
  PaceChart,
  RankBars,
  SpendCalendar,
  Sparkline,
  TrendBars,
  categoryVar,
} from "@/components/charts";
import { MonthPicker } from "@/components/pickers";
import { PinnedReports } from "@/features/reports/ReportsView";
import { Async, Badge, Card, Empty, Money, Skeleton, StatCard, cardLinkClass } from "@/components/ui";
import { api, type Dashboard } from "@/lib/api";
import { categoryLabel, common, periodLabel } from "@/lib/commonMessages";
import { formatDate, formatMonth, fromMinor, todayIso } from "@/lib/format";
import { useApi, useDataVersion, useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { messages } from "./messages";

export function DashboardView() {
  const hydrated = useHydrated();
  const [month, setMonth] = useState(""); // "" = this month (the API's default)
  const changed = useDataVersion("expenses"); // reload after an expense is added, edited or deleted
  const dash = useApi(() => api.dashboard.get(month ? `${month}-01` : undefined), [month, changed]);
  const thisMonth = hydrated ? todayIso().slice(0, 7) : undefined;
  const shown = month || dash.data?.month.slice(0, 7) || thisMonth || "";
  const t = useT(messages);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-3xl">{t("title")}</h1>
          <p className="mt-1.5 text-sm text-muted">
            {shown ? t("subtitleMonth", { month: formatMonth(shown) }) : t("subtitleThisMonth")}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {shown && (
            <MonthPicker
              value={shown}
              max={thisMonth}
              align="right"
              onChange={(m) => setMonth(m === thisMonth ? "" : m)}
            />
          )}
          <Link
            href="/receipts"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium shadow-card hover:bg-card-hover"
          >
            <ScanLine aria-hidden className="size-4" /> {t("scanReceipt")}
          </Link>
          <Link
            href="/expenses#add"
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3 text-sm font-medium text-accent-foreground shadow-card hover:brightness-110"
          >
            <Plus aria-hidden className="size-4" /> {t("addExpense")}
          </Link>
        </div>
      </header>
      <Async {...dash} label={t("loading")} fallback={<DashboardSkeleton />}>
        {(d) => <DashboardBody d={d} isCurrent={!month} onPickMonth={(m) => setMonth(m === thisMonth ? "" : m)} />}
      </Async>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div aria-hidden className="grid gap-4 lg:grid-cols-4">
      <Skeleton className="h-40 rounded-2xl lg:col-span-2" />
      <Skeleton className="h-40 rounded-2xl" />
      <Skeleton className="h-40 rounded-2xl" />
      <Skeleton className="h-80 rounded-2xl lg:col-span-2" />
      <Skeleton className="h-80 rounded-2xl lg:col-span-2" />
    </div>
  );
}

function DashboardBody({ d, isCurrent, onPickMonth }: { d: Dashboard; isCurrent: boolean; onPickMonth: (m: string) => void }) {
  const hydrated = useHydrated();
  const t = useT(messages);
  const tc = useT(common);
  const prevMonth = d.trend.length >= 2 ? d.trend[d.trend.length - 2].month : null;
  // Days so far: today in the current month, the whole month for past months.
  const today = hydrated ? todayIso() : null;
  const daysSoFar = isCurrent && today && today.slice(0, 7) === d.month.slice(0, 7) ? Number(today.slice(8)) : d.daily.length;
  const dailyAverage = fromMinor(Math.floor(d.total_minor / Math.max(1, daysSoFar)));
  const runningTotals = useMemo(
    () =>
      d.daily
        .slice(0, daysSoFar)
        .reduce<number[]>((acc, x) => [...acc, (acc.at(-1) ?? 0) + x.total_minor / 100], []),
    [d.daily, daysSoFar],
  );
  const houseNet = d.house_balances.reduce((s, h) => s + h.balance_minor, 0);
  const sameCurrency = d.house_balances.every((h) => h.currency === d.currency);
  const budgetsOver = d.budgets.filter((b) => b.level !== "ok").length;
  const empty = d.total_minor === 0 && d.trend.every((p) => p.total_minor === 0);

  return (
    <div className="flex flex-col gap-6">
      {d.pending_inbox > 0 && (
        <Link
          href="/inbox"
          className="group flex items-center gap-3 rounded-2xl border border-accent/30 bg-accent-soft px-4 py-3 text-sm transition hover:border-accent/50"
        >
          <span aria-hidden className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <Inbox className="size-4" />
          </span>
          <span className="flex-1">
            <strong className="font-semibold">{d.pending_inbox}</strong>{" "}
            {t("inboxWaiting", { n: d.pending_inbox })}
          </span>
          <span className="inline-flex items-center gap-1 font-medium whitespace-nowrap text-accent">
            {t("review")} <ArrowRight aria-hidden className="size-4 transition group-hover:translate-x-0.5" />
          </span>
        </Link>
      )}

      {/* KPIs: one hero number, three supporting tiles. */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="flex min-w-0 flex-col justify-between gap-4 rounded-2xl border border-border bg-card p-5 shadow-card sm:col-span-2 sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm text-muted">{t("spentIn", { month: formatMonth(d.month) })}</p>
              <p className="mt-1 text-5xl font-semibold tracking-tight">
                <Money amount={d.total} currency={d.currency} />
              </p>
            </div>
            <MonthDelta d={d} prevMonth={prevMonth} />
          </div>
          {runningTotals.length > 1 && <Sparkline values={runningTotals} label={t("runningTotal")} />}
          <p className="text-xs text-muted">{t("totalNote", { currency: d.currency })}</p>
        </div>
        <StatCard
          icon={<TrendingUp />}
          label={t("dailyAverage")}
          value={<Money amount={dailyAverage} currency={d.currency} />}
          footer={t("overDays", { n: daysSoFar })}
        />
        <StatCard
          icon={<PiggyBank />}
          label={t("budgets")}
          value={
            d.budgets.length === 0 ? (
              <span className="text-muted">{t("noneSet")}</span>
            ) : budgetsOver === 0 ? (
              <span>{t("allOnTrack")}</span>
            ) : (
              <span className="text-warning">{t("needLook", { n: budgetsOver })}</span>
            )
          }
          footer={
            <span className="flex flex-wrap items-center justify-between gap-2">
              {d.budgets.length > 0 && <span>{t("budgetsThisMonth", { n: d.budgets.length })}</span>}
              <Link href="/budgets" className={`${cardLinkClass} -ml-1.5`}>
                {d.budgets.length === 0 ? t("setBudget") : tc("open")}
              </Link>
            </span>
          }
        />
      </div>

      <PinnedReports />

      {empty ? (
        <Card>
          <Empty
            icon={<Receipt />}
            action={
              <div className="flex flex-wrap justify-center gap-2">
                <Link href="/expenses#add" className={cardLinkClass}>
                  {t("addAnExpense")}
                </Link>
                <Link href="/receipts" className={cardLinkClass}>
                  {t("scanAReceipt")}
                </Link>
                <Link href="/import" className={cardLinkClass}>
                  {t("importStatement")}
                </Link>
              </div>
            }
          >
            {t("noSpending")}
          </Empty>
        </Card>
      ) : (
        <>
          <div className="grid gap-6 xl:grid-cols-5">
            <Card
              title={t("spendingPace")}
              description={prevMonth ? t("paceAgainst", { month: formatMonth(prevMonth) }) : t("paceAgainstLastMonth")}
              className="xl:col-span-3"
            >
              <PaceChart
                daily={d.daily}
                previous={d.previous_daily}
                uptoDay={daysSoFar}
                monthLabel={formatMonth(d.month)}
                previousLabel={prevMonth ? formatMonth(prevMonth) : t("lastMonth")}
                currency={d.currency}
              />
            </Card>
            <Card title={t("byCategory")} description={formatMonth(d.month)} className="xl:col-span-2">
              {d.by_category.length === 0 ? (
                <Empty>{t("noSpendingIn", { month: formatMonth(d.month) })}</Empty>
              ) : (
                <CategoryDonut rows={d.by_category} total={d.total} currency={d.currency} />
              )}
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Card title={t("lastSixMonths")} description={t("clickMonth")}>
              <TrendBars points={d.trend} currency={d.currency} selected={d.month.slice(0, 7)} onPick={onPickMonth} />
            </Card>
            <Card title={t("calendar")} description={t("darkerDays")}>
              <SpendCalendar daily={d.daily} currency={d.currency} />
            </Card>
            <Card title={t("topPlaces")} description={formatMonth(d.month)} className="lg:col-span-2 xl:col-span-1">
              {d.top_merchants.length === 0 ? (
                <Empty>{t("nothingYet")}</Empty>
              ) : (
                <RankBars
                  rows={d.top_merchants.map((m) => ({ name: m.merchant, total: m.total, total_minor: m.total_minor }))}
                  currency={d.currency}
                  label={t("topPlacesThisMonth")}
                  detail={(i) => t("visits", { n: d.top_merchants[i].count })}
                />
              )}
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title={t("compared")} description={t("comparedDescription")}>
              <CategoryChange current={d.by_category} previous={d.previous_by_category} currency={d.currency} />
            </Card>
            <Card
              title={t("budgets")}
              description={formatMonth(d.month)}
              actions={
                <Link href="/budgets" className={cardLinkClass}>
                  {t("manage")} <ArrowRight aria-hidden className="size-3.5" />
                </Link>
              }
            >
              {d.budgets.length === 0 ? (
                <Empty
                  icon={<PiggyBank />}
                  action={
                    <Link href="/budgets" className={cardLinkClass}>
                      {t("setBudget")}
                    </Link>
                  }
                >
                  {t("noBudgets")}
                </Empty>
              ) : (
                <div className="flex flex-col gap-5">
                  {d.budgets.map((b) => (
                    <BudgetMeter key={b.budget.id} status={b} />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </>
      )}

      <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        <Card
          title={t("houseBalances")}
          actions={
            <Link href="/houses" className={cardLinkClass}>
              {tc("open")} <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          }
        >
          {d.house_balances.length === 0 ? (
            <Empty icon={<Home />}>{t("notInHouse")}</Empty>
          ) : (
            <div className="flex flex-col gap-4">
              {sameCurrency && d.house_balances.length > 1 && (
                <p className="text-sm text-muted">
                  {t("net")}{" "}
                  <Money
                    amount={fromMinor(houseNet)}
                    currency={d.currency}
                    signed
                    className={`font-semibold ${houseNet >= 0 ? "text-positive" : "text-danger"}`}
                  />
                </p>
              )}
              <ul className="flex flex-col divide-y divide-border text-sm">
                {d.house_balances.map((h) => (
                  <li key={h.house_id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                    <span className="flex items-center gap-2.5 font-medium">
                      <span aria-hidden className="flex size-8 items-center justify-center rounded-lg bg-foreground/[0.05]">
                        <Home className="size-4 text-muted" />
                      </span>
                      {h.house_name}
                    </span>
                    {h.balance_minor === 0 ? (
                      <Badge tone="positive">{t("allSettled")}</Badge>
                    ) : h.balance_minor > 0 ? (
                      <span className="text-right">
                        <span className="block text-xs text-muted">{t("youAreOwed")}</span>
                        <Money amount={h.balance} currency={h.currency} className="font-semibold text-positive" />
                      </span>
                    ) : (
                      <span className="text-right">
                        <span className="block text-xs text-muted">{t("youOwe")}</span>
                        <Money amount={h.balance.replace(/^-/, "")} currency={h.currency} className="font-semibold text-danger" />
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card
          title={t("upcoming")}
          description={t("next30Days")}
          actions={
            <Link href="/subscriptions" className={cardLinkClass}>
              {t("all")} <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          }
        >
          {d.upcoming_subscriptions.length === 0 ? (
            <Empty icon={<CalendarClock />}>{t("noUpcoming")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {d.upcoming_subscriptions.map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="flex min-w-0 items-center gap-3">
                    <DateChip iso={s.next_expected_date} />
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{s.display_name}</span>
                      <span className="text-xs text-muted capitalize">{periodLabel(s.period)}</span>
                    </span>
                  </span>
                  <Money amount={s.amount} currency={s.currency} className="font-medium tabular-nums" />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          title={t("recent")}
          actions={
            <Link href="/expenses" className={cardLinkClass}>
              {t("all")} <ArrowRight aria-hidden className="size-3.5" />
            </Link>
          }
          className="lg:col-span-2 xl:col-span-1"
        >
          {d.recent_expenses.length === 0 ? (
            <Empty icon={<Receipt />}>{t("noExpenses")}</Empty>
          ) : (
            <ul className="flex flex-col divide-y divide-border text-sm">
              {d.recent_expenses.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <span className="flex min-w-0 items-center gap-3">
                    <span
                      aria-hidden
                      className="relative flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground/[0.05] text-xs font-semibold text-foreground/70 uppercase"
                    >
                      {e.merchant.slice(0, 1)}
                      <span
                        className="absolute -right-0.5 -bottom-0.5 size-2.5 rounded-full ring-2 ring-[var(--card)]"
                        style={{ background: categoryVar(e.category ?? "") }}
                      />
                    </span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-2">
                        <span className="truncate font-medium">{e.merchant}</span>
                        {e.house_id !== null && <Badge>{tc("house")}</Badge>}
                      </span>
                      <span className="text-xs text-muted">
                        {formatDate(e.expense_date)}
                        {e.category && ` · ${categoryLabel(e.category)}`}
                      </span>
                    </span>
                  </span>
                  <span className="text-right">
                    <Money amount={e.my_amount} currency={e.currency} className="font-medium tabular-nums" />
                    {e.house_id !== null && e.my_amount_minor !== e.total_minor && (
                      <span className="block text-xs text-muted">
                        {t("ofTotal")} <Money amount={e.total} currency={e.currency} />
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

/** "2026-10-27" as a small calendar chip: OCT / 27. */
function DateChip({ iso }: { iso: string }) {
  const label = formatDate(iso);
  const [day, mon] = label.split(" ");
  return (
    <span aria-hidden className="flex w-10 shrink-0 flex-col items-center overflow-hidden rounded-lg border border-border text-center">
      <span className="w-full bg-foreground/[0.05] text-[10px] leading-4 font-semibold text-muted uppercase">{mon}</span>
      <span className="text-sm leading-6 font-semibold tabular-nums">{day}</span>
    </span>
  );
}

function MonthDelta({ d, prevMonth }: { d: Dashboard; prevMonth: string | null }) {
  const cur = d.total_minor;
  const prev = d.previous_month_total_minor;
  const t = useT(messages);
  const prevLabel = prevMonth ? formatMonth(prevMonth) : null;
  if (prev === 0)
    return (
      <p className="text-sm text-muted">
        {prevLabel ? t("nothingSpentIn", { month: prevLabel }) : t("nothingSpentLastMonth")}
      </p>
    );
  // A percentage of two integer totals; display only.
  const pct = Math.round(((cur - prev) * 100) / prev);
  const up = pct > 0;
  return (
    <div className="shrink-0 text-right">
      <span
        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-sm font-semibold ${
          pct === 0 ? "bg-foreground/[0.05] text-muted" : up ? "bg-danger/10 text-danger" : "bg-positive/10 text-positive"
        }`}
      >
        {pct !== 0 && (up ? <ArrowUpRight aria-hidden className="size-4" /> : <ArrowDownRight aria-hidden className="size-4" />)}
        {pct === 0 ? t("same") : t(up ? "more" : "less", { pct: Math.abs(pct) })}
      </span>
      <p className="mt-1 text-xs text-muted">
        {prevLabel ? t("than", { month: prevLabel }) : t("thanLastMonth")} (<Money amount={d.previous_month_total} currency={d.currency} />)
      </p>
    </div>
  );
}
