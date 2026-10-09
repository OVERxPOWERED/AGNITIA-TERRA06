"use client";
/** Forecast Trust: evidence that the trust score tracks real error + the per-hour ribbon. */
import React from "react";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Badge, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useTrustSummary } from "@/hooks/api";
import { toIST } from "@/lib/format";

export default function TrustPage() {
  const summary = useTrustSummary();
  const fc = useForecast("hybrid");
  const lowHours = fc.data?.points.filter((p) => p.trust_score < 40) ?? [];

  return (
    <div className="space-y-6">
      <div className="border-b border-border/60 pb-3">
        <h1 className="text-2xl font-bold tracking-tight text-text">Forecast Trust</h1>
        <p className="text-xs text-muted mt-0.5">
          Uncertainty calibration & empirical validation of the composite trust score
        </p>
      </div>

      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Next 48 hours confidence</CardTitle>
          <span className="text-xs text-muted">Per-hour model agreement and atmospheric stability</span>
        </div>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-20">
          {fc.data && <TrustRibbon points={fc.data.points} />}
          {lowHours.length > 0 ? (
            <div className="mt-4 space-y-2 border-t border-border/60 pt-3">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted">
                Low-confidence hours detail
              </div>
              <ul className="space-y-1.5 text-sm">
                {lowHours.slice(0, 6).map((p) => (
                  <li
                    key={p.target_time_utc}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-panel-muted/40 px-3 py-2 text-xs"
                  >
                    <span className="font-semibold text-text tabular-nums">{toIST(p.target_time_utc)}</span>
                    <div className="flex items-center gap-2">
                      <Badge tone="bad">Score: {p.trust_score}</Badge>
                      <span className="text-muted">{p.trust_reason}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted">All projected hours maintain high or moderate confidence.</p>
          )}
        </QueryState>
      </Card>

      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Does the score mean anything? (test period)</CardTitle>
          <span className="text-xs text-muted">Empirical validation against ground-truth error</span>
        </div>
        <QueryState isLoading={summary.isLoading} error={summary.error} refetch={summary.refetch} height="h-32">
          <div className="grid gap-4 md:grid-cols-2">
            {(["solar", "wind"] as const).map((s) => {
              const t = summary.data?.[s];
              if (!t) return null;
              return (
                <div key={s} className="space-y-2.5 rounded-xl border border-border/80 bg-panel-muted/30 p-4">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold capitalize text-base text-text">{s} Generation</span>
                    <Badge tone="hybrid">Spearman ρ {t.spearman_score_vs_abs_error.toFixed(2)}</Badge>
                  </div>
                  <p className="text-xs text-muted leading-relaxed">
                    Rank correlation between trust score and actual error:{" "}
                    <strong className="text-text">{t.spearman_score_vs_abs_error.toFixed(2)}</strong>{" "}
                    (negative confirms higher score corresponds to strictly lower forecast error).
                  </p>
                  <div className="border-t border-border/60 pt-2 text-xs">
                    <span className="font-medium text-muted">Average MAE by confidence tier:</span>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {Object.entries(t.mae_by_level).map(([k, v]) => (
                        <span key={k} className="rounded-md border border-border bg-panel px-2 py-1 tabular-nums">
                          <strong className="capitalize">{k}</strong>: {v.toFixed(2)} MW
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
