"use client";
/** What-if Simulator: sliders -> POST /whatif (debounced) -> before/after chart and KPIs. */
import React, { useEffect, useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import { Button, Card, CardTitle, Kpi, RangeInput } from "@/components/ui/primitives";
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
  const { resolvedTheme, colors } = useTheme();
  const site = useSite();
  const m = useWhatIf();
  const [sc, setSc] = useState<WhatIfRequest>({ irradiance_scale: 1, wind_scale: 1 });
  const { mutate } = m;

  useEffect(() => {
    const t = setTimeout(() => mutate(sc), 400);
    return () => clearTimeout(t);
  }, [sc, mutate]);

  const option = useMemo(() => {
    if (!m.data) return null;
    const conv = (pts: Record<string, unknown>[]) =>
      pts.map((p) => ({ t: String(p.target_time_utc), lo: Number(p.q10), mid: Number(p.q50), hi: Number(p.q90) }));
    return {
      ...timeAxisOption("MW", {}, resolvedTheme),
      series: [
        ...bandSeries("Baseline (Before)", conv(m.data.before.points), colors.demand, "b"),
        ...bandSeries("Scenario (After)", conv(m.data.after.points), colors.hybrid, "a"),
      ],
    };
  }, [m.data, colors, resolvedTheme]);

  const set = (patch: Partial<WhatIfRequest>) => setSc((s) => ({ ...s, ...patch }));
  const b = m.data?.before,
    a = m.data?.after;

  return (
    <div className="space-y-6">
      <div className="border-b border-border/60 pb-3">
        <h1 className="text-2xl font-bold tracking-tight text-text">What-if Simulator</h1>
        <p className="text-xs text-muted mt-0.5">
          Simulate weather shifts, extreme climate events, and BESS capacity scaling
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-[320px_1fr]">
        <Card className="space-y-4 h-fit">
          <CardTitle>Scenario Parameters</CardTitle>
          <div className="space-y-3.5">
            <RangeInput
              label="Sunlight vs forecast"
              value={sc.irradiance_scale ?? 1}
              min={0.2}
              max={1.3}
              step={0.05}
              onChange={(v) => set({ irradiance_scale: v })}
              format={(v) => `${Math.round(v * 100)}%`}
            />
            <RangeInput
              label="Wind vs forecast"
              value={sc.wind_scale ?? 1}
              min={0.5}
              max={1.5}
              step={0.05}
              onChange={(v) => set({ wind_scale: v })}
              format={(v) => `${Math.round(v * 100)}%`}
            />
            <RangeInput
              label="Battery energy"
              value={sc.battery_mwh ?? site.data?.battery_mwh ?? 50}
              min={0}
              max={200}
              step={10}
              onChange={(v) => set({ battery_mwh: v })}
              format={(v) => `${v} MWh`}
            />
            <RangeInput
              label="Battery power"
              value={sc.battery_mw ?? site.data?.battery_mw ?? 25}
              min={0}
              max={100}
              step={5}
              onChange={(v) => set({ battery_mw: v })}
              format={(v) => `${v} MW`}
            />
          </div>

          <div className="space-y-2 pt-2 border-t border-border/60">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted">
              Quick presets
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(PRESETS).map(([k, v]) => (
                <Button
                  key={k}
                  onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1, ...v })}
                  className="text-xs py-1 px-2.5"
                >
                  {k}
                </Button>
              ))}
              <Button
                onClick={() => setSc({ irradiance_scale: 1, wind_scale: 1 })}
                className="text-xs py-1 px-2.5"
              >
                Reset
              </Button>
            </div>
          </div>
          <p className="text-[11px] text-muted leading-relaxed">
            Physics + LightGBM models evaluate in real time. Capacity updates dynamically rescale the hybrid plant output.
          </p>
        </Card>

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
            <Kpi
              label="Energy 48 h (before → after)"
              value={b && a ? `${mwh(b.energy_mwh_p50)} → ${mwh(a.energy_mwh_p50)}` : "—"}
            />
            <Kpi
              label="Backup (before → after)"
              value={b && a ? `${mwh(b.kpis.backup_mwh)} → ${mwh(a.kpis.backup_mwh)}` : "—"}
            />
            <Kpi label="Cost after" value={a ? inr(a.kpis.cost_inr) : "—"} />
            <Kpi label="CO₂ after" value={a ? `${a.kpis.co2_t.toFixed(0)} t` : "—"} />
          </div>

          <Card className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="mb-0">Combined forecast — before vs after</CardTitle>
              <span className="text-xs text-muted">Baseline (Slate) vs Scenario (Signal)</span>
            </div>
            <QueryState isLoading={m.isPending && !m.data} error={m.error} height="h-[360px]">
              {option && (
                <EChart
                  option={option}
                  height={340}
                  ariaLabel="Hybrid forecast before and after the scenario"
                />
              )}
            </QueryState>
          </Card>
        </div>
      </div>
    </div>
  );
}
