"use client";
/** Battery Dispatch Advisor: plan chart, strategy KPIs, value-of-forecast table. */
import React, { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { timeAxisOption } from "@/components/charts/series";
import { Card, CardTitle, Kpi, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDispatch, useImpact } from "@/hooks/api";
import { inr, mwh } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Strat = "advisor" | "rule" | "none";

export default function DispatchPage() {
  const { resolvedTheme, colors } = useTheme();
  const [strategy, setStrategy] = useState<Strat>("advisor");
  const d = useDispatch(strategy);
  const impact = useImpact();

  const option = useMemo(() => {
    if (!d.data) return null;
    const p = d.data.points;
    const ser = (name: string, key: keyof (typeof p)[number], color: string, sign = 1) => ({
      name,
      type: "bar",
      stack: "flow",
      data: p.map((x) => [x.target_time_utc, sign * (x[key] as number)]),
      itemStyle: { color, borderRadius: sign > 0 ? [2, 2, 0, 0] : [0, 0, 2, 2] },
    });
    return {
      ...timeAxisOption(
        "MW",
        {
          yAxis: [
            { type: "value", name: "Power (MW)", min: 0 },
            { type: "value", name: "SoC (MWh)", min: 0 },
          ],
        },
        resolvedTheme
      ),
      series: [
        ser("Discharge", "discharge_mw", colors.battery),
        ser("Backup", "backup_mw", colors.backup),
        ser("Charge", "charge_mw", colors.battery, -1),
        ser("Curtail", "curtail_mw", colors.bad, -1),
        {
          name: "State of charge",
          type: "line",
          yAxisIndex: 1,
          data: p.map((x) => [x.target_time_utc, x.soc_mwh]),
          lineStyle: { color: colors.hybrid, width: 2 },
          itemStyle: { color: colors.hybrid },
          symbol: "none",
        },
      ],
    };
  }, [d.data, colors, resolvedTheme]);

  const k = d.data?.kpis;
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Battery Dispatch Advisor</h1>
          <p className="text-xs text-muted mt-0.5">
            Optimal storage dispatch scheduling & backup minimization
          </p>
        </div>
        <Segmented
          label="Strategy"
          value={strategy}
          onChange={setStrategy}
          options={[
            { value: "advisor", label: "Vidyut advisor" },
            { value: "rule", label: "Rule-based" },
            { value: "none", label: "No battery" },
          ]}
        />
      </div>

      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
        <Kpi label="Backup (advisor)" value={k ? mwh(k.advisor.backup_mwh, 1) : "—"} hint="Vidyut optimization" />
        <Kpi label="Backup (rule-based)" value={k ? mwh(k.rule.backup_mwh, 1) : "—"} hint="Standard heuristics" />
        <Kpi label="Backup (no battery)" value={k ? mwh(k.none.backup_mwh, 1) : "—"} hint="Unbuffered baseline" />
        <Kpi label="Planned cost (advisor)" value={k ? inr(k.advisor.cost_inr) : "—"} hint="Illustrative cost in config" />
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Next 48 h dispatch plan</CardTitle>
          <span className="text-xs text-muted">Discharge/Backup (positive) · Charge/Curtail (negative)</span>
        </div>
        <QueryState isLoading={d.isLoading} error={d.error} refetch={d.refetch} height="h-[360px]">
          {option && <EChart option={option} height={340} ariaLabel={`Battery plan for strategy ${strategy}`} />}
        </QueryState>
      </Card>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Value of forecast — test period</CardTitle>
          <span className="text-xs text-muted">Settled against observed actual generation</span>
        </div>
        <QueryState isLoading={impact.isLoading} error={impact.error} refetch={impact.refetch} height="h-32">
          <div className="overflow-x-auto rounded-lg border border-border/80">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-xs uppercase tracking-wider text-muted bg-panel-muted/50 border-b border-border">
                <tr>
                  <th className="px-3 py-2.5 font-semibold">Forecast used</th>
                  <th className="px-3 py-2.5 font-semibold">Backup MWh</th>
                  <th className="px-3 py-2.5 font-semibold">Curtailed MWh</th>
                  <th className="px-3 py-2.5 font-semibold">Cost</th>
                  <th className="px-3 py-2.5 font-semibold">tCO₂</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {impact.data?.value_of_forecast.map((r) => (
                  <tr key={String(r.strategy)} className="hover:bg-panel-muted/30 transition-colors">
                    <td className="px-3 py-2.5 font-medium text-text capitalize">{String(r.strategy)}</td>
                    <td className="px-3 py-2.5">{Number(r.backup_mwh).toFixed(0)}</td>
                    <td className="px-3 py-2.5">{Number(r.curtail_mwh).toFixed(0)}</td>
                    <td className="px-3 py-2.5">{inr(Number(r.cost_inr))}</td>
                    <td className="px-3 py-2.5">{Number(r.co2_t).toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </Card>
    </div>
  );
}
