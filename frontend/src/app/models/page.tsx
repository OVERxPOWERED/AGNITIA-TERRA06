"use client";
/** Models & Accuracy: baseline vs ML comparison (MAE, RMSE, skill, band coverage) + error by lead time. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import EChart from "@/components/charts/EChart";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions } from "@/hooks/api";
import { api } from "@/lib/api/client";
import type { ModelsResponse } from "@/lib/api/types";
import { cssVar } from "@/lib/format";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type Src = "solar" | "wind" | "real";

function useModelsCompare(source: "solar" | "wind", by?: "lead_bucket", daylight?: boolean) {
  return useQuery({
    queryKey: ["models", source, by, daylight],
    queryFn: () =>
      api<ModelsResponse>(
        `/models/compare?source=${source}${by ? `&by=${by}` : ""}${daylight ? "&daylight=true" : ""}`
      ),
  });
}

export default function ModelsPage() {
  const [source, setSource] = useState<Src>("solar");
  const [daylightFilter, setDaylightFilter] = useState<"all" | "daylight">("daylight");
  const isSolar = source === "solar";
  const daylight = isSolar && daylightFilter === "daylight";
  const effectiveSource = source === "real" ? "solar" : source;
  const overall = useModelsCompare(effectiveSource, undefined, daylight);
  const byLead = useModelsCompare(effectiveSource, "lead_bucket", daylight);
  const best = overall.data?.rows
    .filter((r) => r.model !== "persistence" && !r.model.startsWith("chronos2"))
    .sort((a, b) => a.mae - b.mae)[0]?.model;
  const assumptions = useAssumptions();

  const option = useMemo(() => {
    if (!byLead.data || source === "real") return null;
    const rawBuckets = [...new Set(byLead.data.rows.map((r) => r.lead_bucket).filter((b): b is string => Boolean(b)))];
    const parseFirstLead = (b: string) => {
      const m = b.match(/^(\d+)/);
      return m ? parseInt(m[1], 10) : Number.POSITIVE_INFINITY;
    };
    const buckets = rawBuckets.sort((a, b) => parseFirstLead(a) - parseFirstLead(b));
    const models = [...new Set(byLead.data.rows.map((r) => r.model))];
    const palette = [cssVar("--hybrid"), cssVar("--solar"), cssVar("--wind"), cssVar("--demand"), cssVar("--battery"), cssVar("--backup")];
    return {
      grid: { left: 48, right: 16, top: 32, bottom: 32 },
      tooltip: { trigger: "axis" },
      legend: { top: 0, type: "scroll" },
      xAxis: { type: "category", data: buckets, name: "lead (h)" },
      yAxis: { type: "value", name: "nMAE %" },
      series: models.map((m, i) => ({
        name: m, type: "bar",
        data: buckets.map((b) => byLead.data!.rows.find((r) => r.model === m && r.lead_bucket === b)?.nmae_pct ?? null),
        itemStyle: { color: palette[i % palette.length] },
      })),
    };
  }, [byLead.data, source]);

  const viewLabel = source === "solar"
    ? ((overall.data ? overall.data.daylight_only : daylightFilter === "daylight") ? "Daylight only" : "All hours")
    : "All hours";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Models & Accuracy</h1>
        {source === "solar" && (
          <Segmented
            label="Daylight filter"
            value={daylightFilter}
            onChange={setDaylightFilter}
            options={[
              { value: "all", label: "All hours" },
              { value: "daylight", label: "Daylight only" },
            ]}
          />
        )}
        <Segmented label="Source" value={source} onChange={setSource}
          options={[{ value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }, { value: "real", label: "Real data" }]} />
      </div>

      {source === "real" ? (
        <Card>
          <CardTitle>Results on real generation data</CardTitle>
          <QueryState isLoading={assumptions.isLoading} error={assumptions.error} refetch={assumptions.refetch}>
             <div className="prose-sm max-w-none space-y-2 text-sm [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-2 [&_th]:border [&_th]:border-border [&_th]:px-2">
               <ReactMarkdown
                 remarkPlugins={[remarkGfm]}
                 components={{
                   table: ({ children, ...props }) => (
                     <div className="w-full overflow-x-auto my-2">
                       <table {...props}>{children}</table>
                     </div>
                   ),
                 }}
               >
                 {assumptions.data?.real_data_results_md ?? ""}
               </ReactMarkdown>
             </div>
          </QueryState>
        </Card>
      ) : (
        <>
          <Card>
            <CardTitle>Test-period comparison — {viewLabel} (lower error is better; band coverage should be near 80% / 90%)</CardTitle>
            <QueryState isLoading={overall.isLoading} error={overall.error} refetch={overall.refetch}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm tabular-nums">
                  <thead className="text-left text-muted">
                    <tr>{["Model", "MAE MW", "RMSE MW", "nMAE %", "Skill vs persistence", "80% band coverage", "90% band coverage", "Band width %"].map((h) => <th key={h} className="px-2 py-1 font-medium">{h}</th>)}</tr>
                  </thead>
                  <tbody>
                    {overall.data?.rows.map((r) => {
                      const isBenchmark = r.model.startsWith("chronos2");
                      const isBest = r.model === best;
                      return (
                        <tr key={r.model} className={isBest ? "bg-hybrid/10 font-semibold" : ""}>
                          <td className="px-2 py-1">
                            {r.model}
                            {isBest && " ★"}
                            {isBenchmark && (
                              <span className="ml-1.5 rounded bg-muted/20 px-1 py-0.5 text-xs text-muted font-normal">
                                benchmark
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-1">{r.mae.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.rmse.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.nmae_pct.toFixed(2)}</td>
                          <td className="px-2 py-1">{r.skill_vs_persistence == null ? "—" : `${(100 * r.skill_vs_persistence).toFixed(0)}%`}</td>
                          <td className="px-2 py-1">{(100 * r.picp80).toFixed(1)}%</td>
                          <td className="px-2 py-1">{(100 * r.picp90).toFixed(1)}%</td>
                          <td className="px-2 py-1">{r.mpiw80_pct.toFixed(1)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted">Coverage target: 80% / 90%. All-hours solar coverage is inflated by night hours (output is zero).</p>
            </QueryState>
          </Card>
          <Card>
            <CardTitle>Error by lead time</CardTitle>
            <QueryState isLoading={byLead.isLoading} error={byLead.error}>
              {option && <EChart option={option} height={300} ariaLabel="Normalised MAE by lead-time bucket for each model" />}
            </QueryState>
          </Card>
        </>
      )}
    </div>
  );
}
