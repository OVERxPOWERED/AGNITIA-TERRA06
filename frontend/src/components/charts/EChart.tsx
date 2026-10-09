"use client";
/** ECharts wrapper: theme-aware, responsive resize, reduced-motion respecting. */
import * as echarts from "echarts";
import React, { useEffect, useRef } from "react";
import { useTheme } from "@/lib/theme";

export default function EChart({
  option,
  height = 320,
  ariaLabel,
}: {
  option: object;
  height?: number;
  ariaLabel: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const { resolvedTheme } = useTheme();

  const prevTheme = useRef<string | null>(null);

  // Initialize or update chart when DOM mounts, theme changes, or option changes
  useEffect(() => {
    if (!ref.current) return;

    const isDark = resolvedTheme === "dark";

    if (chart.current && prevTheme.current !== resolvedTheme) {
      chart.current.dispose();
      chart.current = null;
    }
    prevTheme.current = resolvedTheme;

    if (!chart.current) {
      chart.current = echarts.init(ref.current, isDark ? "dark" : undefined, {
        renderer: "canvas",
      });
      (ref.current as HTMLElement & { __echarts_instance__?: echarts.ECharts }).__echarts_instance__ = chart.current;
    }

    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    chart.current.setOption(
      {
        backgroundColor: "transparent",
        animation: !reducedMotion,
        animationDuration: 500,
        animationEasing: "cubicOut",
        aria: { enabled: true },
        ...option,
      } as echarts.EChartsOption,
      true
    );

    const ro = new ResizeObserver(() => {
      chart.current?.resize();
    });
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
    };
  }, [resolvedTheme, option]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  return (
    <div
      ref={ref}
      role="img"
      aria-label={ariaLabel}
      style={{ width: "100%", height }}
      className="min-w-0 max-w-full overflow-hidden"
    />
  );
}
