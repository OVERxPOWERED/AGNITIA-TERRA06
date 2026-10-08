"use client";
/** Trust Layer (H3): evidence that the trust score tracks real error + the per-hour ribbon. */
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useTrustSummary } from "@/hooks/api";
import { toIST } from "@/lib/format";

export default function TrustPage() {
  const summary = useTrustSummary();
  const fc = useForecast("hybrid");
  const lowHours = fc.data?.points.filter((p) => p.trust_score < 40) ?? [];
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Forecast Trust</h1>
      <Card>
        <CardTitle>Next 48 hours</CardTitle>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-12">
          {fc.data && <TrustRibbon points={fc.data.points} />}
          <ul className="mt-3 space-y-1 text-sm">
            {lowHours.slice(0, 6).map((p) => <li key={p.target_time_utc}>{toIST(p.target_time_utc)} — trust {p.trust_score}: {p.trust_reason}</li>)}
          </ul>
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Does the score mean anything? (test period)</CardTitle>
        <QueryState isLoading={summary.isLoading} error={summary.error} refetch={summary.refetch} height="h-24">
          <div className="grid gap-4 md:grid-cols-2">
            {(["solar", "wind"] as const).map((s) => {
              const t = summary.data?.[s];
              if (!t) return null;
              return (
                <div key={s} className="text-sm">
                  <div className="font-semibold capitalize">{s}</div>
                  <p>Rank correlation between trust score and actual error: <b>{t.spearman_score_vs_abs_error.toFixed(2)}</b> (negative = higher trust, lower error).</p>
                  <p className="mt-1">Average error by trust level: {Object.entries(t.mae_by_level).map(([k, v]) => `${k} ${v.toFixed(2)} MW`).join(" · ")}</p>
                </div>
              );
            })}
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
