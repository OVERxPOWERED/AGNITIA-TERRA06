"use client";
/** The plant the whole dashboard is about: the selected site, the operator's plant profile, the calibration from
 *  uploaded measured history and optional weather-provider keys.
 *
 *  - Everything lives in this browser (localStorage). When the user is signed in, the same data is also saved to
 *    their account and loaded on any browser they sign in from. Provider keys stay in the browser only.
 *  - The default view is the recorded Dewas replay run. Picking another site, running Dewas live, customising the
 *    plant or calibrating it switches every tab to a live forecast built by the API for that site and plant.
 */
import { useMutation, useQuery } from "@tanstack/react-query";
import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { api } from "@/lib/api/client";
import { RETRY_CONFIG } from "@/lib/api/retry";
import type { LocationInfo, LocationJob, LocationResult, PlantStored } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";

export interface MaintenanceWindow { source: "solar" | "wind"; start: string; end: string; units: number | string; note?: string }
export type Value = string | number | MaintenanceWindow[];
export type Values = Record<string, Value>;
export interface CalibrationState {
  factors: { solar?: number; wind?: number };
  report: CalibrationReport;
  at: string;
}
export interface MetricBlock { mae_mw: number | null; nmae_pct: number | null; bias_pct: number | null; hours: number }
export interface SourceFit {
  factor?: number; trial_factor?: number; adopted?: boolean; error?: string; fit_hours?: number; test_hours?: number;
  excluded_outage_hours?: number; test_period?: [string, string]; before?: MetricBlock; after?: MetricBlock;
  corr_openmeteo_ghi?: number; corr_nasa_ghi?: number | null; nasa_hours?: number;
  daily_mwh?: { date: string; measured: number; physics: number; calibrated: number }[];
}
export interface CalibrationReport {
  notes: Record<string, unknown>;
  quality: Record<string, unknown> & { span_days?: number; first_utc?: string; last_utc?: string };
  timestamp_shift_h: number | null;
  warnings: string[];
  sources: Record<string, SourceFit>;
  factors: { solar?: number; wind?: number };
  weather: Record<string, string>;
  location_id?: string;
  saved_to_account?: boolean;
}
export interface PlantStore {
  siteId: string | null; liveHome: boolean; values: Values; onboarded: boolean; dismissed: boolean;
  calibration: CalibrationState | null; keys: { solcast?: string; tomorrow?: string };
}
export interface FieldDef {
  key: string; step: string; label: string; kind: "text" | "number" | "select" | "site" | "windows";
  effect: "forecast" | "plan" | "recorded" | "display"; help: string; unit: string; min: number | null; max: number | null;
  step_size: number | null; verify: boolean; options: { value: string; label: string }[]; applies: "" | "solar" | "wind";
}
export interface ProfileSchema { steps: { id: string; title: string; blurb: string }[]; fields: FieldDef[]; defaults: Values }

const KEY = "vidyut_plant_v1";
const EMPTY: PlantStore = { siteId: null, liveHome: false, values: {}, onboarded: false, dismissed: false, calibration: null, keys: {} };
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
export const isEntered = (v: unknown) => v !== undefined && v !== null && v !== "" && !(Array.isArray(v) && v.length === 0);
const same = (a: unknown, b: unknown) => String(a) === String(b) || (a !== "" && b !== "" && Number(a) === Number(b));

/** Which sources the plant has, from the profile (default: both). */
export const plantSources = (values: Values, defaults?: Values): Set<string> => {
  const s = String(values.sources ?? defaults?.sources ?? "hybrid");
  return new Set(s === "hybrid" ? ["solar", "wind"] : [s]);
};

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
  /** "local" when signed out; otherwise the state of the last save to the account. */
  sync: "local" | "saving" | "saved" | "error";
  setSite: (id: string) => void;
  setLiveHome: (v: boolean) => void;
  saveProfile: (values: Values, onboarded?: boolean) => void;
  resetProfile: () => void;
  dismissSetup: () => void;
  setCalibration: (c: CalibrationState | null) => void;
  setKeys: (k: PlantStore["keys"]) => void;
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
  const auth = useAuth();
  const userId = auth.user?.id ?? null;
  const sitesQ = useQuery({ queryKey: ["locations"], queryFn: () => api<LocationInfo[]>("/locations"), staleTime: Infinity, ...RETRY_CONFIG });
  const schemaQ = useQuery({ queryKey: ["profile-schema"], queryFn: () => api<ProfileSchema>("/profile/schema"), staleTime: Infinity, ...RETRY_CONFIG });
  const sites = useMemo(() => sitesQ.data ?? [], [sitesQ.data]);
  const home = sites.find((s) => s.is_home)?.id ?? null;
  const siteId = store.siteId && sites.some((s) => s.id === store.siteId) ? store.siteId : home;
  const site = sites.find((s) => s.id === siteId) ?? null;
  const schema = schemaQ.data;

  /* ---- account sync: pull on sign-in, push on every change while signed in ---- */
  const save = useMutation({
    mutationFn: (s: PlantStore) => api<PlantStored>("/me/plant", {
      method: "PUT",
      body: JSON.stringify({ values: s.values, site_id: s.siteId ?? undefined, live_home: s.liveHome, calibration: s.calibration ?? {} }),
    }),
  });
  const pushSave = save.mutate;
  const pulledFor = useRef<string | null>(null);
  useEffect(() => {
    if (!userId || pulledFor.current === userId) return;
    pulledFor.current = userId;
    api<PlantStored>("/me/plant").then((p) => {
      if (p.version && p.version > 0) {
        const cal = p.calibration && Object.keys(p.calibration).length ? (p.calibration as unknown as CalibrationState) : null;
        write({ ...read(), values: (p.values ?? {}) as Values, siteId: p.site_id ?? null, liveHome: !!p.live_home,
                calibration: cal && "factors" in cal ? cal : null, onboarded: true, dismissed: true });
      } else {
        pushSave(read());                                  // first sign-in: keep what this browser already has
      }
    }).catch(() => { pulledFor.current = null; });
  }, [userId, pushSave]);
  const persist = useCallback((next: PlantStore) => {
    write(next);
    if (userId) pushSave(next);
  }, [userId, pushSave]);

  /* ---- live run for the selected site and plant ---- */
  const sendValues = useMemo(() => {
    const out: Values = {};
    for (const [k, v] of Object.entries(store.values)) if (k !== "location_id" && isEntered(v)) out[k] = v;
    return out;
  }, [store.values]);
  const calFactors = useMemo(() => store.calibration?.factors ?? {}, [store.calibration]);
  const customised = useMemo(
    () => Object.entries(sendValues).some(([k, v]) => !NAME_ONLY.has(k) && (Array.isArray(v) ? v.length > 0 : !schema || !same(v, schema.defaults[k])))
      || Object.values(calFactors).some((f) => f !== undefined && f !== 1),
    [sendValues, schema, calFactors],
  );
  const live = !!home && !!site && (siteId !== home || store.liveHome || customised);
  const keyNames = Object.entries(store.keys).filter(([, v]) => !!v).map(([k]) => k).sort().join(",");
  const runKey = live ? `${siteId}|${JSON.stringify(sendValues)}|${JSON.stringify(calFactors)}|${keyNames}` : null;

  const startedKey = useRef<string | null>(null);
  const start = useMutation({
    mutationFn: (v: { id: string; force: boolean }) =>
      api<LocationJob>(`/locations/${v.id}/forecast${v.force ? "?force=true" : ""}`, {
        method: "POST",
        body: JSON.stringify({ values: sendValues, calibration: calFactors, keys: store.keys }),
      }),
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
    mutate({ id: siteId, force: false });
  }, [runKey, siteId, mutate]);

  const refresh = useCallback(() => {
    if (siteId) mutate({ id: siteId, force: true });
  }, [siteId, mutate]);

  const run: RunState = useMemo(() => {
    const base = { startedAt: start.submittedAt };
    if (!live) return { ...base, status: "idle", step: "starting", error: null, result: null };
    if (start.isError) return { ...base, status: "failed", step: "starting", error: start.error.message, result: null };
    if (jobQ.data?.status === "failed") return { ...base, status: "failed", step: "done", error: jobQ.data.error ?? "The forecast job failed.", result: null };
    if (resultQ.data && jobQ.data) return { ...base, status: "done", step: "done", error: null, result: resultQ.data };
    return { ...base, status: "loading", step: jobQ.data?.step ?? "starting", error: null, result: null };
  }, [live, start.isError, start.error, start.submittedAt, jobQ.data, resultQ.data]);

  const label = store.values.plant_name ? String(store.values.plant_name) : site ? `${site.name}, ${site.region}` : "Dewas, Madhya Pradesh";
  const sync: ActivePlant["sync"] = !userId ? "local" : save.isPending ? "saving" : save.isError ? "error" : "saved";

  const value: ActivePlant = {
    ready: !!home, sites, home, site, store, schema, customised, live, label, run, sync,
    setSite: (id) => persist({ ...read(), siteId: id, liveHome: false }),
    setLiveHome: (v) => persist({ ...read(), liveHome: v }),
    saveProfile: (values, onboarded = true) => persist({ ...read(), values, onboarded, dismissed: true }),
    resetProfile: () => persist({ ...read(), values: {}, onboarded: false, dismissed: false, calibration: null }),
    dismissSetup: () => write({ ...read(), dismissed: true }),
    setCalibration: (c) => persist({ ...read(), calibration: c }),
    setKeys: (k) => write({ ...read(), keys: k }),               // provider keys never leave this browser except per run
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
