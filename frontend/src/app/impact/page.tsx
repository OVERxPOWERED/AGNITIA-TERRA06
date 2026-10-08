"use client";
/** Impact: CO2, backup, cost and DSM savings from the test-period backtest + labelled extrapolation. */
import { useState } from "react";
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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Impact</h1>
      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch}>
        {i && (
          <>
            <p className="text-sm text-muted">TERRA-planned vs persistence-planned operation over {i.period_days} held-out days, {i.plant_capacity_mw} MW plant.</p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Kpi label="CO₂ avoided" value={`${i.co2_avoided_t.toFixed(0)} t`} hint={`${i.emission_factor_t_per_mwh} tCO₂/MWh (CEA)`} />
              <Kpi label="Backup energy avoided" value={mwh(i.backup_avoided_mwh)} />
              <Kpi label="Cost saved" value={inr(i.cost_saved_inr)} />
              <Kpi label="Deviation charges saved" value={i.dsm_charges_saved_inr != null ? inr(i.dsm_charges_saved_inr) : "—"} hint="illustrative rates" />
            </div>
            <Card className="space-y-3">
              <CardTitle>Scale to a fleet (linear extrapolation — not a measured result)</CardTitle>
              <RangeInput label="Fleet capacity" value={fleet} min={100} max={20000} step={100} onChange={setFleet} format={(v) => `${v.toLocaleString("en-IN")} MW`} />
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                <Kpi label="CO₂ avoided (est.)" value={`${(i.co2_avoided_t * f).toFixed(0)} t`} />
                <Kpi label="Backup avoided (est.)" value={mwh(i.backup_avoided_mwh * f)} />
                <Kpi label="Cost saved (est.)" value={inr(i.cost_saved_inr * f)} />
              </div>
            </Card>
            <Card><CardTitle>Sources</CardTitle><ul className="list-disc pl-5 text-sm">{q.data?.sources.map((s) => <li key={s}>{s}</li>)}</ul></Card>
          </>
        )}
      </QueryState>
    </div>
  );
}
