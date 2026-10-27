"use client";

import type { EChartsCoreOption } from "echarts/core";
import { useCallback, useMemo } from "react";
import { Swatch } from "@/components/charts";
import { EChart } from "@/components/chart/EChart";
import { type ChartTokens, axisBase, tooltipBase } from "@/components/chart/tokens";
import type { ChartSpec } from "@/lib/api";
import { categoryLabel } from "@/lib/commonMessages";
import { formatAxis, formatNumber } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { messages } from "./messages";

// Charts the report agent asks for. Categorical slots in fixed order (validated palette in
// globals.css). A pie keeps at most six slices; the rest fold into "Other" so no colour is
// ever reused.
const MAX_SLICES = 6;

type Row = ChartSpec["data"][number];

const toNumber = (v: unknown): number => {
  const n = typeof v === "number" ? v : Number(String(v ?? "").replace(",", "."));
  return Number.isFinite(n) ? n : 0;
};
const label = (s: string) => s.replace(/_/g, " ");
const cellText = (v: Row[string]) =>
  v === null || v === undefined ? "" : typeof v === "number" ? formatNumber(v) : String(v);
const esc = (s: string) => s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

export function DataTable({ spec }: { spec: ChartSpec }) {
  const columns = spec.columns?.length ? spec.columns : Array.from(new Set(spec.data.flatMap((r) => Object.keys(r))));
  return (
    <div className="max-h-80 overflow-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-card text-xs text-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="border-b border-border px-3 py-2 font-medium capitalize">
                {label(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.data.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0 hover:bg-foreground/[0.03]">
              {columns.map((c) => (
                <td key={c} className={`px-3 py-1.5 ${typeof row[c] === "number" ? "text-right tabular-nums" : ""}`}>
                  {cellText(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ChartView({ spec }: { spec: ChartSpec }) {
  const t = useT(messages);
  const points = useMemo(
    () =>
      spec.data.map((r) => {
        const raw = String(r[spec.x] ?? "");
        // Category keys from the database ("groceries") read as words in the UI language.
        return { x: spec.x === "category" ? categoryLabel(raw) : raw, y: toNumber(r[spec.y]) };
      }),
    [spec],
  );
  const slices = useMemo(() => {
    if (spec.type !== "pie" || points.length <= MAX_SLICES) return points;
    const sorted = [...points].sort((a, b) => b.y - a.y);
    const rest = sorted.slice(MAX_SLICES - 1).reduce((sum, p) => sum + p.y, 0);
    return [...sorted.slice(0, MAX_SLICES - 1), { x: "Other", y: rest }];
  }, [spec.type, points]);
  const yName = label(spec.y);

  const option = useCallback(
    (t: ChartTokens): EChartsCoreOption => {
      const tooltip = {
        ...tooltipBase(t),
        trigger: "item" as const,
        formatter: (p: { name: string; value: number }) =>
          `<b>${formatNumber(p.value)}</b><div style="color:${t.muted}">${esc(p.name)} · ${esc(yName)}</div>`,
      };
      if (spec.type === "pie") {
        return {
          tooltip,
          series: [
            {
              type: "pie",
              radius: ["55%", "85%"],
              padAngle: 1.5,
              itemStyle: { borderRadius: 4, borderColor: t.card, borderWidth: 2 },
              label: { show: false },
              data: slices.map((s, i) => ({
                name: s.x,
                value: s.y,
                itemStyle: { color: s.x === "Other" && i === MAX_SLICES - 1 ? t.other : t.series[i] },
              })),
            },
          ],
        };
      }
      const line = spec.type === "line";
      return {
        grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
        tooltip: line ? { ...tooltip, trigger: "axis", axisPointer: { lineStyle: { color: t.axis } } } : tooltip,
        xAxis: {
          type: "category",
          data: points.map((p) => p.x),
          boundaryGap: !line,
          ...axisBase(t),
          splitLine: { show: false },
          // Every label, tilted when there are many bars, rather than every other one.
          axisLabel: {
            ...axisBase(t).axisLabel,
            interval: 0,
            rotate: points.length > 6 ? 30 : 0,
            hideOverlap: true,
          },
        },
        yAxis: {
          type: "value",
          ...axisBase(t),
          axisLine: { show: false },
          axisLabel: { ...axisBase(t).axisLabel, formatter: (v: number) => formatAxis(v) },
        },
        series: [
          line
            ? {
                type: "line",
                name: yName,
                data: points.map((p) => p.y),
                symbol: "circle",
                symbolSize: 8,
                lineStyle: { width: 2, color: t.series[0] },
                itemStyle: { color: t.series[0], borderColor: t.card, borderWidth: 2 },
                areaStyle: { color: t.soft },
              }
            : {
                type: "bar",
                name: yName,
                barMaxWidth: 24,
                data: points.map((p) => p.y),
                itemStyle: { color: t.series[0], borderRadius: [4, 4, 0, 0] },
              },
        ],
      };
    },
    [spec.type, points, slices, yName],
  );

  if (spec.data.length === 0) return <p className="mt-2 text-sm text-muted">{t("noData")}</p>;

  if (spec.type === "table") {
    return (
      <figure className="mt-3">
        {spec.title && <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>}
        <DataTable spec={spec} />
      </figure>
    );
  }

  return (
    <div className="mt-3 rounded-xl border border-border p-3 sm:p-4">
      {spec.title && <p className="mb-2 text-sm font-medium">{spec.title}</p>}
      <EChart option={option} label={spec.title || `Chart of ${yName}`} className="h-64" />
      {spec.type === "pie" && (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Legend">
          {slices.map((s, i) => (
            <li key={i} className="flex items-center gap-1.5">
              <Swatch color={s.x === "Other" && i === MAX_SLICES - 1 ? "var(--series-other)" : `var(--series-${i + 1})`} />
              {s.x} <span className="text-muted tabular-nums">{formatNumber(s.y)}</span>
            </li>
          ))}
        </ul>
      )}
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted hover:text-foreground">{t("showTable")}</summary>
        <div className="mt-2">
          <DataTable spec={spec} />
        </div>
      </details>
    </div>
  );
}
