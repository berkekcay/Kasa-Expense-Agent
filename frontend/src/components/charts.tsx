"use client";

// Shared money charts. Colours come from the validated --series-* tokens and the reserved
// --status-* tokens in globals.css, so they follow light and dark mode.
// Bar lengths and line positions use minor units as floats for drawing only; every number a
// reader sees is the API's decimal string, formatted.

import type { ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { BudgetStatus } from "@/lib/api";
import { capitalize, formatAxis, formatMoney, formatMonth } from "@/lib/format";
import { Money } from "./ui";

/** Horizontal bars, one series (slot 1), value at the tip. Doubles as its own table. */
export function CategoryBars({
  rows,
  currency,
}: {
  rows: { category: string; total: string; total_minor: number }[];
  currency: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.total_minor));
  return (
    <ul className="flex flex-col gap-2.5" aria-label="Spending by category">
      {rows.map((r) => (
        <li key={r.category} className="grid grid-cols-[6rem_1fr] items-center gap-3 text-sm sm:grid-cols-[8rem_1fr]">
          <span className="truncate text-muted" title={capitalize(r.category)}>
            {capitalize(r.category)}
          </span>
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden
              className="h-3 shrink-0 rounded-r-[4px] bg-[var(--series-1)]"
              style={{ width: `calc((100% - 7.5rem) * ${r.total_minor / max})`, minWidth: 2 }}
            />
            <Money amount={r.total} currency={currency} className="tabular-nums" />
          </span>
        </li>
      ))}
    </ul>
  );
}

type TrendPoint = { month: string; total: string; total_minor: number };

/** Six-month spending line. Single series, so no legend; tooltip plus a table view. */
export function TrendChart({ points, currency }: { points: TrendPoint[]; currency: string }) {
  const data = points.map((p) => ({ label: formatMonth(p.month), value: p.total_minor / 100, total: p.total }));
  return (
    <figure>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 16, bottom: 0, left: 0 }} accessibilityLayer>
            <CartesianGrid stroke="var(--grid)" vertical={false} />
            <XAxis
              dataKey="label"
              stroke="var(--axis)"
              tick={{ fill: "var(--axis-text)", fontSize: 12 }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              stroke="var(--axis)"
              tick={{ fill: "var(--axis-text)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={56}
              tickFormatter={(v: number) => formatAxis(v)}
            />
            <Tooltip
              cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
              content={({ active, payload }) => {
                const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
                if (!active || !p) return null;
                return (
                  <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-md">
                    <p className="font-semibold">{formatMoney(p.total, currency)}</p>
                    <p className="text-muted">{p.label}</p>
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--series-1)"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={{ r: 4, fill: "var(--series-1)", stroke: "var(--card)", strokeWidth: 2 }}
              activeDot={{ r: 5, fill: "var(--series-1)", stroke: "var(--card)", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted">Show as table</summary>
        <table className="mt-2 w-full">
          <thead className="text-left text-xs text-muted">
            <tr>
              <th className="py-1 font-medium">Month</th>
              <th className="py-1 text-right font-medium">Spent</th>
            </tr>
          </thead>
          <tbody className="tabular-nums">
            {points.map((p) => (
              <tr key={p.month} className="border-t border-border">
                <td className="py-1">{formatMonth(p.month)}</td>
                <td className="py-1 text-right">{formatMoney(p.total, currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

const LEVEL = {
  ok: { fill: "var(--series-1)", label: "On track", icon: "✓", text: "text-muted" },
  warning: { fill: "var(--status-warning)", label: "Close to limit", icon: "!", text: "text-warning" },
  exceeded: { fill: "var(--status-critical)", label: "Over limit", icon: "×", text: "text-danger" },
} as const;

/** One budget: a meter whose fill carries the state, plus an icon and a label. */
export function BudgetMeter({ status, actions }: { status: BudgetStatus; actions?: ReactNode }) {
  const b = status.budget;
  const level = LEVEL[status.level];
  const name = b.category ? capitalize(b.category) : "Overall";
  const width = Math.min(100, Math.max(0, status.pct_used));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
        <span className="font-medium">{name}</span>
        <span className="text-muted">
          <Money amount={status.spent} currency={b.currency} className="text-foreground" /> of{" "}
          <Money amount={b.limit} currency={b.currency} />
        </span>
      </div>
      <div
        role="meter"
        aria-label={`${name} budget used`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(status.pct_used, 100)}
        aria-valuetext={`${status.pct_used}% used, ${level.label}`}
        className="relative h-2.5 overflow-hidden rounded-full bg-[var(--series-1-track)]"
      >
        <span
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${width}%`, background: level.fill }}
        />
        <span
          aria-hidden
          title={`Alert at ${b.alert_threshold_pct}%`}
          className="absolute inset-y-0 w-0.5 bg-foreground/40"
          style={{ left: `${b.alert_threshold_pct}%` }}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className={`inline-flex items-center gap-1.5 font-medium ${level.text}`}>
          <span
            aria-hidden
            className="flex size-4 items-center justify-center rounded-full text-[10px] font-bold text-white"
            style={{ background: level.fill === "var(--series-1)" ? "var(--status-good)" : level.fill }}
          >
            {level.icon}
          </span>
          {level.label} · {status.pct_used}%
        </span>
        <span className="ml-auto text-muted">
          {status.remaining_minor >= 0 ? (
            <>
              <Money amount={status.remaining} currency={b.currency} /> left
            </>
          ) : (
            <>
              <Money amount={status.remaining.replace(/^-/, "")} currency={b.currency} /> over
            </>
          )}
        </span>
      </div>
      {actions}
    </div>
  );
}
