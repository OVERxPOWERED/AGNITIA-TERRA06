import type { AlertOut } from "@/lib/api/types";

export const ALERT_LABEL: Record<string, string> = {
  LOW_GENERATION: "Low generation",
  HIGH_GENERATION: "High generation",
  RAMP: "Fast ramp",
  DEFICIT_VS_DEMAND: "Short of demand",
  LOW_CONFIDENCE: "Low confidence",
  WEATHER_DISAGREEMENT: "Weather models disagree",
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
