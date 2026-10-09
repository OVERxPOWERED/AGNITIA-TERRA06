/** Helpers to build ECharts series. Uncertainty bands use the stacked "lower + (upper-lower)" trick.
 *  The two helper series share the P50 series name, so ONE legend entry toggles the whole band,
 *  and the tooltip formatter hides the helper values (ids ending in "-lo" / "-w"). */
import type { SeriesOption } from "echarts";
import { toIST } from "@/lib/format";

export type BandPoint = { t: string; lo: number; mid: number; hi: number };

export function bandSeries(name: string, pts: BandPoint[], color: string, stack: string): SeriesOption[] {
  return [
    {
      id: `${stack}-lo`,
      name,
      type: "line",
      stack,
      data: pts.map((p) => [p.t, p.lo]),
      lineStyle: { opacity: 0 },
      itemStyle: { color },
      symbol: "none",
    },
    {
      id: `${stack}-w`,
      name,
      type: "line",
      stack,
      data: pts.map((p) => [p.t, Math.max(0, p.hi - p.lo)]),
      lineStyle: { opacity: 0 },
      itemStyle: { color },
      areaStyle: { color, opacity: 0.18 },
      symbol: "none",
    },
    {
      id: `${stack}-mid`,
      name,
      type: "line",
      data: pts.map((p) => [p.t, p.mid]),
      lineStyle: { color, width: 2.2 },
      itemStyle: { color },
      symbol: "none",
    },
  ];
}

type TipParam = {
  seriesId?: string;
  seriesName?: string;
  marker?: string;
  value?: unknown;
  axisValue?: unknown;
  color?: string;
};

import { getThemeColors, type ResolvedTheme } from "@/lib/theme";

export function timeAxisOption(unit: string, extra: Record<string, unknown> = {}, activeTheme?: ResolvedTheme) {
  const colors = getThemeColors(activeTheme);
  const isDark = activeTheme ? activeTheme === "dark" : typeof document !== "undefined" && document.documentElement.classList.contains("dark");
  const borderColor = colors.border;
  const textColor = colors.text;
  const mutedColor = colors.muted;
  const panelBg = colors.panel;
  // Soft, low-contrast gridline colors to prevent heavy lines in both themes
  const splitLineColor = isDark ? "rgba(42, 52, 74, 0.45)" : "rgba(226, 226, 220, 0.6)";

  return {
    grid: {
      left: 12,
      right: 36, // Sufficient padding to prevent "IST" axis label clipping
      top: 56, // Sufficient vertical space so top scroll legend never collides with yAxis name
      bottom: 28,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: panelBg,
      borderColor: borderColor,
      borderWidth: 1,
      padding: [10, 14],
      textStyle: {
        color: textColor,
        fontSize: 12,
        fontFamily: "var(--font-geist-sans), sans-serif",
      },
      extraCssText: "box-shadow: 0 4px 16px rgba(0, 0, 0, 0.16); border-radius: 8px;",
      formatter: (raw: unknown) => {
        const params = (Array.isArray(raw) ? raw : [raw]) as TipParam[];
        const shown = params.filter((p) => !p.seriesId?.endsWith("-lo") && !p.seriesId?.endsWith("-w"));
        const t = params[0]?.axisValue ? toIST(new Date(Number(params[0].axisValue)).toISOString()) : "";

        const rows = shown.map((p) => {
          const v = Array.isArray(p.value) ? Number(p.value[1]) : Number(p.value);
          if (p.seriesId?.endsWith("-mid")) {
            const stack = p.seriesId.replace(/-mid$/, "");
            const loParam = params.find((x) => x.seriesId === `${stack}-lo`);
            const wParam = params.find((x) => x.seriesId === `${stack}-w`);
            if (loParam && wParam) {
              const loVal = Array.isArray(loParam.value) ? Number(loParam.value[1]) : Number(loParam.value);
              const wVal = Array.isArray(wParam.value) ? Number(wParam.value[1]) : Number(wParam.value);
              const hiVal = loVal + wVal;
              return `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:3px;">
                <span>${p.marker ?? ""} ${p.seriesName}</span>
                <span style="font-variant-numeric:tabular-nums;font-weight:600;">
                  P50 ${v.toFixed(1)} ${unit} <span style="font-size:11px;opacity:0.85;font-weight:normal;">(P10 ${loVal.toFixed(1)} – P90 ${hiVal.toFixed(1)})</span>
                </span>
              </div>`;
            }
          }
          return `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:3px;">
            <span>${p.marker ?? ""} ${p.seriesName}</span>
            <span style="font-variant-numeric:tabular-nums;font-weight:600;">${v.toFixed(1)} ${unit}</span>
          </div>`;
        });

        return `<div style="font-family:var(--font-geist-sans),sans-serif;font-size:12px;">
          <div style="font-weight:600;color:${mutedColor};border-bottom:1px solid ${borderColor};padding-bottom:5px;margin-bottom:5px;">
            ${t}
          </div>
          ${rows.join("")}
        </div>`;
      },
    },
    legend: {
      top: 4,
      type: "scroll",
      left: "center",
      padding: [0, 20],
      textStyle: {
        color: isDark ? "#E2E8F0" : "#27272A", // Crisp AA contrast
        fontSize: 12,
        fontWeight: "500",
      },
    },
    xAxis: {
      type: "time",
      name: "IST",
      nameLocation: "end",
      nameGap: 8,
      nameTextStyle: { color: mutedColor, fontSize: 11, padding: [0, 0, 0, 4] },
      axisLine: { lineStyle: { color: borderColor, width: 1 } },
      axisTick: { lineStyle: { color: borderColor } },
      splitLine: {
        show: false, // Turn heavy vertical dashed lines off for clean time charts
      },
      axisLabel: {
        color: mutedColor,
        fontSize: 11,
        formatter: (v: number) =>
          new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", hour12: false }).format(v) + "h",
      },
    },
    yAxis: {
      type: "value",
      name: unit,
      nameLocation: "end",
      nameTextStyle: {
        color: mutedColor,
        fontSize: 11,
        padding: [0, 8, 4, 0],
        align: "left",
      },
      min: 0,
      axisLine: { show: false },
      splitLine: {
        show: true,
        lineStyle: { color: splitLineColor, width: 1 },
      },
      axisLabel: {
        color: mutedColor,
        fontSize: 11,
      },
    },
    ...extra,
  };
}
