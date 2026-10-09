"use client";
/** Deviation shield: estimated deviation charges by scheduling strategy, plus the next-day 96-block schedule to download. */
import React from "react";
import { Download } from "lucide-react";
import { PageHeader, Panel, PanelHeader, Pill, tableCls, tdCls, tdNum, thCls } from "@/components/ui/primitives";
import ScheduleSubmit from "@/components/plant/ScheduleSubmit";
import { QueryState } from "@/components/ui/states";
import { useDsm } from "@/hooks/api";
import { API_BASE } from "@/lib/api/client";
import { inr, pct } from "@/lib/format";

const STRATEGY: Record<string, string> = { persistence: "Persistence schedule", terra_optimized: "Vidyut optimised", terra_p50: "Vidyut median forecast" };

export default function DeviationPage() {
  const dsm = useDsm();
  return (
    <>
      <PageHeader
        title="Deviation shield"
        description="If a plant delivers more or less than it scheduled, the grid charges for the difference. This page shows what that would have cost with different day-ahead schedules."
        actions={dsm.data?.illustrative_rates ? <Pill tone="warn">Illustrative rates. Check before quoting.</Pill> : undefined}
      />
      <div className="space-y-6">
        <Panel>
          <PanelHeader title="Estimated deviation charges on held-out days" note="15-minute blocks, day-ahead schedule, simulating the CERC deviation framework." />
          <div className="px-2 pb-4 pt-3 sm:px-3">
            <QueryState isLoading={dsm.isLoading} error={dsm.error} refetch={dsm.refetch}>
              <div className="overflow-x-auto">
                <table className={tableCls}>
                  <thead><tr><th className={thCls}>Source</th><th className={thCls}>Schedule</th><th className={`${thCls} text-right`}>Charges</th><th className={`${thCls} text-right`}>Blocks outside tolerance</th></tr></thead>
                  <tbody>
                    {dsm.data?.rows.map((r) => (
                      <tr key={r.source + r.strategy} className={r.strategy === "terra_optimized" ? "bg-accent-soft/60" : "hover:bg-sunken/60"}>
                        <td className={`${tdCls} font-medium capitalize`}>{r.source}</td>
                        <td className={tdCls}>{STRATEGY[r.strategy] ?? r.strategy.replaceAll("_", " ")}</td>
                        <td className={`${tdNum} text-right`}>{inr(r.charge_inr)}</td>
                        <td className={`${tdNum} text-right`}>{pct(r.blocks_outside_tolerance_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {dsm.data && (
                <p className="mt-3 max-w-[80ch] px-1 text-[12px] text-muted">
                  The optimised schedule is set at {Object.entries(dsm.data.chosen_level).map(([k, v]) => `${k} P${Math.round(v * 100)}`).join(" and ")}. Tolerance is 5% for solar and 10% for wind under the framework that applies from 1 April 2026. The rupee rates are placeholders, so treat the charges as relative, not absolute.
                </p>
              )}
            </QueryState>
          </div>
        </Panel>
        <Panel>
          <div className="px-4 py-4 sm:px-5">
            <h2 className="text-[15px] font-semibold tracking-tight">Submitted schedule</h2>
            <p className="mb-3 mt-0.5 max-w-[70ch] text-[13px] text-muted">When a newer forecast moves more than the tolerance band away from the schedule you submitted for an hour or more, Vidyut raises a critical alert telling you to revise it with your load despatch centre.</p>
            <ScheduleSubmit />
          </div>
        </Panel>
        <Panel>
          <div className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <div>
              <h2 className="text-[15px] font-semibold tracking-tight">Next-day schedule</h2>
              <p className="mt-0.5 max-w-[60ch] text-[13px] text-muted">96 blocks of 15 minutes in IST, generated from the latest forecast. Download as CSV.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {(["hybrid", "solar", "wind"] as const).map((s) => (
                <a key={s} href={`${API_BASE}/dsm/schedule.csv?source=${s}`} download={`vidyut_schedule_${s}.csv`} className="t-colors inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium capitalize hover:bg-sunken">
                  <Download className="h-3.5 w-3.5 text-muted" aria-hidden />{s} CSV
                </a>
              ))}
            </div>
          </div>
        </Panel>
      </div>
    </>
  );
}
