"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartSpec } from "@/lib/api";
import { formatAxis, formatNumber } from "@/lib/format";

// Categorical slots in fixed order (validated palette in globals.css). A pie keeps at most six
// slices; the rest fold into "Other" so no colour is ever reused.
const SERIES = [1, 2, 3, 4, 5, 6].map((i) => `var(--series-${i})`);
const MAX_SLICES = 6;
const AXIS = { stroke: "var(--axis)", tick: { fill: "var(--axis-text)", fontSize: 12 }, tickLine: false };

type Row = ChartSpec["data"][number];

const toNumber = (v: unknown): number => {
  const n = typeof v === "number" ? v : Number(String(v ?? "").replace(",", "."));
  return Number.isFinite(n) ? n : 0;
};
const label = (s: string) => s.replace(/_/g, " ");
const cellText = (v: Row[string]) =>
  v === null || v === undefined ? "" : typeof v === "number" ? formatNumber(v) : String(v);

function ChartTooltip({ active, payload, name }: { active?: boolean; payload?: { payload?: Record<string, unknown> }[]; name: string }) {
  const p = payload?.[0]?.payload as { _x: string; _y: number } | undefined;
  if (!active || !p) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-md">
      <p className="font-semibold">{formatNumber(p._y)}</p>
      <p className="text-muted">
        {p._x} · {name}
      </p>
    </div>
  );
}

export function DataTable({ spec }: { spec: ChartSpec }) {
  const columns = spec.columns?.length ? spec.columns : Array.from(new Set(spec.data.flatMap((r) => Object.keys(r))));
  return (
    <div className="max-h-80 overflow-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-card text-xs text-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="border-b border-border px-3 py-2 font-medium">
                {label(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {spec.data.map((row, i) => (
            <tr key={i} className="border-b border-border last:border-0">
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
  if (spec.data.length === 0) return <p className="mt-2 text-sm text-muted">No data to show.</p>;

  if (spec.type === "table") {
    return (
      <figure className="mt-3">
        {spec.title && <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>}
        <DataTable spec={spec} />
      </figure>
    );
  }

  const points = spec.data.map((r) => ({ _x: String(r[spec.x] ?? ""), _y: toNumber(r[spec.y]) }));
  let slices = points;
  if (spec.type === "pie" && points.length > MAX_SLICES) {
    const sorted = [...points].sort((a, b) => b._y - a._y);
    const rest = sorted.slice(MAX_SLICES - 1).reduce((sum, p) => sum + p._y, 0);
    slices = [...sorted.slice(0, MAX_SLICES - 1), { _x: "Other", _y: rest }];
  }
  const yName = label(spec.y);

  return (
    <figure className="mt-3">
      {spec.title && <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "pie" ? (
            <PieChart accessibilityLayer>
              <Pie
                data={slices}
                dataKey="_y"
                nameKey="_x"
                innerRadius="55%"
                outerRadius="85%"
                stroke="var(--card)"
                strokeWidth={2}
                isAnimationActive={false}
              >
                {slices.map((_, i) => (
                  <Cell key={i} fill={SERIES[i]} />
                ))}
              </Pie>
              <Tooltip content={<ChartTooltip name={yName} />} />
            </PieChart>
          ) : spec.type === "line" ? (
            <LineChart data={points} margin={{ top: 12, right: 16, bottom: 0, left: 0 }} accessibilityLayer>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="_x" {...AXIS} interval="preserveStartEnd" />
              <YAxis {...AXIS} axisLine={false} width={56} tickFormatter={(v: number) => formatAxis(v)} />
              <Tooltip cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} content={<ChartTooltip name={yName} />} />
              <Line
                type="monotone"
                dataKey="_y"
                stroke={SERIES[0]}
                strokeWidth={2}
                dot={{ r: 4, fill: SERIES[0], stroke: "var(--card)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            </LineChart>
          ) : (
            <BarChart data={points} margin={{ top: 12, right: 16, bottom: 0, left: 0 }} accessibilityLayer>
              <CartesianGrid stroke="var(--grid)" vertical={false} />
              <XAxis dataKey="_x" {...AXIS} interval="preserveStartEnd" />
              <YAxis {...AXIS} axisLine={false} width={56} tickFormatter={(v: number) => formatAxis(v)} />
              <Tooltip cursor={{ fill: "var(--foreground)", opacity: 0.05 }} content={<ChartTooltip name={yName} />} />
              <Bar dataKey="_y" fill={SERIES[0]} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
      {spec.type === "pie" && (
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Legend">
          {slices.map((s, i) => (
            <li key={i} className="flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-sm" style={{ background: SERIES[i] }} />
              {s._x} <span className="text-muted tabular-nums">{formatNumber(s._y)}</span>
            </li>
          ))}
        </ul>
      )}
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-muted">Show as table</summary>
        <div className="mt-2">
          <DataTable spec={spec} />
        </div>
      </details>
    </figure>
  );
}
