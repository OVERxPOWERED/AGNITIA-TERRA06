"use client";
/** Control Room (H1): combined forecast with band, solar/wind P50s, demand, trust strip, next alerts, KPIs. */
import { useMemo } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Badge, Card, CardTitle, Kpi } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAlerts, useDispatch, useForecast } from "@/hooks/api";
import { cssVar, mw, mwh, toIST } from "@/lib/format";

export default function ControlRoom() {
  const hybrid = useForecast("hybrid");
  const solar = useForecast("solar");
  const wind = useForecast("wind");
  const dispatch = useDispatch("advisor");
  const alerts = useAlerts();

  const option = useMemo(() => {
    if (!hybrid.data || !solar.data || !wind.data) return null;
    const pts = hybrid.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    const demand = dispatch.data?.points.map((p) => [p.target_time_utc, p.demand_mw]) ?? [];
    return {
      ...timeAxisOption("MW"),
      series: [
        ...bandSeries("Hybrid", pts, cssVar("--hybrid"), "hyb"),
        { name: "Solar P50", type: "line", data: solar.data.points.map((p) => [p.target_time_utc, p.q50]),
          lineStyle: { color: cssVar("--solar"), type: "dashed" }, itemStyle: { color: cssVar("--solar") }, symbol: "none" },
        { name: "Wind P50", type: "line", data: wind.data.points.map((p) => [p.target_time_utc, p.q50]),
          lineStyle: { color: cssVar("--wind"), type: "dashed" }, itemStyle: { color: cssVar("--wind") }, symbol: "none" },
        { name: "Demand", type: "line", data: demand, lineStyle: { color: cssVar("--demand"), width: 1.5 },
          itemStyle: { color: cssVar("--demand") }, symbol: "none" },
      ],
    } as const;
  }, [hybrid.data, solar.data, wind.data, dispatch.data]);

  const h = hybrid.data?.points ?? [];
  const energy = h.reduce((s, p) => s + p.q50, 0);
  const minP = h.length ? Math.min(...h.map((p) => p.q10)) : 0;
  const maxP = h.length ? Math.max(...h.map((p) => p.q90)) : 0;
  const avgTrust = h.length ? h.reduce((s, p) => s + p.trust_score, 0) / h.length : 0;
  const upcoming = (alerts.data ?? []).filter((a) => !a.acknowledged).slice(0, 4);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Control Room</h1>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Next 48 h energy (P50)" value={mwh(energy)} />
        <Kpi label="Lowest likely (P10)" value={mw(minP)} />
        <Kpi label="Highest likely (P90)" value={mw(maxP)} />
        <Kpi label="Average trust" value={`${avgTrust.toFixed(0)} / 100`} />
        <Kpi label="Backup needed (plan)" value={dispatch.data ? mwh(dispatch.data.kpis.advisor.backup_mwh) : "—"} />
      </div>
      <Card>
        <CardTitle>Combined solar + wind forecast with 80% band</CardTitle>
        <QueryState isLoading={hybrid.isLoading} error={hybrid.error ?? solar.error ?? wind.error} refetch={hybrid.refetch}>
          {option && <EChart option={option} height={360} ariaLabel="Hybrid forecast for the next 48 hours with P10–P90 band, solar and wind medians and demand" />}
          <div className="mt-3"><TrustRibbon points={h} /></div>
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Next alerts</CardTitle>
        <QueryState isLoading={alerts.isLoading} error={alerts.error} empty={!upcoming.length} height="h-16">
          <ul className="divide-y divide-border">
            {upcoming.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <Badge tone={a.severity === "critical" ? "bad" : a.severity === "warning" ? "warn" : "neutral"}>{a.severity}</Badge>
                <span className="font-medium">{a.message}</span>
                <span className="text-muted">{toIST(a.start_utc)} → {toIST(a.end_utc)}</span>
              </li>
            ))}
          </ul>
        </QueryState>
      </Card>
    </div>
  );
}
