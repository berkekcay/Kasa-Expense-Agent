// Design tokens for chart code. ECharts draws with plain colour strings, so the CSS
// variables from globals.css are read once per theme change.

export type ChartTokens = {
  series: string[]; // the 8 categorical slots, fixed order
  other: string; // the "Other" bucket, neutral
  seq: string[]; // sequential ramp, light to dark (magnitude)
  up: string; // diverging: more than before
  down: string; // diverging: less than before
  good: string;
  warning: string;
  critical: string;
  track: string;
  soft: string; // series 1 at ~10% for area washes
  card: string;
  foreground: string;
  muted: string;
  border: string;
  grid: string;
  axis: string;
  axisText: string;
  font: string;
};

export function readTokens(): ChartTokens {
  const css = getComputedStyle(document.documentElement);
  const v = (name: string) => css.getPropertyValue(name).trim();
  return {
    series: [1, 2, 3, 4, 5, 6, 7, 8].map((n) => v(`--series-${n}`)),
    other: v("--series-other"),
    seq: [0, 1, 2, 3, 4, 5].map((n) => v(`--seq-${n}`)),
    up: v("--diverge-up"),
    down: v("--diverge-down"),
    good: v("--status-good"),
    warning: v("--status-warning"),
    critical: v("--status-critical"),
    track: v("--series-1-track"),
    soft: v("--series-1-soft"),
    card: v("--card"),
    foreground: v("--foreground"),
    muted: v("--muted"),
    border: v("--border"),
    grid: v("--grid"),
    axis: v("--axis"),
    axisText: v("--axis-text"),
    font: getComputedStyle(document.body).fontFamily,
  };
}

/** Shared tooltip look: a card with a hairline border, text in text tokens. */
export function tooltipBase(t: ChartTokens) {
  return {
    backgroundColor: t.card,
    borderColor: t.border,
    borderWidth: 1,
    padding: [8, 12],
    textStyle: { color: t.foreground, fontFamily: t.font, fontSize: 13 },
    extraCssText: "border-radius:10px;box-shadow:0 8px 24px -6px rgb(0 0 0 / .25);",
  };
}

/** Recessive category / value axes: hairline solid grid, muted 12px labels. */
export function axisBase(t: ChartTokens) {
  return {
    axisLine: { lineStyle: { color: t.axis } },
    axisTick: { show: false },
    axisLabel: { color: t.axisText, fontSize: 12, fontFamily: t.font },
    splitLine: { lineStyle: { color: t.grid, width: 1, type: "solid" as const } },
  };
}
