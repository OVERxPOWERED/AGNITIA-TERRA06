"use client";
/** Forecast Explorer: actual vs predicted on held-out days + the next 48 h for one source/model. */
import { useMemo, useState } from "react";
import EChart from "@/components/charts/EChart";
import { bandSeries, timeAxisOption } from "@/components/charts/series";
import TrustRibbon from "@/components/charts/TrustRibbon";
import { Card, CardTitle, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useHistory } from "@/hooks/api";
import { cssVar } from "@/lib/format";

type Src = "solar" | "wind";
const MODELS = ["ensemble", "gbm", "physics", "persistence"] as const;

export default function ForecastPage() {
  const [source, setSource] = useState<Src>("solar");
  const [model, setModel] = useState<(typeof MODELS)[number]>("ensemble");
  const hist = useHistory(source, model);
  const fc = useForecast(source);
  const color = cssVar(source === "solar" ? "--solar" : "--wind");

  const histOption = useMemo(() => {
    if (!hist.data) return null;
    const pts = hist.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return {
      ...timeAxisOption("MW"),
      dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 4 }],
      series: [...bandSeries("Forecast", pts, color, "h"),
        { name: "Actual", type: "line", data: hist.data.points.map((p) => [p.target_time_utc, p.actual_mw]),
          lineStyle: { color: cssVar("--text"), width: 1.2 }, itemStyle: { color: cssVar("--text") }, symbol: "none" }],
    };
  }, [hist.data, color]);

  const fcOption = useMemo(() => {
    if (!fc.data) return null;
    const pts = fc.data.points.map((p) => ({ t: p.target_time_utc, lo: p.q10, mid: p.q50, hi: p.q90 }));
    return { ...timeAxisOption("MW"), series: bandSeries("Next 48 h", pts, color, "f") };
  }, [fc.data, color]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Forecast Explorer</h1>
        <Segmented label="Source" value={source} onChange={setSource}
          options={[{ value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }]} />
        <Segmented label="Model" value={model} onChange={setModel} options={MODELS.map((m) => ({ value: m, label: m }))} />
      </div>
      <Card>
        <CardTitle>Actual vs predicted — held-out test days (day-ahead, issued 05:30 IST)</CardTitle>
        <QueryState isLoading={hist.isLoading} error={hist.error} refetch={hist.refetch} empty={!hist.data?.points.length}>
          {histOption && <EChart option={histOption} height={340} ariaLabel={`Actual versus ${model} forecast for ${source}`} />}
        </QueryState>
      </Card>
      <Card>
        <CardTitle>Next 48 hours (calibrated ensemble)</CardTitle>
        <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch}>
          {fcOption && <EChart option={fcOption} height={300} ariaLabel={`${source} forecast next 48 hours`} />}
          {fc.data && <div className="mt-3"><TrustRibbon points={fc.data.points} /></div>}
        </QueryState>
      </Card>
    </div>
  );
}
