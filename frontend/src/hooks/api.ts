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
import { liveQuery, useActivePlant } from "@/lib/plant";

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
export const useHistory = (source: "solar" | "wind", model = "ensemble") =>
  useQuery({ queryKey: ["history", source, model], queryFn: () => api<HistoryResponse>(`/forecast/history?source=${source}&model=${model}`), ...RETRY_CONFIG });
export const useModels = (source: "solar" | "wind", by?: "lead_bucket", daylight = false) =>
  useQuery({
    queryKey: ["models", source, by, daylight],
    queryFn: () => api<ModelsResponse>(`/models/compare?source=${source}${by ? `&by=${by}` : ""}${daylight ? "&daylight=true" : ""}`),
    ...RETRY_CONFIG,
  });
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
export const useDsm = () => useQuery({ queryKey: ["dsm"], queryFn: () => api<DsmSummary>("/dsm/summary"), ...RETRY_CONFIG });
export const useImpact = () => useQuery({ queryKey: ["impact"], queryFn: () => api<ImpactResponse>("/impact"), ...RETRY_CONFIG });
export const useAssumptions = () =>
  useQuery({ queryKey: ["assumptions"], queryFn: () => api<Record<string, string>>("/assumptions"), ...RETRY_CONFIG });
export const useTrustSummary = () =>
  useQuery({ queryKey: ["trust-summary"], queryFn: () => api<Record<string, { spearman_score_vs_abs_error: number; mae_by_level: Record<string, number> } | null>>("/trust"), ...RETRY_CONFIG });
export const useWhatIf = () =>
  useMutation({ mutationFn: (body: WhatIfRequest) => api<WhatIfResponse>("/whatif", { method: "POST", body: JSON.stringify(body) }) });
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
