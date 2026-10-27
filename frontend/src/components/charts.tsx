"use client";

// Shared money charts (ECharts). Colours come from the validated tokens in globals.css via
// readTokens(), so they follow light and dark mode. Chart geometry uses minor units as floats
// for drawing only; every number a reader sees is the API's decimal string, formatted.
// Every option builder is memoised with useCallback so a re-render does not replay the
// chart's entry animation.

import type { EChartsCoreOption } from "echarts/core";
import { type ReactNode, useCallback, useMemo } from "react";
import type { BudgetStatus, DayTotal } from "@/lib/api";
import { categoryLabel, common } from "@/lib/commonMessages";
import { formatAxis, formatMoney, formatMonth, fromMinor } from "@/lib/format";
import { translate, useT } from "@/lib/i18n";
import { EChart } from "./chart/EChart";
import { type ChartTokens, axisBase, tooltipBase } from "./chart/tokens";
import { chartMessages } from "./messages";
import { Money } from "./ui";

type Amount = { total: string; total_minor: number };

const thousands = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
/** Short numbers for axis ticks: 0, 500, 1,5K, 12K (drawing only). */
function compact(value: number): string {
  return Math.abs(value) >= 1000 ? `${thousands.format(value / 1000)}K` : formatAxis(value);
}

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

// --- Category colours ---------------------------------------------------------------------
// A category keeps its colour on every chart and every month (colour follows the entity,
// never its rank). Eight slots exist, so the eight most common student categories get one
// each and the rest share the neutral "Other".

const CATEGORY_SLOTS = ["rent", "groceries", "food", "transport", "utilities", "shopping", "entertainment", "education"];

export function categoryColor(t: ChartTokens, category: string): string {
  const slot = CATEGORY_SLOTS.indexOf(category);
  return slot >= 0 ? t.series[slot] : t.other;
}

/** The same colour as a CSS value, for HTML swatches. */
export function categoryVar(category: string): string {
  const slot = CATEGORY_SLOTS.indexOf(category);
  return slot >= 0 ? `var(--series-${slot + 1})` : "var(--series-other)";
}

/** Folds categories without a slot into one "Other" row, keeping the order largest first. */
export function groupCategories<T extends { category: string } & Amount>(rows: T[]) {
  const named = rows.filter((r) => CATEGORY_SLOTS.includes(r.category));
  const rest = rows.filter((r) => !CATEGORY_SLOTS.includes(r.category));
  const out: { category: string; total_minor: number; total: string; parts: T[] }[] = named.map((r) => ({
    category: r.category,
    total_minor: r.total_minor,
    total: r.total,
    parts: [r],
  }));
  if (rest.length) {
    const minor = rest.reduce((s, r) => s + r.total_minor, 0);
    out.push({ category: "other", total_minor: minor, total: fromMinor(minor), parts: rest });
  }
  return out.sort((a, b) => b.total_minor - a.total_minor);
}

/** Swatch next to text: identity comes from the mark, the text keeps text colour. */
export function Swatch({ color }: { color: string }) {
  return <span aria-hidden className="inline-block size-2.5 shrink-0 rounded-[3px]" style={{ background: color }} />;
}

// --- Category donut ------------------------------------------------------------------------

/** Spending by category as a donut with the total in the middle and a legend list beside it. */
export function CategoryDonut({
  rows,
  total,
  currency,
}: {
  rows: ({ category: string } & Amount)[];
  total: string;
  currency: string;
}) {
  const groups = useMemo(() => groupCategories(rows), [rows]);
  const sum = groups.reduce((s, g) => s + g.total_minor, 0) || 1;
  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => ({
      tooltip: {
        ...tooltipBase(t),
        trigger: "item",
        formatter: (p: { dataIndex: number; percent: number }) => {
          const g = groups[p.dataIndex];
          const detail =
            g.parts.length > 1
              ? `<div style="margin-top:4px;color:${t.muted}">${g.parts.map((x) => `${esc(categoryLabel(x.category))} ${formatMoney(x.total, currency)}`).join("<br/>")}</div>`
              : "";
          return `<b>${formatMoney(g.total, currency)}</b> · ${Math.round(p.percent)}%<div style="color:${t.muted}">${esc(categoryLabel(g.category))}</div>${detail}`;
        },
      },
      series: [
        {
          type: "pie",
          radius: ["62%", "88%"],
          padAngle: 1.5,
          itemStyle: { borderRadius: 4, borderColor: t.card, borderWidth: 2 },
          label: { show: false },
          emphasis: { scale: true, scaleSize: 4 },
          data: groups.map((g) => ({
            name: categoryLabel(g.category),
            value: g.total_minor / 100,
            itemStyle: { color: categoryColor(t, g.category) },
          })),
        },
      ],
    }),
    [groups, currency],
  );
  const t = useT(chartMessages);
  const tc = useT(common);
  return (
    <div className="@container">
     <div className="grid items-center gap-6 @md:grid-cols-[minmax(0,12rem)_1fr]">
      <div className="relative mx-auto aspect-square w-full max-w-48">
        <EChart option={option} label={t("spendingByCategory")} className="h-full" />
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-xs text-muted">{tc("total")}</span>
          <span className="text-lg font-semibold tracking-tight">
            <Money amount={total} currency={currency} />
          </span>
        </div>
      </div>
      <ul className="flex flex-col gap-2.5 text-sm" aria-label={t("spendingByCategory")}>
        {groups.map((g) => (
          <li key={g.category} className="flex items-center gap-3">
            <Swatch color={categoryVar(g.category)} />
            <span className="min-w-0 flex-1 truncate" title={g.parts.map((p) => categoryLabel(p.category)).join(", ")}>
              {categoryLabel(g.category)}
              {g.parts.length > 1 && <span className="text-muted"> ({g.parts.length})</span>}
            </span>
            <span className="w-10 text-right text-xs text-muted tabular-nums">{Math.round((g.total_minor * 100) / sum)}%</span>
            <Money amount={g.total} currency={currency} className="w-24 text-right font-medium tabular-nums" />
          </li>
        ))}
      </ul>
     </div>
    </div>
  );
}

// --- This month vs last month -----------------------------------------------------------------

/** Running totals in minor units (exact integers). */
function cumulative(days: DayTotal[]): number[] {
  let run = 0;
  return days.map((d) => (run += d.total_minor));
}

/**
 * Running total through the month, this month against the month before. The current month
 * stops at `uptoDay` (today) so the line does not run flat into the future.
 */
export function PaceChart({
  daily,
  previous,
  uptoDay,
  monthLabel,
  previousLabel,
  currency,
}: {
  daily: DayTotal[];
  previous: DayTotal[];
  uptoDay: number;
  monthLabel: string;
  previousLabel: string;
  currency: string;
}) {
  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => {
      const days = Math.max(daily.length, previous.length);
      const cur = cumulative(daily).slice(0, uptoDay);
      const prev = cumulative(previous);
      const money = (minor: number) => formatMoney(fromMinor(minor), currency);
      return {
        grid: { left: 8, right: 84, top: 16, bottom: 8, containLabel: true }, // room for the end label
        tooltip: {
          ...tooltipBase(t),
          trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: t.axis } },
          formatter: (ps: { seriesName: string; seriesIndex: number; color: string; dataIndex: number }[]) => {
            const day = ps[0]?.dataIndex + 1;
            const rows = ps
              .map(
                (p) =>
                  `<div style="display:flex;gap:8px;align-items:center"><span style="width:10px;height:3px;border-radius:2px;background:${p.color}"></span>${esc(p.seriesName)}<b style="margin-left:auto;padding-left:12px">${money((p.seriesIndex === 0 ? prev : cur)[p.dataIndex])}</b></div>`,
              )
              .join("");
            return `<div style="color:${t.muted};margin-bottom:4px">${translate(chartMessages, "dayRunning", { day })}</div>${rows}`;
          },
        },
        xAxis: {
          type: "category",
          data: Array.from({ length: days }, (_, i) => String(i + 1)),
          boundaryGap: false,
          ...axisBase(t),
          splitLine: { show: false },
          axisLabel: { ...axisBase(t).axisLabel, interval: 4 },
        },
        yAxis: { type: "value", ...axisBase(t), axisLine: { show: false }, axisLabel: { ...axisBase(t).axisLabel, formatter: compact } },
        series: [
          {
            name: previousLabel,
            type: "line",
            data: prev.map((v) => v / 100),
            symbol: "none",
            lineStyle: { width: 2, color: t.other },
            itemStyle: { color: t.other },
            z: 1,
          },
          {
            name: monthLabel,
            type: "line",
            data: cur.map((v) => v / 100),
            symbol: "circle",
            symbolSize: 8,
            showSymbol: false,
            lineStyle: { width: 2, color: t.series[0] },
            itemStyle: { color: t.series[0], borderColor: t.card, borderWidth: 2 },
            areaStyle: { color: t.soft },
            endLabel: {
              show: cur.length > 0,
              color: t.foreground,
              fontWeight: 600,
              fontSize: 12,
              fontFamily: t.font,
              formatter: () => money(cur[cur.length - 1]),
            },
            z: 2,
          },
        ],
      };
    },
    [daily, previous, uptoDay, monthLabel, previousLabel, currency],
  );
  const t = useT(chartMessages);
  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-hidden>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded bg-[var(--series-1)]" /> {monthLabel}
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-3 rounded bg-[var(--series-other)]" /> {previousLabel}
        </li>
      </ul>
      <EChart option={option} label={t("paceLabel", { month: monthLabel, previous: previousLabel })} className="h-64" />
    </div>
  );
}

// --- Six-month trend --------------------------------------------------------------------------

/** Monthly totals as columns; the selected month is the accent, the rest a lighter step. */
export function TrendBars({
  points,
  currency,
  selected,
  onPick,
}: {
  points: ({ month: string } & Amount)[];
  currency: string;
  selected: string;
  onPick?: (month: string) => void;
}) {
  const clickable = Boolean(onPick);
  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => ({
      grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
      tooltip: {
        ...tooltipBase(t),
        trigger: "item",
        formatter: (p: { dataIndex: number }) =>
          `<b>${formatMoney(points[p.dataIndex].total, currency)}</b><div style="color:${t.muted}">${formatMonth(points[p.dataIndex].month)}</div>`,
      },
      xAxis: {
        type: "category",
        data: points.map((p) => formatMonth(p.month).slice(0, 3)),
        ...axisBase(t),
        splitLine: { show: false },
      },
      yAxis: { type: "value", ...axisBase(t), axisLine: { show: false }, axisLabel: { ...axisBase(t).axisLabel, formatter: compact } },
      series: [
        {
          type: "bar",
          barMaxWidth: 24,
          cursor: clickable ? "pointer" : "default",
          data: points.map((p) => ({
            value: p.total_minor / 100,
            itemStyle: {
              color: p.month.slice(0, 7) === selected ? t.series[0] : t.track,
              borderRadius: [4, 4, 0, 0],
            },
          })),
          label: {
            show: true,
            position: "top",
            color: t.muted,
            fontSize: 11,
            fontFamily: t.font,
            formatter: (p: { dataIndex: number }) =>
              points[p.dataIndex].month.slice(0, 7) === selected ? formatMoney(points[p.dataIndex].total, currency) : "",
          },
        },
      ],
    }),
    [points, currency, selected, clickable],
  );
  const t = useT(chartMessages);
  return (
    <EChart
      option={option}
      label={t("lastSixMonths")}
      className="h-56"
      onClick={onPick ? (p) => onPick(points[p.dataIndex].month.slice(0, 7)) : undefined}
    />
  );
}

// --- Spending calendar ----------------------------------------------------------------------

/** One square per day of the month, darker = more spent. Sequential, one hue. */
export function SpendCalendar({ daily, currency }: { daily: DayTotal[]; currency: string }) {
  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => {
      const max = Math.max(1, ...daily.map((d) => d.total_minor / 100));
      const first = daily[0]?.day ?? "2026-01-01";
      const last = daily[daily.length - 1]?.day ?? first;
      return {
        tooltip: {
          ...tooltipBase(t),
          formatter: (p: { dataIndex: number }) => {
            const d = daily[p.dataIndex];
            return `<b>${d.total_minor ? formatMoney(d.total, currency) : translate(chartMessages, "nothingSpent")}</b><div style="color:${t.muted}">${Number(d.day.slice(8))} ${formatMonth(d.day)}</div>`;
          },
        },
        visualMap: {
          show: false,
          min: 0,
          max,
          inRange: { color: t.seq },
        },
        calendar: {
          orient: "vertical",
          range: [first, last],
          left: 4,
          right: 4,
          top: 22,
          bottom: 4,
          cellSize: ["auto", "auto"],
          splitLine: { show: false },
          itemStyle: { borderColor: t.card, borderWidth: 3, color: t.seq[0] },
          dayLabel: {
            firstDay: 1,
            position: "start",
            nameMap: translate(chartMessages, "weekdaysSundayFirst").split(" "),
            color: t.axisText,
            fontSize: 11,
            fontFamily: t.font,
          },
          monthLabel: { show: false },
          yearLabel: { show: false },
        },
        series: [
          {
            type: "heatmap",
            coordinateSystem: "calendar",
            data: daily.map((d) => [d.day, d.total_minor ? d.total_minor / 100 : 0]),
            itemStyle: { borderRadius: 6 },
            label: {
              show: true,
              fontSize: 11,
              fontFamily: t.font,
              formatter: (p: { dataIndex: number }) => String(Number(daily[p.dataIndex].day.slice(8))),
              color: t.muted,
            },
          },
        ],
      };
    },
    [daily, currency],
  );
  const t = useT(chartMessages);
  return <EChart option={option} label={t("perDay")} className="h-60" />;
}

// --- Horizontal bars ------------------------------------------------------------------------

/** Ranked horizontal bars, one series (slot 1), value at the tip. Doubles as its own list. */
export function RankBars({
  rows,
  currency,
  label,
  detail,
}: {
  rows: ({ name: string } & Amount)[];
  currency: string;
  label: string;
  detail?: (index: number) => ReactNode;
}) {
  const max = Math.max(1, ...rows.map((r) => r.total_minor));
  return (
    <ul className="flex flex-col gap-3" aria-label={label}>
      {rows.map((r, i) => (
        <li key={r.name} className="flex flex-col gap-1.5 text-sm">
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate font-medium" title={r.name}>
              {r.name}
              {detail && <span className="ml-2 text-xs font-normal text-muted">{detail(i)}</span>}
            </span>
            <Money amount={r.total} currency={currency} className="tabular-nums" />
          </div>
          <span aria-hidden className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--series-1-track)]">
            <span
              className="block h-full rounded-full bg-[var(--series-1)]"
              style={{ width: `${(r.total_minor / max) * 100}%`, minWidth: 4 }}
            />
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Change per category against last month: diverging bars around zero, more = warm. */
export function CategoryChange({
  current,
  previous,
  currency,
}: {
  current: ({ category: string } & Amount)[];
  previous: ({ category: string } & Amount)[];
  currency: string;
}) {
  const rows = useMemo(() => {
    const names = Array.from(new Set([...current, ...previous].map((r) => r.category)));
    return names
      .map((category) => {
        const now = current.find((r) => r.category === category)?.total_minor ?? 0;
        const before = previous.find((r) => r.category === category)?.total_minor ?? 0;
        return { category, delta: now - before };
      })
      .filter((r) => r.delta !== 0)
      .sort((a, b) => b.delta - a.delta);
  }, [current, previous]);

  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => {
      const limit = Math.max(1, ...rows.map((r) => Math.abs(r.delta) / 100));
      const fmt = (minor: number) => `${minor > 0 ? "+" : minor < 0 ? "−" : ""}${formatMoney(fromMinor(Math.abs(minor)), currency)}`;
      return {
        grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
        tooltip: {
          ...tooltipBase(t),
          trigger: "item",
          formatter: (p: { dataIndex: number }) => {
            const r = rows[p.dataIndex];
            const note = translate(chartMessages, r.delta > 0 ? "moreThanLastMonth" : "lessThanLastMonth", {
              category: categoryLabel(r.category),
            });
            return `<b>${fmt(r.delta)}</b><div style="color:${t.muted}">${esc(note)}</div>`;
          },
        },
        xAxis: {
          type: "value",
          ...axisBase(t),
          axisLabel: { show: false },
          splitLine: { show: false },
          // Symmetric with 60% headroom so the value labels never reach the category names.
          min: -limit * 1.6,
          max: limit * 1.6,
        },
        yAxis: {
          type: "category",
          inverse: true,
          data: rows.map((r) => categoryLabel(r.category)),
          ...axisBase(t),
          axisLine: { show: false },
          splitLine: { show: false },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 14,
            data: rows.map((r) => ({
              value: r.delta / 100,
              itemStyle: {
                color: r.delta > 0 ? t.up : t.down,
                borderRadius: r.delta > 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
              },
              label: { position: r.delta > 0 ? "right" : "left" },
            })),
            label: {
              show: true,
              color: t.muted,
              fontSize: 11,
              fontFamily: t.font,
              formatter: (p: { dataIndex: number }) => fmt(rows[p.dataIndex].delta),
            },
            markLine: { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: t.axis, type: "solid" }, data: [{ xAxis: 0 }] },
          },
        ],
      };
    },
    [rows, currency],
  );
  const t = useT(chartMessages);
  if (rows.length === 0) return <p className="text-sm text-muted">{t("sameEveryCategory")}</p>;
  return (
    <div>
      <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-hidden>
        <li className="flex items-center gap-1.5">
          <Swatch color="var(--diverge-up)" /> {t("moreLegend")}
        </li>
        <li className="flex items-center gap-1.5">
          <Swatch color="var(--diverge-down)" /> {t("lessLegend")}
        </li>
      </ul>
      <div style={{ height: Math.max(120, rows.length * 32) }}>
        <EChart option={option} label={t("changeLabel")} className="h-full" />
      </div>
    </div>
  );
}

// --- Sparkline ------------------------------------------------------------------------------

/** A tiny line for stat cards, no axes. */
export function Sparkline({ values, label }: { values: number[]; label: string }) {
  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => ({
      grid: { left: 0, right: 0, top: 2, bottom: 2 },
      xAxis: { type: "category", show: false, boundaryGap: false, data: values.map((_, i) => i) },
      yAxis: { type: "value", show: false, min: 0 },
      series: [
        {
          type: "line",
          data: values,
          symbol: "none",
          lineStyle: { width: 2, color: t.series[0] },
          areaStyle: { color: t.soft },
          silent: true,
        },
      ],
      animation: false,
    }),
    [values],
  );
  return <EChart option={option} label={label} className="h-10" />;
}

// --- Budget meter (HTML) ----------------------------------------------------------------------

const LEVEL = {
  ok: { fill: "var(--series-1)", label: "onTrack", icon: "✓", text: "text-muted" },
  warning: { fill: "var(--status-warning)", label: "closeToLimit", icon: "!", text: "text-warning" },
  exceeded: { fill: "var(--status-critical)", label: "overLimit", icon: "×", text: "text-danger" },
} as const;

/** One budget: a meter whose fill carries the state, plus an icon and a label. */
export function BudgetMeter({ status, actions }: { status: BudgetStatus; actions?: ReactNode }) {
  const b = status.budget;
  const t = useT(chartMessages);
  const level = LEVEL[status.level];
  const levelLabel = t(level.label);
  const name = b.category ? categoryLabel(b.category) : t("overall");
  const width = Math.min(100, Math.max(0, status.pct_used));
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
        <span className="font-medium">{name}</span>
        <span className="text-muted">
          <Money amount={status.spent} currency={b.currency} className="text-foreground" /> {t("of")}{" "}
          <Money amount={b.limit} currency={b.currency} />
        </span>
      </div>
      <div
        role="meter"
        aria-label={t("budgetUsed", { name })}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(status.pct_used, 100)}
        aria-valuetext={t("usedText", { pct: status.pct_used, level: levelLabel })}
        className="relative h-2 overflow-hidden rounded-full bg-[var(--series-1-track)]"
      >
        <span className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${width}%`, background: level.fill }} />
        <span
          aria-hidden
          title={t("alertAt", { pct: b.alert_threshold_pct })}
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
          {levelLabel} · {status.pct_used}%
        </span>
        <span className="ml-auto text-muted">
          {status.remaining_minor >= 0 ? (
            <>
              <Money amount={status.remaining} currency={b.currency} /> {t("left")}
            </>
          ) : (
            <>
              <Money amount={status.remaining.replace(/^-/, "")} currency={b.currency} /> {t("over")}
            </>
          )}
        </span>
      </div>
      {actions}
    </div>
  );
}
