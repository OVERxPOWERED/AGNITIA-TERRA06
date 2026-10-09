"use client";
/** What-if: change the weather or the battery, see the 48-hour forecast and plan before and after. */
import React, { useEffect, useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, istMs, timeChart, type BandPoint } from "@/components/charts/series";
import { Button, PageHeader, Panel, PanelHeader, RangeInput, Stat } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useSite, useWhatIf } from "@/hooks/api";
import type { WhatIfRequest } from "@/lib/api/types";
import { inr, mwh } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const PRESETS: Record<string, Partial<WhatIfRequest>> = {
  "Monsoon cloudy day": { irradiance_scale: 0.45, wind_scale: 1.2 },
  "Low-wind heatwave": { irradiance_scale: 1.05, wind_scale: 0.6 },
  "Double the battery": { battery_mw: 50, battery_mwh: 100 },
};

export default function WhatIfPage() {
  const { colors: c } = useTheme();
  const site = useSite();
  const m = useWhatIf();
  const [sc, setSc] = useState<WhatIfRequest>({ irradiance_scale: 1, wind_scale: 1 });
  const { mutate } = m;

  // Ask the API 400 ms after the last slider move.
  useEffect(() => {
    const t = setTimeout(() => mutate(sc), 400);
    return () => clearTimeout(t);
  }, [sc, mutate]);

  const option = useMemo(() => {
    if (!m.data) return null;
    const conv = (pts: Record<string, unknown>[]): BandPoint[] => pts.map((p) => ({ t: istMs(String(p.target_time_utc)), lo: Number(p.q10), mid: Number(p.q50), hi: Number(p.q90) }));
    const before = conv(m.data.before.points);
    const after = conv(m.data.after.points);
    if (!before.length) return null;
    return timeChart({
      c, unit: "MW", tMin: before[0].t, tMax: before[before.length - 1].t, bands: { b: before, a: after },
      series: [...bandSeries("Before", before, c.demand, "b", { bandOpacity: 0.1 }), ...bandSeries("After", after, c.hybrid, "a", { width: 2.6 })],
    });
  }, [m.data, c]);

  const set = (patch: Partial<WhatIfRequest>) => setSc((s) => ({ ...s, ...patch }));
  const b = m.data?.before;
  const a = m.data?.after;
  const arrow = (x: string, y: string) => `${x} → ${y}`;

  return (
    <>
      <PageHeader title="What-if simulator" description="Change the weather or the battery and see how the next 48 hours and the dispatch plan respond." />
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <Panel className="h-fit">
          <PanelHeader title="Scenario" />
          <div className="space-y-5 px-4 pb-5 pt-4 sm:px-5">
            <RangeInput label="Sunlight compared with forecast" value={sc.irradiance_scale ?? 1} min={0.2} max={1.3} step={0.05} onChange={(v) => set({ irradiance_scale: v })} format={(v) => `${Math.round(v * 100)}%`} />
            <RangeInput label="Wind compared with forecast" value={sc.wind_scale ?? 1} min={0.5} max={1.5} step={0.05} onChange={(v) => set({ wind_scale: v })} format={(v) => `${Math.round(v * 100)}%`} />
            <RangeInput label="Battery energy" value={sc.battery_mwh ?? site.data?.battery_mwh ?? 40} min={0} max={200} step={10} onChange={(v) => set({ battery_mwh: v })} format={(v) => `${v} MWh`} />
            <RangeInput label="Battery power" value={sc.battery_mw ?? site.data?.battery_mw ?? 20} min={0} max={100} step={5} onChange={(v) => set({ battery_mw: v })} format={(v) => `${v} MW`} />
            <div className="border-t border-line pt-4">
              <div className="mb-2 text-[13px] text-muted">Start from a preset</div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(PRESETS).map(([k, v]) => <Button key={k} onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1, ...v })}>{k}</Button>)}
                <Button variant="ghost" onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1 })}>Reset</Button>
              </div>
            </div>
          </div>
        </Panel>

        <div className="min-w-0 space-y-6">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
            <Stat label="Energy, 48 hours" value={b && a ? arrow(mwh(b.energy_mwh_p50), mwh(a.energy_mwh_p50)) : "—"} note="before → after" className="col-span-2" />
            <Stat label="Backup needed" value={b && a ? arrow(mwh(b.kpis.backup_mwh), mwh(a.kpis.backup_mwh)) : "—"} note="before → after" className="col-span-2" />
            <Stat label="Cost after" value={a ? inr(a.kpis.cost_inr) : "—"} note="illustrative prices" className="col-span-2" />
            <Stat label="CO₂ after" value={a ? `${a.kpis.co2_t.toFixed(0)} t` : "—"} className="col-span-2" />
          </dl>
          <Panel>
            <PanelHeader title="Combined forecast, before and after" note="The slate line is the current forecast and the green line is your scenario. Shaded bands are the 80% range." />
            <div className="px-2 pb-3 pt-2 sm:px-3">
              <QueryState isLoading={m.isPending && !m.data} error={m.error} height="h-[360px]">
                {option && <EChart option={option} height={360} ariaLabel="Hybrid forecast before and after the scenario" />}
              </QueryState>
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
