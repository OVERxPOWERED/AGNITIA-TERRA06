"use client";
/** Forecast Explorer: actual vs predicted on held-out days + the next 48 h for one source/model. */
import React, { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useHistory } from "@/hooks/api";

type Src = "solar" | "wind";
const MODELS = ["ensemble", "gbm", "physics", "persistence", "chronos2_zs"] as const;
type ModelKey = (typeof MODELS)[number];

const MODEL_LABELS: Record<ModelKey, string> = {
  ensemble: "Ensemble",
  gbm: "LightGBM",
  physics: "Physics",
  persistence: "Persistence",
  chronos2_zs: "Chronos-2 (Zero-shot)",
};

import { useTheme } from "@/lib/theme";

export default function ForecastPage() {
  const { resolvedTheme, colors } = useTheme();
  const [source, setSource] = useState<Src>("solar");
  const [model, setModel] = useState<ModelKey>("ensemble");
  const hist = useHistory(source, model);
  const fc = useForecast(source);
  const color = source === "solar" ? colors.solar : colors.wind;

  const histOption = useMemo(() => {
    if (!hist.data) return null;
    const pts = hist.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return {
      ...timeAxisOption("MW", {}, resolvedTheme),
      dataZoom: [
        { type: "inside" },
        {
          type: "slider",
          height: 20,
          bottom: 4,
          borderColor: colors.border,
          fillerColor: resolvedTheme === "dark" ? "rgba(129, 140, 248, 0.18)" : "rgba(67, 56, 202, 0.12)",
          textStyle: { color: colors.muted, fontSize: 11 },
        },
      ],
      series: [
        ...bandSeries("Forecast", pts, color, "h"),
        {
          name: "Actual",
          type: "line",
          data: hist.data.points.map((p) => [p.target_time_utc, p.actual_mw]),
          lineStyle: { color: colors.text, width: 1.5 },
          itemStyle: { color: colors.text },
          symbol: "none",
        },
      ],
    };
  }, [hist.data, color, colors, resolvedTheme]);

  const fcOption = useMemo(() => {
    if (!fc.data) return null;
    const pts = fc.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return {
      ...timeAxisOption("MW", {}, resolvedTheme),
      series: bandSeries("Next 48 h", pts, color, "f"),
    };
  }, [fc.data, color, resolvedTheme]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Forecast Explorer</h1>
          <p className="text-xs text-muted mt-0.5">
            Single-asset backtest vs actuals & next 48-hour forward projection
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            label="Source"
            value={source}
            onChange={setSource}
            options={[
              { value: "solar", label: "Solar" },
              { value: "wind", label: "Wind" },
            ]}
          />
          <Segmented
            label="Model"
            value={model}
            onChange={setModel}
            options={MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))}
          />
        </div>
      </div>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">
            Actual vs predicted — held-out test days (day-ahead, issued 05:30 IST)
          </CardTitle>
          <span className="text-xs text-muted">Use slider below chart to zoom time range</span>
        </div>
        <QueryState
          isLoading={hist.isLoading}
          error={hist.error}
          refetch={hist.refetch}
          empty={!hist.data?.points.length}
          height="h-[360px]"
        >
          {histOption && (
            <EChart
              option={histOption}
              height={340}
              ariaLabel={`Actual versus ${model} forecast for ${source}`}
            />
          )}
        </QueryState>
      </Card>

      <Card className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="mb-0">Next 48 hours (calibrated ensemble)</CardTitle>
          <span className="text-xs text-muted">Forward projection with hourly trust ribbon</span>
        </div>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-[320px]">
          {fcOption && (
            <EChart
              option={fcOption}
              height={300}
              ariaLabel={`${source} forecast next 48 hours`}
            />
          )}
          {fc.data && (
            <div className="pt-2 border-t border-border/50">
              <TrustRibbon points={fc.data.points} />
            </div>
          )}
        </QueryState>
      </Card>
    </div>
  );
}
