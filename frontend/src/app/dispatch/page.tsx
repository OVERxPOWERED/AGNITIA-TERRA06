"use client";
/** Battery dispatch: the 48-hour plan for the chosen strategy, what each strategy costs, and what forecast quality is worth. */
import React, { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { istMs, timeChart, fmtDayHM } from "@/components/charts/series";
import { PageHeader, Panel, PanelHeader, Segmented, Stat, tableCls, tdCls, tdNum, thCls } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDispatch, useImpact } from "@/hooks/api";
import { inr, mwh } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Strat = "advisor" | "rule" | "none";
const FORECAST_NAME: Record<string, string> = {
  persistence: "Persistence (yesterday repeats)", physics: "Physics model", gbm: "LightGBM", ensemble: "Ensemble (served)",
  perfect_foresight: "Perfect foresight (upper bound)", no_battery: "No battery",
};
const NAMES: Record<Strat, string> = { advisor: "Vidyut advisor", rule: "Rule-based", none: "No battery" };

export default function DispatchPage() {
  const { colors: c } = useTheme();
  const [strategy, setStrategy] = useState<Strat>("advisor");
  const d = useDispatch(strategy);
  const impact = useImpact();
  const kp = d.data?.kpis;

  const option = useMemo(() => {
    const p = d.data?.points;
    if (!p?.length) return null;
    const t = p.map((x) => istMs(x.target_time_utc));
    const bar = (name: string, key: "discharge_mw" | "backup_mw" | "charge_mw" | "curtail_mw", color: string, sign: 1 | -1) => ({
      id: key, name, type: "bar" as const, stack: "flow", barMaxWidth: 14, itemStyle: { color, borderRadius: sign > 0 ? [2, 2, 0, 0] : [0, 0, 2, 2] },
      data: p.map((x, i) => [t[i], sign * x[key]]),
    });
    const base = timeChart({
      c, unit: "MW", tMin: t[0], tMax: t[t.length - 1],
      series: [
        bar("Battery discharge", "discharge_mw", c.battery, 1), bar("Backup", "backup_mw", c.backup, 1),
        bar("Battery charge", "charge_mw", c.battery, -1), bar("Curtailed", "curtail_mw", c.bad, -1),
        { id: "soc", name: "Stored energy", type: "line" as const, yAxisIndex: 1, symbol: "none", data: p.map((x, i) => [t[i], x.soc_mwh]), lineStyle: { color: c.hybrid, width: 2 }, itemStyle: { color: c.hybrid }, z: 5 },
      ],
    });
    const mono = { color: c.muted, fontSize: 11, fontFamily: "var(--font-geist-mono), monospace" };
    return {
      ...base,
      grid: { ...(base.grid as object), right: 52 },
      yAxis: [
        { type: "value" as const, name: "MW", nameLocation: "end" as const, nameTextStyle: { ...mono, align: "right" as const }, axisLabel: mono, splitLine: { lineStyle: { color: c.line } } },
        { type: "value" as const, name: "MWh stored", nameLocation: "end" as const, nameTextStyle: { ...mono, align: "left" as const }, axisLabel: mono, min: 0, splitLine: { show: false } },
      ],
      tooltip: {
        trigger: "axis" as const, backgroundColor: c.surface, borderColor: c.line, textStyle: { color: c.ink, fontSize: 12 },
        formatter: (raw: unknown) => {
          const ps = (Array.isArray(raw) ? raw : [raw]) as { seriesName: string; value: [number, number]; color: string; axisValue: number }[];
          const rows = ps.filter((s) => Math.abs(s.value[1]) > 0.005).map((s) => `<div style="display:flex;justify-content:space-between;gap:16px"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${s.color};margin-right:6px"></span>${s.seriesName}</span><span style="font-family:var(--font-geist-mono),monospace">${Math.abs(s.value[1]).toFixed(1)} ${s.seriesName === "Stored energy" ? "MWh" : "MW"}</span></div>`).join("");
          return `<div style="font-size:12px"><div style="color:${c.muted}">${fmtDayHM(ps[0].axisValue)}</div>${rows || "No flows this hour"}</div>`;
        },
      },
    };
  }, [d.data, c]);

  return (
    <>
      <PageHeader
        title="Battery dispatch"
        description="When to charge and discharge the battery over the next 48 hours so that backup power is kept to a minimum."
        actions={<Segmented label="Strategy" value={strategy} onChange={setStrategy} options={(Object.keys(NAMES) as Strat[]).map((k) => ({ value: k, label: NAMES[k] }))} />}
      />
      <div className="space-y-6">
        <dl className="grid grid-cols-2 gap-y-5 sm:grid-cols-4 sm:divide-x sm:divide-line [&>div]:sm:px-5 [&>div:first-child]:sm:pl-0">
          <Stat label="Backup with advisor" value={kp ? mwh(kp.advisor.backup_mwh, 1) : "—"} note="Vidyut optimisation" />
          <Stat label="Backup, rule-based" value={kp ? mwh(kp.rule.backup_mwh, 1) : "—"} note="Simple charge and discharge rules" />
          <Stat label="Backup, no battery" value={kp ? mwh(kp.none.backup_mwh, 1) : "—"} note="Nothing buffered" />
          <Stat label="Planned cost, advisor" value={kp ? inr(kp.advisor.cost_inr) : "—"} note="Illustrative prices from config" />
        </dl>
        <Panel>
          <PanelHeader title={`Plan for the next 48 hours: ${NAMES[strategy].toLowerCase()}`} note="Above the zero line: battery discharge and backup power. Below it: battery charging and curtailed generation." />
          <div className="px-2 pb-3 pt-2 sm:px-3">
            <QueryState isLoading={d.isLoading} error={d.error} refetch={d.refetch} height="h-[360px]">
              {option && <EChart option={option} height={360} ariaLabel={`Battery plan for the ${NAMES[strategy]} strategy`} />}
            </QueryState>
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="What forecast quality is worth" note="The same plant run over the test period with different forecasts, settled against what was actually generated." />
          <div className="px-2 pb-4 pt-3 sm:px-3">
            <QueryState isLoading={impact.isLoading} error={impact.error} refetch={impact.refetch} height="h-32">
              <div className="overflow-x-auto">
                <table className={tableCls}>
                  <thead><tr>{["Forecast used", "Backup (MWh)", "Curtailed (MWh)", "Cost", "CO₂ (t)"].map((h, i) => <th key={h} className={`${thCls} ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
                  <tbody>
                    {impact.data?.value_of_forecast.map((r) => (
                      <tr key={String(r.strategy)} className="hover:bg-sunken/60">
                        <td className={`${tdCls} font-medium`}>{FORECAST_NAME[String(r.strategy)] ?? String(r.strategy).replaceAll("_", " ")}</td>
                        <td className={`${tdNum} text-right`}>{Number(r.backup_mwh).toFixed(0)}</td>
                        <td className={`${tdNum} text-right`}>{Number(r.curtail_mwh).toFixed(0)}</td>
                        <td className={`${tdNum} text-right`}>{inr(Number(r.cost_inr))}</td>
                        <td className={`${tdNum} text-right`}>{Number(r.co2_t).toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </QueryState>
          </div>
        </Panel>
      </div>
    </>
  );
}
