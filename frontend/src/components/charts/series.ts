/** Chart helpers.
 *
 * Time: every timestamp is shifted by +5h30 and the chart runs with `useUTC: true`, so axis ticks land on real
 * IST hours (00, 06, 12, 18) whatever time zone the viewer's browser is in.
 * Bands: uncertainty is drawn with the stacked "lower + (upper - lower)" trick; the helper series share the P50
 * series' name so one legend entry toggles the whole band, and the tooltip reads P10/P90 from the points.
 */
import type { EChartsOption, SeriesOption } from "echarts";
import type { Palette } from "@/lib/theme";

const IST_MS = 330 * 60_000;
const HOUR = 3_600_000;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const pad = (n: number) => String(n).padStart(2, "0");

export const istMs = (iso: string) => Date.parse(iso) + IST_MS;
export const fmtHM = (ms: number) => `${pad(new Date(ms).getUTCHours())}:${pad(new Date(ms).getUTCMinutes())}`;
export const fmtDayHM = (ms: number) => {
  const d = new Date(ms);
  return `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]}, ${fmtHM(ms)} IST`;
};

export type BandPoint = { t: number; lo: number; mid: number; hi: number };

export interface BandOpts {
  width?: number;
  dashed?: boolean;
  bandOpacity?: number;
  showBand?: boolean;
}

/** P10-P90 band + P50 line as three series that share one name. Series ids: `${id}-lo`, `${id}-w`, `${id}-mid`. */
export function bandSeries(name: string, pts: BandPoint[], color: string, id: string, o: BandOpts = {}): SeriesOption[] {
  const out: SeriesOption[] = [];
  if (o.showBand !== false) {
    out.push(
      { id: `${id}-lo`, name, type: "line", stack: id, data: pts.map((p) => [p.t, p.lo]), lineStyle: { opacity: 0 }, itemStyle: { color }, symbol: "none", silent: true, z: 1 },
      { id: `${id}-w`, name, type: "line", stack: id, data: pts.map((p) => [p.t, Math.max(0, p.hi - p.lo)]), lineStyle: { opacity: 0 }, itemStyle: { color }, areaStyle: { color, opacity: o.bandOpacity ?? 0.14 }, symbol: "none", silent: true, z: 1 },
    );
  }
  out.push({
    id: `${id}-mid`, name, type: "line", data: pts.map((p) => [p.t, p.mid]), symbol: "none", z: 3,
    lineStyle: { color, width: o.width ?? 2.2, type: o.dashed ? "dashed" : "solid" }, itemStyle: { color }, smooth: false,
  });
  return out;
}

export function lineSeries(name: string, pts: [number, number][], color: string, o: { width?: number; dashed?: boolean; id?: string; z?: number } = {}): SeriesOption {
  return {
    id: o.id ?? `${name}-line`, name, type: "line", data: pts, symbol: "none", z: o.z ?? 2,
    lineStyle: { color, width: o.width ?? 1.6, type: o.dashed ? "dashed" : "solid" }, itemStyle: { color },
  };
}

type TipParam = { seriesId?: string; seriesName?: string; value?: unknown; dataIndex?: number; axisValue?: number | string; color?: string };

export function tooltipFor(c: Palette, unit: string, bands: Record<string, BandPoint[]> = {}) {
  return {
    trigger: "axis" as const,
    backgroundColor: c.surface,
    borderColor: c.line,
    borderWidth: 1,
    padding: [8, 10],
    extraCssText: "border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.12);",
    textStyle: { color: c.ink, fontSize: 12, fontFamily: "var(--font-geist-sans), sans-serif" },
    axisPointer: { type: "line" as const, lineStyle: { color: c.lineStrong, width: 1 } },
    formatter: (raw: unknown) => {
      const ps = (Array.isArray(raw) ? raw : [raw]) as TipParam[];
      const head = ps[0]?.axisValue != null ? fmtDayHM(Number(ps[0].axisValue)) : "";
      const rows = ps
        .filter((p) => !/-(lo|w)$/.test(p.seriesId ?? ""))
        .map((p) => {
          const v = Array.isArray(p.value) ? Number(p.value[1]) : Number(p.value);
          if (!Number.isFinite(v)) return "";
          const isMid = (p.seriesId ?? "").endsWith("-mid");
          const band = isMid ? bands[(p.seriesId ?? "").replace(/-mid$/, "")]?.[p.dataIndex ?? -1] : undefined;
          const range = band ? ` <span style="color:${c.muted}">(${band.lo.toFixed(1)} to ${band.hi.toFixed(1)})</span>` : "";
          const label = isMid ? `${p.seriesName} P50` : p.seriesName;
          return `<div style="display:flex;justify-content:space-between;gap:18px;margin-top:3px"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:6px"></span>${label}</span><span style="font-family:var(--font-geist-mono),monospace;font-variant-numeric:tabular-nums">${v.toFixed(1)} ${unit}${range}</span></div>`;
        })
        .join("");
      return `<div style="font-size:12px"><div style="color:${c.muted};margin-bottom:2px">${head}</div>${rows}</div>`;
    },
  };
}

export interface TimeChartArgs {
  c: Palette;
  unit: string;
  series: SeriesOption[];
  /** time range in shifted ms; the axis is padded half an hour each side so hourly points sit in the middle of their hour */
  tMin: number;
  tMax: number;
  bands?: Record<string, BandPoint[]>;
  legend?: boolean;
  /** pixels reserved left/right of the plot; the confidence strip uses the same numbers to line up */
  left?: number;
  right?: number;
  tickHours?: number;
  yMin?: number;
  yMax?: number;
  bottom?: number;
  extra?: Partial<EChartsOption>;
}

export const GRID_LEFT = 48;
export const GRID_RIGHT = 16;

export function timeChart(a: TimeChartArgs): EChartsOption {
  const { c } = a;
  const tick = (a.tickHours ?? 6) * HOUR;
  const label = { color: c.muted, fontSize: 11, fontFamily: "var(--font-geist-mono), monospace" };
  return {
    useUTC: true,
    backgroundColor: "transparent",
    aria: { enabled: true },
    grid: { left: a.left ?? GRID_LEFT, right: a.right ?? GRID_RIGHT, top: a.legend === false ? 16 : 44, bottom: a.bottom ?? 26, containLabel: false },
    legend: a.legend === false ? { show: false } : {
      top: 4, left: a.left ?? GRID_LEFT, type: "scroll", icon: "roundRect", itemWidth: 14, itemHeight: 4, itemGap: 18,
      textStyle: { color: c.ink, fontSize: 12, fontFamily: "var(--font-geist-sans), sans-serif" },
      pageIconColor: c.muted, pageTextStyle: { color: c.muted },
    },
    tooltip: tooltipFor(c, a.unit, a.bands),
    xAxis: {
      type: "time", min: a.tMin - HOUR / 2, max: a.tMax + HOUR / 2, minInterval: tick, maxInterval: tick,
      axisLine: { lineStyle: { color: c.line } }, axisTick: { lineStyle: { color: c.line } },
      splitLine: { show: false },
      axisLabel: {
        ...label, hideOverlap: true,
        formatter: (v: number) => {
          const d = new Date(v);
          return d.getUTCHours() === 0 ? `${pad(d.getUTCDate())} ${MONTHS[d.getUTCMonth()]}` : `${pad(d.getUTCHours())}:00`;
        },
      },
    },
    yAxis: {
      type: "value", name: a.unit, nameLocation: "end", nameGap: 12,
      nameTextStyle: { ...label, align: "right" as const }, min: a.yMin, max: a.yMax,
      axisLabel: label, axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: c.line, width: 1 } },
    },
    series: a.series,
    ...a.extra,
  };
}
