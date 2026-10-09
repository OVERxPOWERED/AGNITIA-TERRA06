import React from "react";
import { toIST } from "@/lib/format";
import { useTheme } from "@/lib/theme";

/** Per-hour trust strip; softened muted tones, slim 8px height with rounded ends,
 *  distinguishable via pattern cue + accessible text. */
export default function TrustRibbon({
  points,
}: {
  points: { target_time_utc: string; trust_score: number; trust_reason: string }[];
}) {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  // Softened, calm semantic colors (low saturation to avoid visually screaming)
  const getStyle = (s: number): React.CSSProperties => {
    if (s >= 70) {
      // High confidence: soft subtle sage green
      return {
        backgroundColor: isDark ? "rgba(52, 211, 153, 0.45)" : "rgba(34, 197, 94, 0.35)",
      };
    }
    if (s >= 40) {
      // Medium confidence: gentle muted amber
      return {
        backgroundColor: isDark ? "rgba(251, 191, 36, 0.45)" : "rgba(217, 119, 6, 0.35)",
      };
    }
    // Low confidence: soft rose/coral with subtle hatched pattern for colorblind distinction
    return {
      backgroundColor: isDark ? "rgba(248, 113, 113, 0.45)" : "rgba(225, 29, 72, 0.35)",
      backgroundImage: `repeating-linear-gradient(45deg, transparent, transparent 2px, ${
        isDark ? "rgba(248, 113, 113, 0.7)" : "rgba(225, 29, 72, 0.6)"
      } 2px, ${isDark ? "rgba(248, 113, 113, 0.7)" : "rgba(225, 29, 72, 0.6)"} 4px)`,
    };
  };

  const low = points.filter((p) => p.trust_score < 40).length;

  return (
    <div className="space-y-1.5">
      <div
        className="flex h-2 w-full overflow-hidden rounded-full border border-border/50 bg-border/30"
        aria-label={`Forecast trust per hour: ${low} low-confidence hours`}
      >
        {points.map((p) => (
          <div
            key={p.target_time_utc}
            className="flex-1 transition-opacity hover:opacity-80"
            style={getStyle(p.trust_score)}
            title={`${toIST(p.target_time_utc)} · trust ${p.trust_score} · ${p.trust_reason}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-good/60 shrink-0" />
            <span>High (≥70)</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-warn/60 shrink-0" />
            <span>Medium (40–69)</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-bad/60 border border-bad/40 shrink-0" />
            <span>Low (&lt;40)</span>
          </span>
        </div>
        {low > 0 && (
          <span className="font-medium text-muted">
            {low} low-confidence {low === 1 ? "hour" : "hours"} flagged
          </span>
        )}
      </div>
    </div>
  );
}
