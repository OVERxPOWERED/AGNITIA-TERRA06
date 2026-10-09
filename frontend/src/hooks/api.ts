"use client";
/** One hook per endpoint. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, API_BASE } from "@/lib/api/client";
import type {
  AlertOut, DispatchResponse, DsmSummary, ForecastResponse, Health, HistoryResponse, ImpactResponse,
  ModelsResponse, SiteInfo, Source, WhatIfRequest, WhatIfResponse,
} from "@/lib/api/types";

import { RETRY_CONFIG, retryDelay, shouldRetry } from "@/lib/api/retry";
import { liveQuery, useActivePlant, type PlantEvaluation } from "@/lib/plant";

export { RETRY_CONFIG, retryDelay, shouldRetry };

const LIVE = { refetchInterval: 60_000, ...RETRY_CONFIG };

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), ...LIVE });

/* Hooks marked "site-aware" read the live run for the selected site when one is active, otherwise the recorded replay. */
export function useSite() {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["site"], queryFn: () => api<SiteInfo>("/site"), ...RETRY_CONFIG });
  if (!ap.live || !ap.site) return q;
  return liveQuery(ap, (r): SiteInfo => ({
    name: r.plant.plant_name, latitude: ap.site!.latitude, longitude: ap.site!.longitude, timezone: "Asia/Kolkata",
    solar_ac_mw: r.plant.solar_ac_mw, wind_mw: r.plant.wind_mw, battery_mw: r.plant.battery_mw, battery_mwh: r.plant.battery_mwh,
    attribution: r.attribution, plant_note: r.caveat,
  })) as unknown as typeof q;
}
export function useForecast(source: Source, horizon = 48) {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["forecast", source, horizon], queryFn: () => api<ForecastResponse>(`/forecast?source=${source}&horizon=${horizon}`), enabled: !ap.live, ...LIVE });
  if (!ap.live) return q;
  return liveQuery(ap, (r): ForecastResponse => {
    const cap = source === "solar" ? r.plant.solar_ac_mw : source === "wind" ? r.plant.wind_mw : r.plant.solar_ac_mw + r.plant.wind_mw;
    return { source, issue_time_utc: r.issue_time_utc, mode: "live", capacity_mw: cap, points: r[source].filter((p) => p.lead_h <= horizon) };
  }) as unknown as typeof q;
}
/* Evaluation-backed hooks: when the operator has uploaded measured history for this site, they return that plant's
 * figures (the same harness, run on their data); otherwise the Dewas evaluation. `usePlantFigures()` says which. */
function fromEval<Q, T>(ap: ReturnType<typeof useActivePlant>, q: Q, pick: (e: PlantEvaluation) => T | undefined): Q {
  if (!ap.evaluation) return q;
  return { data: pick(ap.evaluation), isLoading: false, isError: false, isFetching: false, error: null, refetch: () => {} } as unknown as Q;
}
export const usePlantFigures = () => !!useActivePlant().evaluation;

export function useHistory(source: "solar" | "wind", model = "ensemble") {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["history", source, model], queryFn: () => api<HistoryResponse>(`/forecast/history?source=${source}&model=${model}`), ...RETRY_CONFIG });
  return fromEval(ap, q, (e): HistoryResponse => ({ source, model, lead_h_max: 24, points: model === "ensemble" ? e.history[source] ?? [] : [] }));
}
export function useModels(source: "solar" | "wind", by?: "lead_bucket", daylight = false) {
  const ap = useActivePlant();
  const q = useQuery({
    queryKey: ["models", source, by, daylight],
    queryFn: () => api<ModelsResponse>(`/models/compare?source=${source}${by ? `&by=${by}` : ""}${daylight ? "&daylight=true" : ""}`),
    ...RETRY_CONFIG,
  });
  return fromEval(ap, q, (e): ModelsResponse | undefined => {
    const a = e.accuracy[source];
    if (!a) return { source, split: "test", rows: [], daylight_only: daylight };
    // solar daylight rows are the default view; all-hours rows for "All hours"
    const rows = (by ? a.by_lead : source === "solar" && !daylight ? a.all_hours_rows : a.rows) as unknown as ModelsResponse["rows"];
    return { source, split: "test", rows, daylight_only: daylight && source === "solar" };
  });
}
export function useAlerts() {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["alerts"], queryFn: () => api<AlertOut[]>("/alerts"), enabled: !ap.live, ...LIVE });
  if (!ap.live) return q;
  return liveQuery(ap, (r) => r.alerts) as unknown as typeof q;
}
export function useDispatch(strategy: "advisor" | "rule" | "none" = "advisor") {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["dispatch", strategy], queryFn: () => api<DispatchResponse>(`/dispatch?strategy=${strategy}`), enabled: !ap.live, ...LIVE });
  if (!ap.live) return q;
  return liveQuery(ap, (r): DispatchResponse => ({ strategy, points: r.dispatch_by_strategy[strategy] ?? [], kpis: r.kpis_by_strategy })) as unknown as typeof q;
}
export function useDsm() {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["dsm"], queryFn: () => api<DsmSummary>("/dsm/summary"), ...RETRY_CONFIG });
  return fromEval(ap, q, (e): DsmSummary => ({ illustrative_rates: e.dsm.illustrative_rates, chosen_level: e.dsm.chosen_level, rows: e.dsm.table }));
}
export function useImpact() {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["impact"], queryFn: () => api<ImpactResponse>("/impact"), ...RETRY_CONFIG });
  return fromEval(ap, q, (e): ImpactResponse | undefined => e.impact ? {
    impact: e.impact, value_of_forecast: e.value_of_forecast ?? [], hybrid: {},
    sources: [
      "Your plant's measured history, the last 20% of the uploaded period (days the calibration never saw).",
      "Each day the forecast was re-issued at 05:30 IST from archived weather forecasts, as the live system would have.",
      "The battery was planned with each forecast and settled against what your plant actually produced.",
      "Deviation charges use the configured tolerance bands with illustrative rates.",
    ],
  } : undefined);
}
export const useAssumptions = () =>
  useQuery({ queryKey: ["assumptions"], queryFn: () => api<Record<string, string>>("/assumptions"), ...RETRY_CONFIG });
type TrustSummary = Record<string, { spearman_score_vs_abs_error: number; mae_by_level: Record<string, number> } | null>;
export function useTrustSummary() {
  const ap = useActivePlant();
  const q = useQuery({ queryKey: ["trust-summary"], queryFn: () => api<TrustSummary>("/trust"), ...RETRY_CONFIG });
  return fromEval(ap, q, (e) => e.trust as unknown as TrustSummary);
}
export function useWhatIf() {
  const ap = useActivePlant();
  const job = ap.live ? ap.jobId : null;
  return useMutation({ mutationFn: (body: WhatIfRequest) => api<WhatIfResponse>(`/whatif${job ? `?job_id=${job}` : ""}`, { method: "POST", body: JSON.stringify(body) }) });
}
export const ackAlert = (id: string) => api<{ ok: boolean }>(`/alerts/${encodeURIComponent(id)}/ack`, { method: "POST" });

/** Subscribe to Server-Sent Events; refresh cached data when a new run completes. */
export function useLiveUpdates(onAlert?: (a: AlertOut) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/alerts/stream`);
    es.addEventListener("run_complete", () => qc.invalidateQueries());
    es.addEventListener("alert", (e) => onAlert?.(JSON.parse((e as MessageEvent).data)));
    return () => es.close();
  }, [qc, onAlert]);
}
