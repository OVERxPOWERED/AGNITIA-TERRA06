"use client";
/** Deviation Shield: DSM charges by strategy (test period) + download next-day 96-block schedule. */
import React from "react";
import { Download } from "lucide-react";
import { Badge, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDsm } from "@/hooks/api";
import { API_BASE } from "@/lib/api/client";
import { inr, pct } from "@/lib/format";

export default function DeviationPage() {
  const dsm = useDsm();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Deviation Shield</h1>
          <p className="text-xs text-muted mt-0.5">
            Deviation Settlement Mechanism (DSM) penalty risk assessment & optimized schedule
          </p>
        </div>
        {dsm.data?.illustrative_rates && (
          <Badge tone="warn" className="text-xs py-1 px-3">
            Illustrative rates — verify before quoting
          </Badge>
        )}
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">
            Estimated deviation charges on held-out days (15-min blocks, day-ahead schedule)
          </CardTitle>
          <span className="text-xs text-muted">CERC DSM regulation simulation</span>
        </div>
        <QueryState isLoading={dsm.isLoading} error={dsm.error} refetch={dsm.refetch}>
          <div className="overflow-x-auto rounded-lg border border-border/80">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-xs uppercase tracking-wider text-muted bg-panel-muted/50 border-b border-border">
                <tr>
                  <th className="px-3 py-2.5 font-semibold">Source</th>
                  <th className="px-3 py-2.5 font-semibold">Schedule strategy</th>
                  <th className="px-3 py-2.5 font-semibold">Charges</th>
                  <th className="px-3 py-2.5 font-semibold">Blocks outside tolerance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {dsm.data?.rows.map((r) => {
                  const isOptimized = r.strategy === "terra_optimized";
                  return (
                    <tr
                      key={r.source + r.strategy}
                      className={
                        isOptimized
                          ? "bg-accent/10 font-semibold text-text"
                          : "hover:bg-panel-muted/30 transition-colors"
                      }
                    >
                      <td className="px-3 py-2.5 capitalize font-medium">{r.source}</td>
                      <td className="px-3 py-2.5">
                        <span className="inline-flex items-center gap-1.5">
                          <span>{r.strategy.replace("_", " ")}</span>
                          {isOptimized && (
                            <span className="text-[10px] rounded bg-accent/20 text-accent font-semibold px-1.5 py-0.5 uppercase">
                              Optimized
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 font-semibold">{inr(r.charge_inr)}</td>
                      <td className="px-3 py-2.5">{pct(r.blocks_outside_tolerance_pct)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {dsm.data && (
            <p className="mt-2 text-xs text-muted leading-relaxed">
              Optimized schedule level:{" "}
              <strong className="text-text">
                {Object.entries(dsm.data.chosen_level)
                  .map(([k, v]) => `${k} P${Math.round(v * 100)}`)
                  .join(", ")}
              </strong>
              . Tolerances: solar ±5%, wind ±10% (CERC DSM framework, applicable from 1 Apr 2026).
            </p>
          )}
        </QueryState>
      </Card>

      <Card className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5">
        <div className="space-y-1">
          <CardTitle className="mb-0">Next-day schedule (96 × 15-min blocks, IST)</CardTitle>
          <p className="text-xs text-muted">
            Export regulatory submission schedules generated from the latest calibrated forecast.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          {(["hybrid", "solar", "wind"] as const).map((s) => (
            <a
              key={s}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-panel px-3.5 py-2 text-xs font-medium text-text hover:bg-border/60 transition-colors shadow-xs"
              href={`${API_BASE}/dsm/schedule.csv?source=${s}`}
              download={`terra_schedule_${s}.csv`}
            >
              <Download className="h-3.5 w-3.5 text-muted" />
              <span>Download {s} CSV</span>
            </a>
          ))}
        </div>
      </Card>
    </div>
  );
}
