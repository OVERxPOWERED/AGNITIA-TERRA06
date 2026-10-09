"use client";
/** Weather second opinions: the served forecast against the plant's physics output under each weather model. */
import React, { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, istMs, lineSeries, timeChart, type BandPoint } from "@/components/charts/series";
import { Pill, Segmented } from "@/components/ui/primitives";
import type { LocationResult } from "@/lib/api/types";
import { useTheme } from "@/lib/theme";

type Src = "hybrid_mw" | "solar_mw" | "wind_mw";
const DASH = ["dashed", "dotted", "solid"] as const;

export default function SecondOpinions({ r }: { r: LocationResult }) {
  const { colors: c } = useTheme();
  const [src, setSrc] = useState<Src>("hybrid_mw");
  const models = r.second_opinions.filter((m) => m.points.length);
  const key = src === "hybrid_mw" ? "hybrid" : src === "solar_mw" ? "solar" : "wind";

  const option = useMemo(() => {
    const pts = r[key];
    if (!pts.length) return null;
    const band: BandPoint[] = pts.map((p) => ({ t: istMs(p.target_time_utc), lo: p.q10, mid: p.q50, hi: p.q90 }));
    const tone = [c.solar, c.wind, c.battery, c.demand, c.backup];
    const lines = models.map((m, i) => lineSeries(`${m.label} (physics)`, m.points.filter((p) => p[src] != null).map((p) => [istMs(p.target_time_utc), p[src] as number]),
      tone[i % tone.length], { width: 1.4, dashed: DASH[i % 3] !== "solid", id: `wm-${m.id}` }));
    return timeChart({ c, unit: "MW", tMin: band[0].t, tMax: band[band.length - 1].t, bands: { f: band },
      series: [...bandSeries("Vidyut forecast", band, c.hybrid, "f", { width: 2.4, bandOpacity: 0.12 }), ...lines] });
  }, [r, key, src, models, c]);

  const spread = useMemo(() => {
    if (models.length < 2) return null;
    const n = models[0].points.length;
    let worst = 0;
    for (let i = 0; i < n; i++) {
      const v = models.map((m) => m.points[i]?.hybrid_mw).filter((x): x is number => x != null);
      if (v.length > 1) worst = Math.max(worst, Math.max(...v) - Math.min(...v));
    }
    return worst;
  }, [models]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 px-2 sm:px-3">
        <Segmented label="Source" value={src} onChange={setSrc} options={[{ value: "hybrid_mw", label: "Hybrid" }, { value: "solar_mw", label: "Solar" }, { value: "wind_mw", label: "Wind" }]} />
        {r.second_opinions.map((m) => (
          <Pill key={m.id} tone={m.status === "ok" ? "neutral" : "warn"} title={m.status}>{m.label}{m.status === "ok" ? "" : `: ${m.status}`}</Pill>
        ))}
        {spread != null && <span className="text-[12px] text-muted">Largest gap between weather models: <span className="num text-ink">{spread.toFixed(1)} MW</span></span>}
      </div>
      {option ? <EChart option={option} height={320} ariaLabel="Forecast against physics output under each weather model" /> : <p className="px-3 py-6 text-[13px] text-muted">No second opinions for this run.</p>}
      <p className="px-2 text-[12px] text-faint sm:px-3">Lines are the physics model of your plant run on each weather model&apos;s forecast, with the same availability and calibration. They are not separate ML forecasts; where they spread apart, the weather itself is uncertain.</p>
    </div>
  );
}
