"use client";
/** Battery Dispatch Advisor (H2): plan chart, strategy KPIs, value-of-forecast table. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { timeAxisOption } from "@/components/charts/series";
import { Card, CardTitle, Kpi, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDispatch, useImpact } from "@/hooks/api";
import { cssVar, inr, mwh } from "@/lib/format";

type Strat = "advisor" | "rule" | "none";

export default function DispatchPage() {
  const [strategy, setStrategy] = useState<Strat>("advisor");
  const d = useDispatch(strategy);
  const impact = useImpact();

  const option = useMemo(() => {
    if (!d.data) return null;
    const p = d.data.points;
    const ser = (name: string, key: keyof (typeof p)[number], color: string, sign = 1) => ({
      name, type: "bar", stack: "flow", data: p.map((x) => [x.target_time_utc, sign * (x[key] as number)]), itemStyle: { color },
    });
    return {
      ...timeAxisOption("MW", { yAxis: [{ type: "value", name: "MW" }, { type: "value", name: "SoC MWh", min: 0 }] }),
      series: [
        ser("Discharge", "discharge_mw", cssVar("--battery")),
        ser("Backup", "backup_mw", cssVar("--backup")),
        ser("Charge", "charge_mw", cssVar("--battery"), -1),
        ser("Curtail", "curtail_mw", cssVar("--bad"), -1),
        { name: "State of charge", type: "line", yAxisIndex: 1, data: p.map((x) => [x.target_time_utc, x.soc_mwh]),
          lineStyle: { color: cssVar("--hybrid") }, itemStyle: { color: cssVar("--hybrid") }, symbol: "none" },
      ],
    };
  }, [d.data]);

  const k = d.data?.kpis;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Battery Dispatch Advisor</h1>
        <Segmented label="Strategy" value={strategy} onChange={setStrategy}
          options={[{ value: "advisor", label: "TERRA advisor" }, { value: "rule", label: "Rule-based" }, { value: "none", label: "No battery" }]} />
      </div>
      {k && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Backup (advisor)" value={mwh(k.advisor.backup_mwh, 1)} />
          <Kpi label="Backup (rule-based)" value={mwh(k.rule.backup_mwh, 1)} />
          <Kpi label="Backup (no battery)" value={mwh(k.none.backup_mwh, 1)} />
          <Kpi label="Planned cost (advisor)" value={inr(k.advisor.cost_inr)} hint="cost assumptions in config" />
        </div>
      )}
      <Card>
        <CardTitle>Next 48 h plan</CardTitle>
        <QueryState isLoading={d.isLoading} error={d.error} refetch={d.refetch}>
          {option && <EChart option={option} height={340} ariaLabel={`Battery plan for strategy ${strategy}`} />}
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Value of forecast — test period, plans settled on actual generation</CardTitle>
        <QueryState isLoading={impact.isLoading} error={impact.error} height="h-32">
          <table className="w-full text-sm tabular-nums">
            <thead className="text-left text-muted"><tr><th className="px-2 py-1">Forecast used</th><th className="px-2 py-1">Backup MWh</th><th className="px-2 py-1">Curtailed MWh</th><th className="px-2 py-1">Cost</th><th className="px-2 py-1">tCO₂</th></tr></thead>
            <tbody>
              {impact.data?.value_of_forecast.map((r) => (
                <tr key={String(r.strategy)}>
                  <td className="px-2 py-1">{String(r.strategy)}</td>
                  <td className="px-2 py-1">{Number(r.backup_mwh).toFixed(0)}</td>
                  <td className="px-2 py-1">{Number(r.curtail_mwh).toFixed(0)}</td>
                  <td className="px-2 py-1">{inr(Number(r.cost_inr))}</td>
                  <td className="px-2 py-1">{Number(r.co2_t).toFixed(0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </QueryState>
      </Card>
    </div>
  );
}
