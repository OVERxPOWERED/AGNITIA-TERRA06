"use client";
/** Impact: what the planning saved over the test period, and a clearly labelled extrapolation to a larger fleet. */
import React, { useState } from "react";
import { PageHeader, Panel, PanelHeader, RangeInput, Stat } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useImpact } from "@/hooks/api";
import { inr, mwh } from "@/lib/format";

export default function ImpactPage() {
  const q = useImpact();
  const [fleet, setFleet] = useState(1000);
  const i = q.data?.impact as Record<string, number> | undefined;
  const f = i ? fleet / i.plant_capacity_mw : 0;
  return (
    <>
      <PageHeader title="Impact" description="What Vidyut-planned operation saved compared with planning on a persistence forecast, measured on days the models never saw." />
      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch} height="h-64">
        {i && (
          <div className="space-y-6">
            <p className="text-[14px] text-muted">Over <span className="num text-ink">{i.period_days}</span> held-out days on a <span className="num text-ink">{i.plant_capacity_mw} MW</span> hybrid plant.</p>
            <dl className="grid grid-cols-2 gap-y-6 lg:grid-cols-4 lg:divide-x lg:divide-line [&>div]:lg:px-6 [&>div:first-child]:lg:pl-0">
              <Stat label="CO₂ avoided" value={`${i.co2_avoided_t.toFixed(0)} t`} note={`${i.emission_factor_t_per_mwh} tCO₂ per MWh, CEA grid baseline`} />
              <Stat label="Backup energy avoided" value={mwh(i.backup_avoided_mwh)} note="Diesel or grid power not needed" />
              <Stat label="Cost saved" value={inr(i.cost_saved_inr)} note="Direct operating cost" />
              <Stat label="Deviation charges saved" value={i.dsm_charges_saved_inr != null ? inr(i.dsm_charges_saved_inr) : "—"} note="Illustrative rates" />
            </dl>
            <Panel>
              <PanelHeader title="Scale to a fleet" note="A straight-line multiple of the figures above. It is an extrapolation, not a measured result." />
              <div className="space-y-5 px-4 pb-5 pt-4 sm:px-5">
                <RangeInput label="Fleet capacity" value={fleet} min={100} max={20000} step={100} onChange={setFleet} format={(v) => `${v.toLocaleString("en-IN")} MW`} />
                <dl className="grid gap-5 sm:grid-cols-3">
                  <Stat label="CO₂ avoided, estimated" value={`${(i.co2_avoided_t * f).toFixed(0)} t`} />
                  <Stat label="Backup avoided, estimated" value={mwh(i.backup_avoided_mwh * f)} />
                  <Stat label="Cost saved, estimated" value={inr(i.cost_saved_inr * f)} />
                </dl>
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="How these were worked out" />
              <ul className="list-disc space-y-1.5 px-9 pb-5 pt-3 text-[13px] text-muted">
                {q.data?.sources.map((s) => <li key={s}>{s}</li>)}
              </ul>
            </Panel>
          </div>
        )}
      </QueryState>
    </>
  );
}
