"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
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

// Colours come from CSS tokens so charts follow light/dark mode.
const COLORS = [1, 2, 3, 4, 5, 6].map((i) => `var(--chart-${i})`);
const AXIS = { stroke: "var(--muted)", fontSize: 12 };
const TOOLTIP = {
  contentStyle: { background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8 },
  labelStyle: { color: "var(--foreground)" },
  itemStyle: { color: "var(--foreground)" },
};

export function ChartView({ spec }: { spec: ChartSpec }) {
  if (spec.data.length === 0) return <p className="text-sm text-muted">No data to chart.</p>;
  return (
    <figure className="mt-2">
      {spec.title && <figcaption className="mb-2 text-sm font-medium">{spec.title}</figcaption>}
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {spec.type === "pie" ? (
            <PieChart>
              <Pie data={spec.data} dataKey={spec.y} nameKey={spec.x} outerRadius="80%" stroke="var(--card)">
                {spec.data.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip {...TOOLTIP} />
              <Legend />
            </PieChart>
          ) : spec.type === "line" ? (
            <LineChart data={spec.data}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey={spec.x} {...AXIS} />
              <YAxis {...AXIS} width={56} />
              <Tooltip {...TOOLTIP} />
              <Line type="monotone" dataKey={spec.y} stroke={COLORS[0]} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          ) : (
            <BarChart data={spec.data}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey={spec.x} {...AXIS} />
              <YAxis {...AXIS} width={56} />
              <Tooltip {...TOOLTIP} cursor={{ fill: "var(--border)", opacity: 0.4 }} />
              <Bar dataKey={spec.y} fill={COLORS[0]} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
