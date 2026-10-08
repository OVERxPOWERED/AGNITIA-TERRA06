/** Helpers to build ECharts series. Uncertainty bands use the stacked "lower + (upper-lower)" trick.
 *  The two helper series share the P50 series name, so ONE legend entry toggles the whole band,
 *  and the tooltip formatter hides the helper values (ids ending in "-lo" / "-w"). */
import type { SeriesOption } from "echarts";
import { toIST } from "@/lib/format";

export type BandPoint = { t: string; lo: number; mid: number; hi: number };

export function bandSeries(name: string, pts: BandPoint[], color: string, stack: string): SeriesOption[] {
  return [
    { id: `${stack}-lo`, name, type: "line", stack, data: pts.map((p) => [p.t, p.lo]), lineStyle: { opacity: 0 },
      itemStyle: { color }, symbol: "none" },
    { id: `${stack}-w`, name, type: "line", stack, data: pts.map((p) => [p.t, p.hi - p.lo]), lineStyle: { opacity: 0 },
      itemStyle: { color }, areaStyle: { color, opacity: 0.2 }, symbol: "none" },
    { id: `${stack}-mid`, name, type: "line", data: pts.map((p) => [p.t, p.mid]), lineStyle: { color, width: 2 },
      itemStyle: { color }, symbol: "none" },
  ];
}

type TipParam = { seriesId?: string; seriesName?: string; marker?: string; value?: unknown; axisValue?: unknown };

export function timeAxisOption(unit: string, extra: Record<string, unknown> = {}) {
  return {
    grid: { left: 48, right: 36, top: 40, bottom: 40 },
    tooltip: {
      trigger: "axis",
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
              return `${p.marker ?? ""} ${p.seriesName}: <b>P50 ${v.toFixed(1)} ${unit} (P10 ${loVal.toFixed(1)} – P90 ${hiVal.toFixed(1)})</b>`;
            }
          }
          return `${p.marker ?? ""} ${p.seriesName}: <b>${v.toFixed(1)} ${unit}</b>`;
        });
        return [t, ...rows].join("<br/>");
      },
    },
    legend: { top: 0, type: "scroll", left: 60, right: 60 },
    xAxis: { type: "time", name: "IST", axisLabel: { formatter: (v: number) =>
      new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", hour12: false }).format(v) + "h" } },
    yAxis: { type: "value", name: unit, min: 0 },
    ...extra,
  };
}
