"use client";

// Spent against the limit for every budget, as a share of its own limit. Budgets differ a lot
// in size (an overall limit next to a small category), so the axis is "% of the limit" and
// the limit itself is the vertical line at 100%. Bar colour carries the budget's state, and
// every bar also has an icon and the percentage as text, so colour is never the only cue.

import type { EChartsCoreOption } from "echarts/core";
import { useCallback } from "react";
import { Swatch } from "@/components/charts";
import { EChart } from "@/components/chart/EChart";
import { type ChartTokens, axisBase, tooltipBase } from "@/components/chart/tokens";
import type { BudgetStatus } from "@/lib/api";
import { categoryLabel } from "@/lib/commonMessages";
import { formatMoney } from "@/lib/format";
import { translate, useLocale, useT } from "@/lib/i18n";
import { messages } from "./messages";

export const LEVELS = {
  ok: { icon: "✓", css: "var(--series-1)" },
  warning: { icon: "!", css: "var(--status-warning)" },
  exceeded: { icon: "×", css: "var(--status-critical)" },
} as const;

function levelColor(t: ChartTokens, level: BudgetStatus["level"]): string {
  return level === "exceeded" ? t.critical : level === "warning" ? t.warning : t.series[0];
}

type Key = keyof (typeof messages)["en"] & string;

const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

/** "Groceries" / "Market", or "Overall" / "Genel" for the budget without a category. */
export const budgetName = (s: BudgetStatus) =>
  s.budget.category ? categoryLabel(s.budget.category) : translate(messages, "overall");

export function BudgetChart({ rows }: { rows: BudgetStatus[] }) {
  const t = useT(messages);
  const locale = useLocale(); // the builder translates with translate(); rebuild when the language changes
  const option = useCallback(
    (c: ChartTokens): EChartsCoreOption => {
      const tr = (key: Key, vars?: Record<string, string | number>) => translate(messages, key, vars);
      const names = rows.map(budgetName);
      const top = Math.max(100, ...rows.map((r) => r.pct_used));
      // Headroom past the longest bar so its label never clips.
      const max = Math.ceil((top * 1.2) / 25) * 25;
      return {
        grid: { left: 8, right: 24, top: 28, bottom: 4, containLabel: true },
        tooltip: {
          ...tooltipBase(c),
          trigger: "item",
          formatter: (p: { dataIndex: number }) => {
            const r = rows[p.dataIndex];
            const level = LEVELS[r.level];
            return (
              `<b>${esc(names[p.dataIndex])}</b>` +
              `<div>${esc(tr("tooltipOf", { spent: formatMoney(r.spent, r.budget.currency), limit: formatMoney(r.budget.limit, r.budget.currency) }))}</div>` +
              `<div style="color:${c.muted}">${esc(tr("tooltipLevel", { icon: level.icon, label: tr(`level.${r.level}`), pct: r.pct_used }))}</div>`
            );
          },
        },
        xAxis: {
          type: "value",
          min: 0,
          max,
          ...axisBase(c),
          axisLine: { show: false },
          axisLabel: { ...axisBase(c).axisLabel, formatter: (v: number) => tr("pct", { v }) },
        },
        yAxis: {
          type: "category",
          inverse: true,
          data: names,
          ...axisBase(c),
          splitLine: { show: false },
        },
        series: [
          {
            type: "bar",
            barMaxWidth: 16,
            data: rows.map((r) => ({
              value: r.pct_used,
              itemStyle: { color: levelColor(c, r.level), borderRadius: [0, 4, 4, 0] },
            })),
            label: {
              show: true,
              position: "right",
              color: c.muted,
              fontSize: 11,
              fontFamily: c.font,
              formatter: (p: { dataIndex: number }) =>
                `${LEVELS[rows[p.dataIndex].level].icon} ${tr("pct", { v: rows[p.dataIndex].pct_used })}`,
            },
            markLine: {
              silent: true,
              symbol: "none",
              lineStyle: { color: c.foreground, opacity: 0.45, type: "solid", width: 1 },
              label: { show: true, position: "end", formatter: tr("limit"), color: c.muted, fontSize: 11, fontFamily: c.font },
              data: [{ xAxis: 100 }],
            },
          },
        ],
      };
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- locale is read through translate()
    [rows, locale],
  );

  const levels = (Object.keys(LEVELS) as BudgetStatus["level"][]).filter((l) => rows.some((r) => r.level === l));
  return (
    <div>
      <ul className="mb-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted" aria-hidden>
        {levels.map((l) => (
          <li key={l} className="flex items-center gap-1.5">
            <Swatch color={LEVELS[l].css} /> {LEVELS[l].icon} {t(`level.${l}`)}
          </li>
        ))}
      </ul>
      <div style={{ height: Math.max(150, rows.length * 44 + 40) }}>
        <EChart option={option} label={t("chartAria")} className="h-full" />
      </div>
    </div>
  );
}
