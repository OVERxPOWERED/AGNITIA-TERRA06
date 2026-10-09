"use client";
/** One hook per endpoint. Components never call fetch directly. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, API_BASE, ApiError } from "@/lib/api/client";
import type {
  AlertOut, DispatchResponse, DsmSummary, ForecastResponse, Health, HistoryResponse, ImpactResponse,
  ModelsResponse, SiteInfo, Source, WhatIfRequest, WhatIfResponse,
} from "@/lib/api/types";

/**
 * TanStack Query retry policy for waking up cold backend instances (e.g. Render free tier).
 * - Up to 12 retries for network errors and HTTP 502/503/504
 * - Explicitly skips 4xx client errors and 503 NO_DATA_YET (which is a valid state)
 * - Exponential backoff capped at 8 seconds
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 12) return false;
  if (error instanceof ApiError) {
    if (error.status >= 400 && error.status < 500) return false;
    if (error.status === 503 && error.code === "NO_DATA_YET") return false;
    if ([502, 503, 504].includes(error.status)) return true;
    return false;
  }
  // Network errors (Failed to fetch, server offline, DNS failure, etc.)
  return true;
}

export function retryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 8000);
}

export const RETRY_CONFIG = {
  retry: shouldRetry,
  retryDelay,
};

const LIVE = { refetchInterval: 60_000, ...RETRY_CONFIG };

export const useHealth = () => useQuery({ queryKey: ["health"], queryFn: () => api<Health>("/health"), ...LIVE });
export const useSite = () => useQuery({ queryKey: ["site"], queryFn: () => api<SiteInfo>("/site"), ...RETRY_CONFIG });
export const useForecast = (source: Source, horizon = 48) =>
  useQuery({ queryKey: ["forecast", source, horizon], queryFn: () => api<ForecastResponse>(`/forecast?source=${source}&horizon=${horizon}`), ...LIVE });
export const useHistory = (source: "solar" | "wind", model = "ensemble") =>
  useQuery({ queryKey: ["history", source, model], queryFn: () => api<HistoryResponse>(`/forecast/history?source=${source}&model=${model}`), ...RETRY_CONFIG });
export const useModels = (source: "solar" | "wind", by?: "lead_bucket") =>
  useQuery({ queryKey: ["models", source, by], queryFn: () => api<ModelsResponse>(`/models/compare?source=${source}${by ? `&by=${by}` : ""}`), ...RETRY_CONFIG });
export const useAlerts = () => useQuery({ queryKey: ["alerts"], queryFn: () => api<AlertOut[]>("/alerts"), ...LIVE });
export const useDispatch = (strategy: "advisor" | "rule" | "none" = "advisor") =>
  useQuery({ queryKey: ["dispatch", strategy], queryFn: () => api<DispatchResponse>(`/dispatch?strategy=${strategy}`), ...LIVE });
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
