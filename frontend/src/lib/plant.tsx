"use client";
/** The plant the whole dashboard is about: which site is selected and the operator's plant profile.
 *
 *  - Both live in this browser (localStorage), never on the server, so one visitor can't change another's plant.
 *  - The default view is the recorded Dewas replay run. Picking another site, running Dewas live, or customising the
 *    plant switches every tab to a live forecast built by the API for that site and profile.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { api } from "@/lib/api/client";
import { RETRY_CONFIG } from "@/lib/api/retry";
import type { LocationInfo, LocationJob, LocationResult } from "@/lib/api/types";

export type Values = Record<string, string | number>;
export interface PlantStore { siteId: string | null; liveHome: boolean; values: Values; onboarded: boolean; dismissed: boolean }
export interface FieldDef {
  key: string; step: string; label: string; kind: "text" | "number" | "select"; effect: "forecast" | "plan" | "recorded" | "display";
  help: string; unit: string; min: number | null; max: number | null; step_size: number | null; verify: boolean; required: boolean;
}
export interface ProfileSchema { steps: { id: string; title: string; blurb: string }[]; fields: FieldDef[]; defaults: Values }

const KEY = "vidyut_plant_v1";
const EMPTY: PlantStore = { siteId: null, liveHome: false, values: {}, onboarded: false, dismissed: false };
const listeners = new Set<() => void>();
let cache: PlantStore | null = null;

function read(): PlantStore {
  if (cache) return cache;
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) cache = { ...EMPTY, ...(JSON.parse(raw) as Partial<PlantStore>) };
  } catch {
    /* storage can be unavailable (private mode) */
  }
  return (cache ??= EMPTY);
}
function write(next: PlantStore) {
  cache = next;
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };

const NAME_ONLY = new Set(["plant_name", "operator", "location_id"]);
export const isEntered = (v: unknown) => v !== undefined && v !== null && v !== "";

export interface RunState {
  status: "idle" | "loading" | "done" | "failed";
  step: LocationJob["step"] | "starting";
  error: string | null;
  result: LocationResult | null;
  startedAt: number;
}

export interface ActivePlant {
  ready: boolean;
  sites: LocationInfo[];
  home: string | null;
  site: LocationInfo | null;
  store: PlantStore;
  schema: ProfileSchema | undefined;
  customised: boolean;
  live: boolean;
  /** Plain name for the top bar and page notes, e.g. "Pavagada, Karnataka" or the plant's own name. */
  label: string;
  run: RunState;
  setSite: (id: string) => void;
  setLiveHome: (v: boolean) => void;
  saveProfile: (values: Values, onboarded?: boolean) => void;
  resetProfile: () => void;
  dismissSetup: () => void;
  refresh: () => void;
}

const Ctx = createContext<ActivePlant | null>(null);
export const useActivePlant = (): ActivePlant => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useActivePlant must be used inside <ActivePlantProvider>");
  return c;
};

export function ActivePlantProvider({ children }: { children: React.ReactNode }) {
  const store = useSyncExternalStore(subscribe, read, () => EMPTY);
  const sitesQ = useQuery({ queryKey: ["locations"], queryFn: () => api<LocationInfo[]>("/locations"), staleTime: Infinity, ...RETRY_CONFIG });
  const schemaQ = useQuery({ queryKey: ["profile-schema"], queryFn: () => api<ProfileSchema>("/profile/schema"), staleTime: Infinity, ...RETRY_CONFIG });
  const sites = useMemo(() => sitesQ.data ?? [], [sitesQ.data]);
  const home = sites.find((s) => s.is_home)?.id ?? null;
  const siteId = store.siteId && sites.some((s) => s.id === store.siteId) ? store.siteId : home;
  const site = sites.find((s) => s.id === siteId) ?? null;
  const schema = schemaQ.data;

  const sendValues = useMemo(() => {
    const out: Values = {};
    for (const [k, v] of Object.entries(store.values)) if (k !== "location_id" && isEntered(v)) out[k] = v;
    return out;
  }, [store.values]);
  const customised = useMemo(
    () => Object.entries(sendValues).some(([k, v]) => !NAME_ONLY.has(k) && (!schema || Number(v) !== Number(schema.defaults[k]))),
    [sendValues, schema],
  );
  const live = !!home && !!site && (siteId !== home || store.liveHome || customised);
  const runKey = live ? `${siteId}|${JSON.stringify(sendValues)}` : null;

  const startedKey = useRef<string | null>(null);
  const start = useMutation({
    mutationFn: (v: { id: string; values: Values; force: boolean }) =>
      api<LocationJob>(`/locations/${v.id}/forecast${v.force ? "?force=true" : ""}`, { method: "POST", body: JSON.stringify({ values: v.values }) }),
  });
  const mutate = start.mutate;
  const jobId = start.data?.job_id ?? null;
  const jobQ = useQuery({
    queryKey: ["plant-job", jobId],
    enabled: !!jobId && live,
    queryFn: () => api<LocationJob>(`/locations/jobs/${jobId}`),
    refetchInterval: (q) => (q.state.data && ["done", "failed"].includes(q.state.data.status) ? false : 1000),
    retry: false,
  });
  const done = jobQ.data?.status === "done";
  const resultQ = useQuery({
    queryKey: ["plant-result", jobId],
    enabled: !!jobId && done,
    queryFn: () => api<LocationResult>(`/locations/jobs/${jobId}/result`),
    staleTime: Infinity,
    retry: false,
  });

  useEffect(() => {
    if (!runKey || !siteId || startedKey.current === runKey) return;
    startedKey.current = runKey;
    mutate({ id: siteId, values: sendValues, force: false });
  }, [runKey, siteId, sendValues, mutate]);

  const refresh = useCallback(() => {
    if (!siteId) return;
    mutate({ id: siteId, values: sendValues, force: true });
  }, [siteId, sendValues, mutate]);

  const run: RunState = useMemo(() => {
    const base = { startedAt: start.submittedAt };
    if (!live) return { ...base, status: "idle", step: "starting", error: null, result: null };
    if (start.isError) return { ...base, status: "failed", step: "starting", error: start.error.message, result: null };
    if (jobQ.data?.status === "failed") return { ...base, status: "failed", step: "done", error: jobQ.data.error ?? "The forecast job failed.", result: null };
    if (resultQ.data && jobQ.data) return { ...base, status: "done", step: "done", error: null, result: resultQ.data };
    return { ...base, status: "loading", step: jobQ.data?.step ?? "starting", error: null, result: null };
  }, [live, start.isError, start.error, start.submittedAt, jobQ.data, resultQ.data]);

  const label = store.values.plant_name ? String(store.values.plant_name) : site ? `${site.name}, ${site.region}` : "Dewas, Madhya Pradesh";

  const value: ActivePlant = {
    ready: !!home, sites, home, site, store, schema, customised, live, label, run,
    setSite: (id) => write({ ...read(), siteId: id, liveHome: false }),
    setLiveHome: (v) => write({ ...read(), liveHome: v }),
    saveProfile: (values, onboarded = true) => write({ ...read(), values, onboarded, dismissed: true }),
    resetProfile: () => write({ ...read(), values: {}, onboarded: false, dismissed: false }),
    dismissSetup: () => write({ ...read(), dismissed: true }),
    refresh,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** The shape components expect from a query, filled from the live run so pages need no special cases. */
export function liveQuery<T>(ap: ActivePlant, pick: (r: LocationResult) => T) {
  const r = ap.run.result;
  return {
    data: r ? pick(r) : undefined,
    isLoading: ap.run.status === "loading",
    isError: ap.run.status === "failed",
    isFetching: ap.run.status === "loading",
    error: ap.run.status === "failed" ? new Error(ap.run.error ?? "The live forecast failed") : null,
    refetch: () => ap.refresh(),
  };
}
