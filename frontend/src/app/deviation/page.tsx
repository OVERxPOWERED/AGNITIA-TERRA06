"use client";
/** Deviation Shield (H5): DSM charges by strategy (test period) + download next-day 96-block schedule. */
import { Badge, Card, CardTitle } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useDsm } from "@/hooks/api";
import { API_BASE } from "@/lib/api/client";
import { inr, pct } from "@/lib/format";

export default function DeviationPage() {
  const dsm = useDsm();
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Deviation Shield</h1>
        {dsm.data?.illustrative_rates && <Badge tone="warn">Illustrative rates — verify before quoting</Badge>}
      </div>
      <Card>
        <CardTitle>Estimated deviation charges on held-out days (15-min blocks, day-ahead schedule)</CardTitle>
        <QueryState isLoading={dsm.isLoading} error={dsm.error} refetch={dsm.refetch}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-muted"><tr><th className="px-2 py-1">Source</th><th className="px-2 py-1">Schedule from</th><th className="px-2 py-1">Charges</th><th className="px-2 py-1">Blocks outside tolerance</th></tr></thead>
              <tbody>
                {dsm.data?.rows.map((r) => (
                  <tr key={r.source + r.strategy} className={r.strategy === "terra_optimized" ? "font-semibold" : ""}>
                    <td className="px-2 py-1 capitalize">{r.source}</td>
                    <td className="px-2 py-1">{r.strategy.replace("_", " ")}</td>
                    <td className="px-2 py-1">{inr(r.charge_inr)}</td>
                    <td className="px-2 py-1">{pct(r.blocks_outside_tolerance_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {dsm.data && <p className="mt-2 text-xs text-muted">Optimised schedule level: {Object.entries(dsm.data.chosen_level).map(([k, v]) => `${k} P${Math.round(v * 100)}`).join(", ")}. Tolerance: solar ±5%, wind ±10% (CERC, from 1 Apr 2026).</p>}
        </QueryState>
      </Card>
      <Card className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Next-day schedule (96 × 15-min blocks, IST)</CardTitle>
          <p className="text-sm text-muted">Generated from the latest calibrated forecast.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["hybrid", "solar", "wind"] as const).map((s) => (
            <a key={s} className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-border/60"
              href={`${API_BASE}/dsm/schedule.csv?source=${s}`} download={`terra_schedule_${s}.csv`}>Download {s} CSV</a>
          ))}
        </div>
      </Card>
    </div>
  );
}
