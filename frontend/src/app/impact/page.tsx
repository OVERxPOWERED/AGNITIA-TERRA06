"use client";
/** Impact: CO2, backup, cost and DSM savings from the test-period backtest + labelled extrapolation. */
import React, { useState } from "react";
import { Card, CardTitle, Kpi, RangeInput } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useImpact } from "@/hooks/api";
import { inr, mwh } from "@/lib/format";

export default function ImpactPage() {
  const q = useImpact();
  const [fleet, setFleet] = useState(1000);
  const i = q.data?.impact as Record<string, number> | undefined;
  const f = i ? fleet / i.plant_capacity_mw : 0;

  return (
    <div className="space-y-6">
      <div className="border-b border-border/60 pb-3">
        <h1 className="text-2xl font-bold tracking-tight text-text">Impact & Decarbonization</h1>
        <p className="text-xs text-muted mt-0.5">
          Quantified emissions abatement, cost avoidance, and fleet-scale extrapolation
        </p>
      </div>

      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch}>
        {i && (
          <>
            <div className="rounded-xl border border-border/80 bg-panel-muted/30 p-4 text-xs text-muted">
              Vidyut-planned vs persistence-planned operation over{" "}
              <strong className="text-text">{i.period_days} held-out test days</strong>, on a{" "}
              <strong className="text-text">{i.plant_capacity_mw} MW hybrid plant</strong>.
            </div>

            <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
              <Kpi
                label="CO₂ avoided"
                value={`${i.co2_avoided_t.toFixed(0)} t`}
                hint={`${i.emission_factor_t_per_mwh} tCO₂/MWh (CEA grid baseline)`}
              />
              <Kpi label="Backup energy avoided" value={mwh(i.backup_avoided_mwh)} hint="Diesel/grid generation saved" />
              <Kpi label="Cost saved" value={inr(i.cost_saved_inr)} hint="Direct operational savings" />
              <Kpi
                label="Deviation charges saved"
                value={i.dsm_charges_saved_inr != null ? inr(i.dsm_charges_saved_inr) : "—"}
                hint="Illustrative regulatory rates"
              />
            </div>

            <Card className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="mb-0">
                  Scale to a fleet (linear extrapolation — not a measured result)
                </CardTitle>
                <span className="text-xs text-muted">Slide to adjust portfolio capacity</span>
              </div>
              <RangeInput
                label="Fleet capacity"
                value={fleet}
                min={100}
                max={20000}
                step={100}
                onChange={setFleet}
                format={(v) => `${v.toLocaleString("en-IN")} MW`}
              />
              <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3 pt-2">
                <Kpi label="CO₂ avoided (est.)" value={`${(i.co2_avoided_t * f).toFixed(0)} t`} />
                <Kpi label="Backup avoided (est.)" value={mwh(i.backup_avoided_mwh * f)} />
                <Kpi label="Cost saved (est.)" value={inr(i.cost_saved_inr * f)} />
              </div>
            </Card>

            <Card className="space-y-2">
              <CardTitle>Methodology Sources</CardTitle>
              <ul className="list-disc pl-5 text-xs text-muted space-y-1">
                {q.data?.sources.map((s) => (
                  <li key={s} className="leading-relaxed">
                    {s}
                  </li>
                ))}
              </ul>
            </Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
