"use client";
/** Models and accuracy: every model on the held-out test period, plus how error grows with lead time. */
import React, { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import Markdown from "@/components/ui/Markdown";
import { PageHeader, Panel, PanelHeader, Pill, Segmented, tableCls, tdCls, tdNum, thCls } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions, useModels } from "@/hooks/api";
import { useTheme, type Palette } from "@/lib/theme";

type Src = "solar" | "wind" | "real";

const modelColor = (c: Palette): Record<string, string> => ({
  ensemble: c.hybrid, gbm: c.wind, physics: c.solar, persistence: c.faint, week_mean: c.backup, chronos2_zs: c.battery,
});

export default function ModelsPage() {
  const { colors: c } = useTheme();
  const [source, setSource] = useState<Src>("solar");
  const [view, setView] = useState<"all" | "daylight">("daylight");
  const eff = source === "real" ? "solar" : source;
  const daylight = source === "solar" && view === "daylight";
  const overall = useModels(eff, undefined, daylight);
  const byLead = useModels(eff, "lead_bucket", daylight);
  const docs = useAssumptions();

  // "Best" only considers models that actually serve forecasts: not the naive baseline, not the benchmark.
  const best = overall.data?.rows.filter((r) => r.model !== "persistence" && !r.model.startsWith("chronos2")).sort((a, b) => a.mae - b.mae || (a.model === "ensemble" ? -1 : b.model === "ensemble" ? 1 : 0))[0]?.model;

  const option = useMemo(() => {
    const rows = byLead.data?.rows;
    if (!rows?.length || source === "real") return null;
    const first = (b: string) => Number(/^(\d+)/.exec(b)?.[1] ?? 1e9);
    const buckets = [...new Set(rows.map((r) => r.lead_bucket).filter((b): b is string => Boolean(b)))].sort((a, b) => first(a) - first(b));
    const models = [...new Set(rows.map((r) => r.model))];
    const col = modelColor(c);
    const mono = { color: c.muted, fontSize: 11, fontFamily: "var(--font-geist-mono), monospace" };
    return {
      backgroundColor: "transparent", aria: { enabled: true },
      grid: { left: 44, right: 12, top: 48, bottom: 30 },
      legend: { top: 4, left: 44, type: "scroll" as const, icon: "roundRect", itemWidth: 12, itemHeight: 8, textStyle: { color: c.ink, fontSize: 12 } },
      tooltip: { trigger: "axis" as const, backgroundColor: c.surface, borderColor: c.line, textStyle: { color: c.ink, fontSize: 12 }, valueFormatter: (v: unknown) => `${Number(v).toFixed(2)}% nMAE` },
      xAxis: { type: "category" as const, data: buckets.map((b) => `${b} h ahead`), axisLine: { lineStyle: { color: c.line } }, axisTick: { show: false }, axisLabel: mono },
      yAxis: { type: "value" as const, name: "nMAE %", nameTextStyle: { ...mono, align: "right" as const }, axisLabel: mono, splitLine: { lineStyle: { color: c.line } } },
      series: models.map((m) => ({
        name: m, type: "bar" as const, barMaxWidth: 26, itemStyle: { color: col[m] ?? c.muted, borderRadius: [3, 3, 0, 0] },
        data: buckets.map((b) => rows.find((r) => r.model === m && r.lead_bucket === b)?.nmae_pct ?? null),
      })),
    };
  }, [byLead.data, source, c]);

  const viewLabel = source === "solar" ? (daylight ? "daylight hours only" : "all hours") : "all hours";

  return (
    <>
      <PageHeader
        title="Models and accuracy"
        description="How each model performed on days it never saw during training. Lower error is better; the 80% and 90% ranges should cover about that share of actual values."
        actions={<>
          {source === "solar" && <Segmented label="Solar hours" value={view} onChange={setView} options={[{ value: "all", label: "All hours" }, { value: "daylight", label: "Daylight only" }]} />}
          <Segmented label="Source" value={source} onChange={setSource} options={[{ value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }, { value: "real", label: "Real data" }]} />
        </>}
      />
      {source === "real" ? (
        <Panel>
          <PanelHeader title="Results on real generation data" note="Benchmarks against measured generation from other plants and the national grid." />
          <div className="px-4 pb-5 pt-2 sm:px-5">
            <QueryState isLoading={docs.isLoading} error={docs.error} refetch={docs.refetch}><Markdown>{docs.data?.real_data_results_md ?? ""}</Markdown></QueryState>
          </div>
        </Panel>
      ) : (
        <div className="space-y-6">
          <Panel>
            <PanelHeader title={`Test-period comparison, ${viewLabel}`} note="The star marks the lowest error among the models that serve forecasts. The benchmark is run for comparison only." />
            <div className="px-2 pb-4 pt-3 sm:px-3">
              <QueryState isLoading={overall.isLoading} error={overall.error} refetch={overall.refetch}>
                <div className="overflow-x-auto">
                  <table className={tableCls}>
                    <thead><tr>{["Model", "MAE (MW)", "RMSE (MW)", "nMAE", "Skill over persistence", "80% range covers", "90% range covers", "Band width"].map((h, i) => <th key={h} className={`${thCls} ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
                    <tbody>
                      {overall.data?.rows.map((r) => (
                        <tr key={r.model} className={r.model === best ? "bg-accent-soft/60" : "hover:bg-sunken/60"}>
                          <td className={`${tdCls} font-medium`}>
                            <span className="inline-flex items-center gap-2">
                              <span className="num">{r.model}</span>
                              {r.model === best && <span title="Lowest error among serving models" aria-label="Lowest error among serving models" className="text-accent">★</span>}
                              {r.model.startsWith("chronos2") && <Pill>benchmark</Pill>}
                            </span>
                          </td>
                          <td className={`${tdNum} text-right`}>{r.mae.toFixed(2)}</td>
                          <td className={`${tdNum} text-right`}>{r.rmse.toFixed(2)}</td>
                          <td className={`${tdNum} text-right`}>{r.nmae_pct.toFixed(2)}%</td>
                          <td className={`${tdNum} text-right`}>{r.skill_vs_persistence == null ? "—" : `${(100 * r.skill_vs_persistence).toFixed(0)}%`}</td>
                          <td className={`${tdNum} text-right`}>{(100 * r.picp80).toFixed(1)}%</td>
                          <td className={`${tdNum} text-right`}>{(100 * r.picp90).toFixed(1)}%</td>
                          <td className={`${tdNum} text-right`}>{r.mpiw80_pct.toFixed(1)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 px-1 text-[12px] text-muted">Coverage targets are 80% and 90%. Solar coverage over all hours looks better than it is, because at night both the forecast and the actual value are zero; the daylight view removes that.</p>
              </QueryState>
            </div>
          </Panel>
          <Panel>
            <PanelHeader title="Error by how far ahead" note="Normalised error (nMAE) for each model, split by forecast lead time." />
            <div className="px-2 pb-3 pt-2 sm:px-3">
              <QueryState isLoading={byLead.isLoading} error={byLead.error} refetch={byLead.refetch} height="h-[320px]">
                {option && <EChart option={option} height={320} ariaLabel="Normalised error by lead time for each model" />}
              </QueryState>
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
