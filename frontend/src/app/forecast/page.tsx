"use client";
/** Forecast Explorer: how one source and one model did against what was actually generated, then the next 48 hours. */
import React, { useMemo, useState } from "react";
import ConfidenceStrip from "@/components/charts/ConfidenceStrip";
import EChart from "@/components/charts/EChart";
import { GRID_LEFT, GRID_RIGHT, bandSeries, istMs, lineSeries, timeChart, type BandPoint } from "@/components/charts/series";
import { PageHeader, Panel, PanelHeader, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useForecast, useHistory } from "@/hooks/api";
import { useActivePlant } from "@/lib/plant";
import { useTheme } from "@/lib/theme";

type Src = "solar" | "wind";
const MODELS = ["ensemble", "gbm", "physics", "persistence", "chronos2_zs"] as const;
type ModelKey = (typeof MODELS)[number];
const MODEL_LABELS: Record<ModelKey, string> = { ensemble: "Ensemble", gbm: "LightGBM", physics: "Physics", persistence: "Persistence", chronos2_zs: "Chronos-2 (benchmark)" };

export default function ForecastPage() {
  const { colors: c } = useTheme();
  const [source, setSource] = useState<Src>("solar");
  const [model, setModel] = useState<ModelKey>("ensemble");
  const ap = useActivePlant();
  const hist = useHistory(source, model);
  const fc = useForecast(source);
  const color = source === "solar" ? c.solar : c.wind;
  const name = source === "solar" ? "Solar" : "Wind";

  const histOption = useMemo(() => {
    const pts = hist.data?.points;
    if (!pts?.length) return null;
    const band: BandPoint[] = pts.map((p) => ({ t: istMs(p.target_time_utc), lo: p.q10, mid: p.q50, hi: p.q90 }));
    return timeChart({
      c, unit: "MW", tMin: band[0].t, tMax: band[band.length - 1].t, tickHours: 24, bottom: 56, bands: { f: band },
      series: [...bandSeries(`${name} forecast`, band, color, "f", { width: 1.8 }), lineSeries("Actual", pts.map((p) => [istMs(p.target_time_utc), p.actual_mw]), c.ink, { width: 1.2, id: "actual-line", z: 4 })],
      extra: { dataZoom: [{ type: "inside" }, { type: "slider", height: 18, bottom: 8, borderColor: c.line, fillerColor: `${color}22`, handleSize: 14, textStyle: { color: c.muted, fontSize: 10 } }] },
    });
  }, [hist.data, c, color, name]);

  const nextOption = useMemo(() => {
    const pts = fc.data?.points;
    if (!pts?.length) return null;
    const band: BandPoint[] = pts.map((p) => ({ t: istMs(p.target_time_utc), lo: p.q10, mid: p.q50, hi: p.q90 }));
    return timeChart({ c, unit: "MW", tMin: band[0].t, tMax: band[band.length - 1].t, bands: { n: band }, series: bandSeries(`${name} forecast`, band, color, "n", { width: 2.4 }) });
  }, [fc.data, c, color, name]);

  return (
    <>
      <PageHeader
        title="Forecast explorer"
        description="Pick a source and a model to see how its forecasts compared with what was actually generated, then the latest 48-hour forecast."
        actions={<>
          <Segmented label="Source" value={source} onChange={setSource} options={[{ value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }]} />
          <Segmented label="Model" value={model} onChange={setModel} options={MODELS.map((m) => ({ value: m, label: MODEL_LABELS[m] }))} />
        </>}
      />
      <div className="space-y-6">
        <Panel>
          <PanelHeader title="Forecast against actual generation" note={`${ap.live ? "Dewas evaluation, not " + ap.label + ". " : ""}Held-out test days, forecast issued the morning before (05:30 IST). Drag the bar below the chart to zoom.`} />
          <div className="px-2 pb-3 pt-2 sm:px-3">
            <QueryState isLoading={hist.isLoading} error={hist.error} refetch={hist.refetch} empty={!hist.data?.points.length} height="h-[380px]">
              {histOption && <EChart option={histOption} height={380} ariaLabel={`${MODEL_LABELS[model]} forecast against actual ${source} generation`} />}
            </QueryState>
          </div>
        </Panel>
        <Panel>
          <PanelHeader title={`${name}: next 48 hours`} note={`${ap.live ? ap.label + ". " : ""}Calibrated ensemble with its 80% range.`} />
          <div className="px-2 pb-3 pt-2 sm:px-3">
            <QueryState isLoading={fc.isLoading} error={fc.error} refetch={fc.refetch} height="h-[320px]">
              {nextOption && <EChart option={nextOption} height={320} ariaLabel={`${source} forecast for the next 48 hours`} />}
            </QueryState>
          </div>
          {fc.data && (
            <div className="border-t border-line px-2 pb-4 pt-3 sm:px-3">
              <div className="mb-2 text-[13px] font-medium" style={{ paddingLeft: GRID_LEFT }}>Forecast confidence by hour</div>
              <ConfidenceStrip points={fc.data.points} padLeft={GRID_LEFT} padRight={GRID_RIGHT} />
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
