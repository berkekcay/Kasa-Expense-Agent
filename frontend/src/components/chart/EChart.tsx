"use client";

import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { useEffect, useRef, useState } from "react";
import { useResolvedTheme } from "@/lib/theme";
import { type ChartTokens, readTokens } from "./tokens";

type Props = {
  /** Builds the option from the current theme's tokens. Called again when the theme changes. */
  option: (t: ChartTokens) => EChartsCoreOption;
  /** Accessible name; the chart canvas itself is hidden from screen readers. */
  label: string;
  className?: string;
  onClick?: (params: { name: string; dataIndex: number; seriesIndex: number; data: unknown }) => void;
};

/**
 * One ECharts chart. Loads echarts lazily, follows the light/dark theme, resizes with its
 * box. Charts are for reading at a glance; every chart in Kasa also has the numbers in
 * text (a list, a table or the tooltip) for screen readers and for copying.
 */
export function EChart({ option, label, className = "h-64", onClick }: Props) {
  const box = useRef<HTMLDivElement | null>(null);
  const chart = useRef<EChartsType | null>(null);
  const theme = useResolvedTheme();
  const [ready, setReady] = useState(false);
  const optionRef = useRef(option);
  const clickRef = useRef(onClick);
  useEffect(() => {
    optionRef.current = option;
    clickRef.current = onClick;
  });

  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
    void import("./setup").then(({ echarts }) => {
      if (disposed || !box.current) return;
      const instance = echarts.init(box.current, null, { renderer: "svg" });
      chart.current = instance;
      instance.on("click", (p) => clickRef.current?.(p as Parameters<NonNullable<Props["onClick"]>>[0]));
      observer = new ResizeObserver(() => instance.resize());
      observer.observe(box.current);
      setReady(true);
    });
    return () => {
      disposed = true;
      observer?.disconnect();
      chart.current?.dispose();
      chart.current = null;
      setReady(false);
    };
  }, []);

  useEffect(() => {
    if (!ready || !chart.current) return;
    const t = readTokens();
    chart.current.setOption({ animationDuration: 400, ...optionRef.current(t) }, { notMerge: true });
  }, [ready, theme, option]);

  return (
    <figure aria-label={label} className={`relative w-full min-w-0 ${className}`}>
      <div ref={box} aria-hidden className="absolute inset-0" />
      {!ready && <div aria-hidden className="skeleton absolute inset-0 rounded-lg opacity-40" />}
    </figure>
  );
}
