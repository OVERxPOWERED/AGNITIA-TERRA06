"use client";
/** Models & Accuracy: baseline vs ML comparison (MAE, RMSE, skill, band coverage) + error by lead time. */
import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import EChart from "@/components/charts/EChart";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions } from "@/hooks/api";
import { api } from "@/lib/api/client";
import type { ModelsResponse } from "@/lib/api/types";
import { useTheme } from "@/lib/theme";

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
  const { resolvedTheme, colors } = useTheme();
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
    const palette = [
      colors.hybrid,
      colors.solar,
      colors.wind,
      colors.demand,
      colors.battery,
      colors.backup,
    ];
    const isDark = resolvedTheme === "dark";
    const splitLineColor = isDark ? "rgba(42, 52, 74, 0.45)" : "rgba(226, 226, 220, 0.6)";

    return {
      grid: { left: 16, right: 16, top: 52, bottom: 24, containLabel: true },
      tooltip: {
        trigger: "axis",
        backgroundColor: colors.panel,
        borderColor: colors.border,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: colors.text,
          fontSize: 12,
          fontFamily: "var(--font-geist-sans), sans-serif",
        },
        extraCssText: "box-shadow: 0 4px 16px rgba(0, 0, 0, 0.16); border-radius: 8px;",
        formatter: (raw: unknown) => {
          const params = (Array.isArray(raw) ? raw : [raw]) as Array<{
            seriesName?: string;
            marker?: string;
            value?: unknown;
            axisValue?: string;
          }>;
          const lead = params[0]?.axisValue ? `Lead: ${params[0].axisValue} h` : "";
          const rows = params
            .filter((p) => p.value != null && !Number.isNaN(Number(p.value)))
            .map(
              (p) => `<div style="display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:3px;">
                <span>${p.marker ?? ""} <strong style="color:${colors.text};">${p.seriesName}</strong></span>
                <span style="font-variant-numeric:tabular-nums;font-weight:600;color:${colors.text};">${Number(p.value).toFixed(2)}% nMAE</span>
              </div>`
            );
          return `<div style="font-family:var(--font-geist-sans),sans-serif;font-size:12px;">
            <div style="font-weight:600;color:${colors.muted};border-bottom:1px solid ${colors.border};padding-bottom:5px;margin-bottom:5px;">
              ${lead}
            </div>
            ${rows.join("")}
          </div>`;
        },
      },
      legend: {
        top: 2,
        type: "scroll",
        textStyle: {
          color: isDark ? "#E2E8F0" : "#27272A", // AA contrast in both themes
          fontSize: 12,
          fontWeight: "500",
        },
      },
      xAxis: {
        type: "category",
        data: buckets,
        name: "lead (h)",
        nameTextStyle: { color: colors.muted, fontSize: 11 },
        axisLine: { lineStyle: { color: colors.border } },
        axisTick: { lineStyle: { color: colors.border } },
        axisLabel: { color: colors.muted, fontSize: 11 },
      },
      yAxis: {
        type: "value",
        name: "nMAE %",
        nameTextStyle: { color: colors.muted, fontSize: 11 },
        splitLine: {
          show: true,
          lineStyle: { color: splitLineColor, width: 1 },
        },
        axisLabel: { color: colors.muted, fontSize: 11 },
      },
      series: models.map((m, i) => ({
        name: m,
        type: "bar",
        data: buckets.map((b) => byLead.data!.rows.find((r) => r.model === m && r.lead_bucket === b)?.nmae_pct ?? null),
        itemStyle: { color: palette[i % palette.length], borderRadius: [3, 3, 0, 0] },
      })),
    };
  }, [byLead.data, source, colors, resolvedTheme]);

  const viewLabel =
    source === "solar"
      ? (overall.data ? overall.data.daylight_only : daylightFilter === "daylight")
        ? "Daylight only"
        : "All hours"
      : "All hours";

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Models & Accuracy</h1>
          <p className="text-xs text-muted mt-0.5">
            Statistical benchmark comparison across ML architectures & lead times
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
          <Segmented
            label="Source"
            value={source}
            onChange={setSource}
            options={[
              { value: "solar", label: "Solar" },
              { value: "wind", label: "Wind" },
              { value: "real", label: "Real data" },
            ]}
          />
        </div>
      </div>

      {source === "real" ? (
        <Card className="space-y-3">
          <CardTitle>Results on real generation data</CardTitle>
          <QueryState isLoading={assumptions.isLoading} error={assumptions.error} refetch={assumptions.refetch}>
            <div className="prose-sm max-w-none space-y-2 text-sm [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5 [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-panel-muted/50">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children, ...props }) => (
                    <div className="w-full overflow-x-auto my-2 rounded-lg border border-border">
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
          <Card className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="mb-0">
                Test-period comparison — {viewLabel}
              </CardTitle>
              <span className="text-xs text-muted">Coverage target: 80% / 90%</span>
            </div>
            <QueryState isLoading={overall.isLoading} error={overall.error} refetch={overall.refetch}>
              <div className="overflow-x-auto rounded-lg border border-border/80">
                <table className="w-full text-sm tabular-nums">
                  <thead className="text-left text-xs uppercase tracking-wider text-muted bg-panel-muted/50 border-b border-border">
                    <tr>
                      {[
                        "Model",
                        "MAE MW",
                        "RMSE MW",
                        "nMAE %",
                        "Skill vs persistence",
                        "80% coverage",
                        "90% coverage",
                        "Band width %",
                      ].map((h) => (
                        <th key={h} className="px-3 py-2.5 font-semibold">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {overall.data?.rows.map((r) => {
                      const isBenchmark = r.model.startsWith("chronos2");
                      const isBest = r.model === best;
                      return (
                        <tr
                          key={r.model}
                          className={
                            isBest
                              ? "bg-accent/10 font-semibold text-text"
                              : "hover:bg-panel-muted/30 transition-colors"
                          }
                        >
                          <td className="px-3 py-2.5">
                            <span className="inline-flex items-center gap-1.5">
                              <span>{r.model}</span>
                              {isBest && (
                                <span className="text-xs text-accent font-bold" title="Best performer">
                                  ★
                                </span>
                              )}
                              {isBenchmark && (
                                <span className="rounded bg-muted/20 px-1.5 py-0.5 text-[10px] text-muted font-normal uppercase">
                                  benchmark
                                </span>
                              )}
                            </span>
                          </td>
                          <td className="px-3 py-2.5">{r.mae.toFixed(2)}</td>
                          <td className="px-3 py-2.5">{r.rmse.toFixed(2)}</td>
                          <td className="px-3 py-2.5">{r.nmae_pct.toFixed(2)}%</td>
                          <td className="px-3 py-2.5">
                            {r.skill_vs_persistence == null ? "—" : `${(100 * r.skill_vs_persistence).toFixed(0)}%`}
                          </td>
                          <td className="px-3 py-2.5">{(100 * r.picp80).toFixed(1)}%</td>
                          <td className="px-3 py-2.5">{(100 * r.picp90).toFixed(1)}%</td>
                          <td className="px-3 py-2.5">{r.mpiw80_pct.toFixed(1)}%</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted">
                Note: All-hours solar coverage is inflated by night hours (zero irradiance). Daylight filter isolates active generation hours.
              </p>
            </QueryState>
          </Card>

          <Card className="space-y-3">
            <CardTitle>Error by lead time</CardTitle>
            <QueryState isLoading={byLead.isLoading} error={byLead.error} height="h-[320px]">
              {option && (
                <EChart
                  option={option}
                  height={300}
                  ariaLabel="Normalised MAE by lead-time bucket for each model"
                />
              )}
            </QueryState>
          </Card>
        </>
      )}
    </div>
  );
}
