import type { AlertOut } from "@/lib/api/types";

export const ALERT_LABEL: Record<string, string> = {
  LOW_GENERATION: "Low generation",
  HIGH_GENERATION: "High generation",
  RAMP: "Fast ramp",
  DEFICIT_VS_DEMAND: "Short of demand",
  LOW_CONFIDENCE: "Low confidence",
  WEATHER_DISAGREEMENT: "Weather models disagree",
  DEVIATION_RISK: "Revise your schedule",
};

/** For LOW_CONFIDENCE the API's magnitude_mw is an internal placeholder, not megawatts: show the trust score instead. */
export function alertValue(a: AlertOut): string {
  if (a.type === "LOW_CONFIDENCE") {
    const m = /trust score (\d+)/.exec(a.message);
    return m ? `score ${m[1]}` : "—";
  }
  return `${a.magnitude_mw.toFixed(1)} MW`;
}

export const severityTone = (s: string) => (s === "critical" ? "bad" : s === "warning" ? "warn" : "neutral") as "bad" | "warn" | "neutral";

/** What the operator should do, per alert type (shown on critical alerts). */
export const ALERT_ACTION: Record<string, string> = {
  DEVIATION_RISK: "Revise the schedule with your load despatch centre before the window starts.",
  DEFICIT_VS_DEMAND: "Line up backup power or battery reserve for this window.",
  LOW_GENERATION: "Check backup and battery plans; consider revising the schedule.",
  HIGH_GENERATION: "Expect curtailment; check the export limit and charge the battery.",
  RAMP: "Prepare for a fast change in output; warn the control room.",
  LOW_CONFIDENCE: "Treat this window's forecast with caution and keep extra reserve.",
  WEATHER_DISAGREEMENT: "Weather models disagree; keep extra reserve and watch the next update.",
};

/** "Starts in 2 h 10 min", "Happening now" or "Ended" for an alert window. */
export function timeToStart(a: AlertOut, now: number): string {
  const s = Date.parse(a.start_utc), e = Date.parse(a.end_utc);
  if (now >= e) return "Ended";
  if (now >= s) return "Happening now";
  const m = Math.round((s - now) / 60_000);
  return m < 60 ? `Starts in ${m} min` : `Starts in ${Math.floor(m / 60)} h ${m % 60} min`;
}
