"use client";

import { CalendarClock, CalendarRange, Repeat, ScanSearch, Wallet } from "lucide-react";
import { Fragment, useState } from "react";
import { api, type Subscription } from "@/lib/api";
import { common, periodLabel } from "@/lib/commonMessages";
import { capitalize, formatDate, fromMinor, todayIso } from "@/lib/format";
import { useApi, useHydrated } from "@/lib/hooks";
import { useT } from "@/lib/i18n";
import { RankBars } from "@/components/charts";
import { useToast } from "@/components/Toast";
import {
  Async,
  Badge,
  Button,
  Card,
  Empty,
  Money,
  PageHeader,
  Segmented,
  Skeleton,
  Spinner,
  StatCard,
  errorMessage,
} from "@/components/ui";
import { messages } from "./messages";

/** Charges per year for each period, so every subscription can be compared on one scale. */
const PER_YEAR = { weekly: 52, monthly: 12, yearly: 1 } as const;

/** Yearly cost in integer minor units. */
const yearlyMinor = (s: Subscription) => s.amount_minor * PER_YEAR[s.period];
/** Monthly cost in integer minor units, rounded to the nearest kuruş (weekly and yearly do not divide evenly). */
const monthlyMinor = (s: Subscription) => Math.round(yearlyMinor(s) / 12);

type Totals = { currency: string; monthly: number; yearly: number; count: number }[];

/** Costs per currency, the currency with the most subscriptions first. */
function totalsByCurrency(subs: Subscription[]): Totals {
  const map = new Map<string, Totals[number]>();
  for (const s of subs) {
    const t = map.get(s.currency) ?? { currency: s.currency, monthly: 0, yearly: 0, count: 0 };
    t.monthly += monthlyMinor(s);
    t.yearly += yearlyMinor(s);
    t.count += 1;
    map.set(s.currency, t);
  }
  return [...map.values()].sort((a, b) => b.count - a.count);
}

/** One amount per currency, joined with "+" when there is more than one. */
function MoneyList({ totals, pick }: { totals: Totals; pick: (t: Totals[number]) => number }) {
  return (
    <>
      {totals.map((t, i) => (
        <Fragment key={t.currency}>
          {i > 0 && <span className="text-muted"> + </span>}
          <Money amount={fromMinor(pick(t))} currency={t.currency} />
        </Fragment>
      ))}
    </>
  );
}

/** Whole days from today to an ISO date (dates only, no money). */
function daysUntil(today: string, iso: string): number {
  const toUtc = (s: string) => Date.UTC(Number(s.slice(0, 4)), Number(s.slice(5, 7)) - 1, Number(s.slice(8, 10)));
  return Math.round((toUtc(iso) - toUtc(today)) / 86_400_000);
}

export function SubscriptionsView() {
  const [showDismissed, setShowDismissed] = useState(false);
  const list = useApi(() => api.subscriptions.list(showDismissed), [showDismissed]);
  const upcoming = useApi(() => api.subscriptions.upcoming(30), []);
  const [detecting, setDetecting] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const notify = useToast();
  const t = useT(messages);

  async function detect() {
    setDetecting(true);
    try {
      const found = await api.subscriptions.detect();
      notify(found.length === 0 ? t("foundNone") : t("found", { n: found.length }), "success");
      list.reload();
      upcoming.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setDetecting(false);
    }
  }

  async function dismiss(s: Subscription) {
    setBusyId(s.id);
    try {
      await api.subscriptions.dismiss(s.id);
      notify(t("dismissedToast", { name: s.display_name }), "success");
      list.reload();
      upcoming.reload();
    } catch (err) {
      notify(errorMessage(err), "error");
    } finally {
      setBusyId(null);
    }
  }

  const scanButton = (
    <Button onClick={detect} disabled={detecting}>
      {detecting ? <Spinner /> : <ScanSearch aria-hidden className="size-4" />}
      {detecting ? t("scanning") : t("scan")}
    </Button>
  );

  return (
    <>
      <PageHeader title={t("title")} subtitle={t("subtitle")} actions={scanButton} />
      <Async {...list} label={t("loading")} fallback={<SubscriptionsSkeleton />}>
        {(rows) => {
          const active = rows.filter((s) => s.status === "active");
          if (rows.length === 0 && !showDismissed) {
            return (
              <Card>
                <Empty icon={<Repeat />} action={scanButton}>
                  {t("empty")}
                </Empty>
              </Card>
            );
          }
          const totals = totalsByCurrency(active);
          const next = upcoming.data?.[0];
          return (
            <div className="flex flex-col gap-6">
              <div className="grid gap-4 sm:grid-cols-3">
                <StatCard
                  icon={<Wallet />}
                  label={t("monthlyCost")}
                  value={totals.length ? <MoneyList totals={totals} pick={(x) => x.monthly} /> : <span className="text-muted">{t("none")}</span>}
                  footer={t("monthlyFoot")}
                />
                <StatCard
                  icon={<CalendarRange />}
                  label={t("yearlyCost")}
                  value={totals.length ? <MoneyList totals={totals} pick={(x) => x.yearly} /> : <span className="text-muted">{t("none")}</span>}
                  footer={t("yearlyFoot")}
                />
                <StatCard
                  icon={<Repeat />}
                  label={t("activeCount")}
                  value={active.length}
                  footer={
                    next ? t("nextFoot", { name: next.display_name, date: formatDate(next.next_expected_date) }) : t("noNextFoot")
                  }
                />
              </div>

              <div className="grid items-start gap-6 lg:grid-cols-5">
                <Card
                  title={t("listTitle")}
                  description={t("listDesc")}
                  className="lg:col-span-3"
                  actions={
                    <Segmented
                      label={t("showLabel")}
                      value={showDismissed ? "all" : "active"}
                      onChange={(v) => setShowDismissed(v === "all")}
                      options={[
                        { value: "active", label: t("showActive") },
                        { value: "all", label: t("showAll") },
                      ]}
                    />
                  }
                >
                  {rows.length === 0 ? (
                    <Empty icon={<Repeat />}>{t("nothingYet")}</Empty>
                  ) : (
                    <ul className="flex flex-col divide-y divide-border text-sm">
                      {rows.map((s) => (
                        <li key={s.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-3 first:pt-0 last:pb-0">
                          <DateChip iso={s.next_expected_date} muted={s.status === "dismissed"} />
                          <div className="min-w-0 flex-1">
                            <p className="flex flex-wrap items-center gap-2">
                              <span className={`truncate font-medium ${s.status === "dismissed" ? "text-muted" : ""}`}>
                                {s.display_name}
                              </span>
                              <Badge>{capitalize(periodLabel(s.period))}</Badge>
                              {s.status === "dismissed" && <Badge tone="warning">{t("dismissed")}</Badge>}
                            </p>
                            <p className="mt-0.5 text-xs text-muted">
                              <span className="sr-only">{t("nextChargeSr", { date: formatDate(s.next_expected_date) })} </span>
                              {t("lastCharged", { date: formatDate(s.last_charge_date) })}
                            </p>
                          </div>
                          <div className="ml-auto flex items-center gap-3">
                            <Money amount={s.amount} currency={s.currency} className="font-medium tabular-nums" />
                            {s.status === "active" && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => dismiss(s)}
                                disabled={busyId === s.id}
                                aria-label={t("notSubAria", { name: s.display_name })}
                              >
                                {t("notSub")}
                              </Button>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <div className="flex min-w-0 flex-col gap-6 lg:col-span-2">
                  <UpcomingCard upcoming={upcoming} />
                  {active.length > 0 && <CostChart active={active} currency={totals[0].currency} />}
                </div>
              </div>
            </div>
          );
        }}
      </Async>
    </>
  );
}

function SubscriptionsSkeleton() {
  return (
    <div aria-hidden className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
        <Skeleton className="h-28 rounded-2xl" />
      </div>
      <div className="grid gap-6 lg:grid-cols-5">
        <Skeleton className="h-80 rounded-2xl lg:col-span-3" />
        <Skeleton className="h-80 rounded-2xl lg:col-span-2" />
      </div>
    </div>
  );
}

function UpcomingCard({
  upcoming,
}: {
  upcoming: { data: Subscription[] | null; error: string | null; loading: boolean; reload: () => void };
}) {
  const t = useT(messages);
  const tc = useT(common);
  const hydrated = useHydrated();
  const today = hydrated ? todayIso() : null;

  function when(iso: string): string {
    if (!today) return formatDate(iso);
    const days = daysUntil(today, iso);
    if (days < 0) return t("overdue");
    if (days === 0) return tc("today");
    if (days === 1) return t("tomorrow");
    return t("inDays", { n: days });
  }

  return (
    <Card title={t("upcomingTitle")} description={t("upcomingDesc")}>
      <Async {...upcoming} label={t("upcomingLoading")}>
        {(rows) => {
          if (rows.length === 0) return <Empty icon={<CalendarClock />}>{t("upcomingEmpty")}</Empty>;
          const sameCurrency = rows.every((s) => s.currency === rows[0].currency);
          const total = rows.reduce((sum, s) => sum + s.amount_minor, 0);
          return (
            <div className="flex flex-col gap-4">
              <ul className="flex flex-col divide-y divide-border text-sm">
                {rows.map((s) => (
                  <li key={s.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <span className="flex min-w-0 items-center gap-3">
                      <DateChip iso={s.next_expected_date} />
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{s.display_name}</span>
                        <span className="text-xs text-muted">
                          <span className="sr-only">{formatDate(s.next_expected_date)}, </span>
                          {when(s.next_expected_date)}
                        </span>
                      </span>
                    </span>
                    <Money amount={s.amount} currency={s.currency} className="font-medium tabular-nums" />
                  </li>
                ))}
              </ul>
              {sameCurrency && rows.length > 1 && (
                <p className="flex items-center justify-between gap-3 border-t border-border pt-3 text-sm">
                  <span className="text-muted">{t("totalDue")}</span>
                  <Money amount={fromMinor(total)} currency={rows[0].currency} className="font-semibold tabular-nums" />
                </p>
              )}
            </div>
          );
        }}
      </Async>
    </Card>
  );
}

/** Cost per subscription on one scale (per month or per year), largest first. */
function CostChart({ active, currency }: { active: Subscription[]; currency: string }) {
  const t = useT(messages);
  const tc = useT(common);
  const [scale, setScale] = useState<"year" | "month">("year");
  const shown = active.filter((s) => s.currency === currency);
  const other = active.length - shown.length;
  const rows = shown
    .map((s) => {
      const minor = scale === "year" ? yearlyMinor(s) : monthlyMinor(s);
      return { name: s.display_name, total: fromMinor(minor), total_minor: minor, period: s.period };
    })
    .sort((a, b) => b.total_minor - a.total_minor);
  return (
    <Card
      title={scale === "year" ? t("perYear") : t("perMonth")}
      description={other > 0 ? `${t("chartDesc")} ${t("otherCurrencies", { n: other })}` : t("chartDesc")}
      actions={
        <Segmented
          label={t("costPer")}
          value={scale}
          onChange={setScale}
          options={[
            { value: "month", label: tc("month") },
            { value: "year", label: t("year") },
          ]}
        />
      }
    >
      <RankBars
        rows={rows}
        currency={currency}
        label={scale === "year" ? t("rankAriaYear") : t("rankAriaMonth")}
        detail={(i) => periodLabel(rows[i].period)}
      />
    </Card>
  );
}

/** "2026-10-27" as a small calendar chip: OCT / 27. */
function DateChip({ iso, muted = false }: { iso: string; muted?: boolean }) {
  const [day, mon] = formatDate(iso).split(" ");
  return (
    <span
      aria-hidden
      className={`flex w-10 shrink-0 flex-col items-center overflow-hidden rounded-lg border border-border text-center ${muted ? "opacity-50" : ""}`}
    >
      <span className="w-full bg-foreground/[0.05] text-[10px] leading-4 font-semibold text-muted uppercase">{mon}</span>
      <span className="text-sm leading-6 font-semibold tabular-nums">{day}</span>
    </span>
  );
}
