"use client";
/** Minimal ECharts wrapper: init once, update on option change, resize with the container. */
import * as echarts from "echarts";
import { useEffect, useRef } from "react";

/** `option` is typed loosely on purpose: ECharts' literal types are strict and slow down beginners. */
export default function EChart({ option, height = 320, ariaLabel }: {
  option: object; height?: number; ariaLabel: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    chart.current = echarts.init(ref.current, dark ? "dark" : undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); chart.current?.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    chart.current?.setOption({ backgroundColor: "transparent", aria: { enabled: true }, ...option } as echarts.EChartsOption, true);
  }, [option]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ width: "100%", height }} />;
}
