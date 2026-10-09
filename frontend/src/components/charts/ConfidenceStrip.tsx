"use client";
/** One square per forecast hour, coloured by trust level, laid out with the same side padding as the chart above it
 *  so each square sits under its own hour on the time axis. Colours are soft tints, never alarm-red. */
import React from "react";
import type { ForecastPoint } from "@/lib/api/types";
import { fmtDayHM, istMs } from "./series";

const FILL: Record<string, string> = {
  high: "color-mix(in srgb, var(--good) 70%, var(--surface))",
  medium: "color-mix(in srgb, var(--warn) 62%, var(--surface))",
  low: "color-mix(in srgb, var(--bad) 52%, var(--surface))",
};

export function trustCounts(points: ForecastPoint[]) {
  const n = { high: 0, medium: 0, low: 0 };
  for (const p of points) if (p.trust_level in n) n[p.trust_level as keyof typeof n] += 1;
  return n;
}

export default function ConfidenceStrip({ points, padLeft = 0, padRight = 0 }: { points: ForecastPoint[]; padLeft?: number; padRight?: number }) {
  const n = trustCounts(points);
  const summary = `Forecast confidence per hour: ${n.high} high, ${n.medium} medium, ${n.low} low`;
  return (
    <div>
      <div role="img" aria-label={summary} className="grid gap-[3px]" style={{ gridTemplateColumns: `repeat(${points.length || 1}, minmax(0, 1fr))`, paddingLeft: padLeft, paddingRight: padRight }}>
        {points.map((p) => (
          <span
            key={p.target_time_utc}
            title={`${fmtDayHM(istMs(p.target_time_utc))}: confidence ${Math.round(p.trust_score)} of 100 (${p.trust_level}). ${p.trust_reason}`}
            className="h-4 rounded-[3px]"
            style={{ background: FILL[p.trust_level] ?? FILL.medium }}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted" style={{ paddingLeft: padLeft, paddingRight: padRight }}>
        {(["high", "medium", "low"] as const).map((k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2.5 w-2.5 rounded-[3px]" style={{ background: FILL[k] }} />
            <span className="capitalize">{k}</span>
            <span className="num text-ink">{n[k]} h</span>
          </span>
        ))}
      </div>
    </div>
  );
}
