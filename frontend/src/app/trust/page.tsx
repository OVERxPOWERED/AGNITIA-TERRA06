"use client";
/** Forecast trust: the hour-by-hour confidence score and the evidence that it tracks real error. */
import React from "react";
import ConfidenceStrip from "@/components/charts/ConfidenceStrip";
import { PageHeader, Panel, PanelHeader, Pill } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useTrustSummary } from "@/hooks/api";
import { toIST } from "@/lib/format";

export default function TrustPage() {
  const summary = useTrustSummary();
  const fc = useForecast("hybrid");
  const low = fc.data?.points.filter((p) => p.trust_level === "low") ?? [];
  return (
    <>
      <PageHeader title="Forecast trust" description="Each hour gets a confidence score from 0 to 100. It rises when the models agree, the range is narrow and recent forecasts have been accurate." />
      <div className="space-y-6">
        <Panel>
          <PanelHeader title="Next 48 hours" note="Scores below 40 are low, 40 to 69 medium, 70 and above high. They are measured against what was typical during validation, so many hours can read low on an unsettled day." />
          <div className="px-4 pb-5 pt-4 sm:px-5">
            <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-20">
              {fc.data && <ConfidenceStrip points={fc.data.points} />}
              {low.length > 0 && (
                <div className="mt-5">
                  <h3 className="text-[13px] font-medium text-ink">Lowest-confidence hours</h3>
                  <ul className="mt-2 divide-y divide-line rounded-lg border border-line">
                    {[...low].sort((a, b) => a.trust_score - b.trust_score).slice(0, 6).map((p) => (
                      <li key={p.target_time_utc} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-[13px]">
                        <span className="num">{toIST(p.target_time_utc)}</span>
                        <span className="flex items-center gap-3"><span className="text-muted">{p.trust_reason}</span><Pill tone="bad">score {p.trust_score.toFixed(0)}</Pill></span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </QueryState>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Does the score mean anything?" note="On the test period, hours with a higher score had smaller errors. A negative rank correlation means exactly that." />
          <div className="px-4 pb-5 pt-4 sm:px-5">
            <QueryState isLoading={summary.isLoading} error={summary.error} refetch={summary.refetch} height="h-32">
              <div className="grid gap-4 md:grid-cols-2">
                {(["solar", "wind"] as const).map((s) => {
                  const t = summary.data?.[s];
                  if (!t) return null;
                  return (
                    <div key={s} className="rounded-lg border border-line p-4">
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="text-[14px] font-semibold capitalize">{s}</h3>
                        <Pill tone="accent">rank correlation <span className="num">{t.spearman_score_vs_abs_error.toFixed(2)}</span></Pill>
                      </div>
                      <p className="mt-3 text-[13px] text-muted">Average error by confidence level</p>
                      <dl className="mt-1.5 grid grid-cols-3 gap-2">
                        {Object.entries(t.mae_by_level).map(([k, v]) => (
                          <div key={k} className="rounded-md bg-sunken px-3 py-2">
                            <dt className="text-[12px] capitalize text-muted">{k}</dt>
                            <dd className="num text-[15px]">{v.toFixed(2)} <span className="text-[12px] text-faint">MW</span></dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  );
                })}
              </div>
            </QueryState>
          </div>
        </Panel>
      </div>
    </>
  );
}
