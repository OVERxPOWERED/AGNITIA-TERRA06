"use client";
/** Thin ECharts wrapper. Colours come from the option (built with the active palette), so a theme change simply
 *  produces a new option; the chart redraws in place. Animation runs once and is off for reduced-motion users. */
import * as echarts from "echarts";
import React, { useEffect, useRef } from "react";

export default function EChart({ option, height = 320, ariaLabel }: { option: echarts.EChartsOption; height?: number; ariaLabel: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!chart.current) chart.current = echarts.init(el, undefined, { renderer: "canvas" });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    chart.current.setOption({ animation: !reduce, animationDuration: 450, animationEasing: "cubicOut", ...option }, true);
  }, [option]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(el);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ width: "100%", height }} className="min-w-0 max-w-full" />;
}
