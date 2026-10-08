"use client";
/** Models & Accuracy: baseline vs ML comparison (MAE, RMSE, skill, band coverage) + error by lead time. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useModels } from "@/hooks/api";
import { cssVar } from "@/lib/format";

type Src = "solar" | "wind";

export default function ModelsPage() {
  const [source, setSource] = useState<Src>("solar");
  const overall = useModels(source);
  const byLead = useModels(source, "lead_bucket");
  const best = overall.data?.rows.filter((r) => r.model !== "persistence").sort((a, b) => a.mae - b.mae)[0]?.model;

  const option = useMemo(() => {
    if (!byLead.data) return null;
    const buckets = ["1-12", "13-36", "37-48"];
    const models = [...new Set(byLead.data.rows.map((r) => r.model))];
    const palette = [cssVar("--hybrid"), cssVar("--solar"), cssVar("--wind"), cssVar("--demand"), cssVar("--battery"), cssVar("--backup")];
    return {
      grid: { left: 48, right: 16, top: 32, bottom: 32 },
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      xAxis: { type: "category", data: buckets, name: "lead (h)" },
      yAxis: { type: "value", name: "nMAE %" },
      series: models.map((m, i) => ({
        name: m, type: "bar",
        data: buckets.map((b) => byLead.data!.rows.find((r) => r.model === m && r.lead_bucket === b)?.nmae_pct ?? null),
        itemStyle: { color: palette[i % palette.length] },
      })),
    };
  }, [byLead.data]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Models & Accuracy</h1>
        <Segmented label="Source" value={source} onChange={setSource}
          options={[{ value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }]} />
      </div>
      <Card>
        <CardTitle>Test-period comparison (lower error is better; band coverage should be near 80% / 90%)</CardTitle>
        <QueryState isLoading={overall.isLoading} error={overall.error} refetch={overall.refetch}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm tabular-nums">
              <thead className="text-left text-muted">
                <tr>{["Model", "MAE MW", "RMSE MW", "nMAE %", "Skill vs persistence", "80% band coverage", "90% band coverage", "Band width %"].map((h) => <th key={h} className="px-2 py-1 font-medium">{h}</th>)}</tr>
              </thead>
              <tbody>
                {overall.data?.rows.map((r) => (
                  <tr key={r.model} className={r.model === best ? "bg-hybrid/10 font-semibold" : ""}>
                    <td className="px-2 py-1">{r.model}{r.model === best && " ★"}</td>
                    <td className="px-2 py-1">{r.mae.toFixed(2)}</td>
                    <td className="px-2 py-1">{r.rmse.toFixed(2)}</td>
                    <td className="px-2 py-1">{r.nmae_pct.toFixed(2)}</td>
                    <td className="px-2 py-1">{r.skill_vs_persistence == null ? "—" : `${(100 * r.skill_vs_persistence).toFixed(0)}%`}</td>
                    <td className="px-2 py-1">{(100 * r.picp80).toFixed(1)}%</td>
                    <td className="px-2 py-1">{(100 * r.picp90).toFixed(1)}%</td>
                    <td className="px-2 py-1">{r.mpiw80_pct.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Error by lead time</CardTitle>
        <QueryState isLoading={byLead.isLoading} error={byLead.error}>
          {option && <EChart option={option} height={300} ariaLabel="Normalised MAE by lead-time bucket for each model" />}
        </QueryState>
      </Card>
    </div>
  );
}
