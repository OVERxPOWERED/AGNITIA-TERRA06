"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, MapPin, OctagonAlert, UserRound } from "lucide-react";
import { isAcked, useLocalAcks } from "@/lib/acks";
import { ALERT_LABEL, timeToStart } from "@/lib/alerts";
import { useAuth } from "@/lib/auth";
import { useAlerts, useForecast, useHealth, useLiveUpdates, useSite } from "@/hooks/api";
import { getApiBaseConfigError } from "@/lib/api/client";
import type { AlertOut } from "@/lib/api/types";
import { toIST } from "@/lib/format";
import { useActivePlant } from "@/lib/plant";
import { cn } from "@/lib/cn";
import { Dot, Pill, Spinner } from "@/components/ui/primitives";
import { fmtDayHM, istMs } from "@/components/charts/series";
import { Logo } from "./Logo";
import { NAV } from "./nav";
import SettingsMenu from "./SettingsMenu";

const pad = (n: number) => String(n).padStart(2, "0");

/** Live IST clock. Starts empty so server and first client render match. */
function Clock() {
  const [t, setT] = useState<string | null>(null);
  useEffect(() => {
    const tick = () => {
      const d = new Date(Date.now() + 330 * 60_000);
      setT(`${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="num text-[13px] text-ink" aria-label="Current time in India">{t ?? "--:--:--"} <span className="text-muted">IST</span></span>;
}

/** The status of the API connection, shown as the mode pill. */
function ModePill() {
  const health = useHealth();
  const ap = useActivePlant();
  if (ap.live && !health.isError) {
    return <Pill tone="good" title="A live forecast on current weather, built for the site shown below."><Dot color="var(--good)" />Live</Pill>;
  }
  const lastOk = health.dataUpdatedAt ? toIST(new Date(health.dataUpdatedAt).toISOString()) : null;
  // A failed refresh while we still hold an earlier answer is a hiccup (Render cold start, redeploy), not an outage.
  if (health.isError && health.data) {
    return <Pill tone="warn" title={`The last check failed; retrying every minute. Last contact: ${lastOk}. Data on screen is from then.`}><Spinner className="h-3 w-3" />Reconnecting</Pill>;
  }
  if (health.isError) {
    return <Pill tone="bad" title="The forecast server did not answer after repeated tries. It may be restarting; this page keeps retrying."><Dot color="var(--bad)" />Offline</Pill>;
  }
  if (!health.data) return <Pill tone="warn" title="The free server sleeps when idle and takes about a minute to wake."><Spinner className="h-3 w-3" />Waking up</Pill>;
  const live = health.data.mode === "live";
  return (
    <Pill tone={live ? "good" : "accent"} title={live ? "Live: new runs arrive on a schedule" : "Replay: a recorded run from the held-out test period"}>
      <Dot color={live ? "var(--good)" : "var(--accent)"} />
      {live ? "Live" : "Replay"}
    </Pill>
  );
}

/** Forecast outline: one bar per hour of the next 48 h hybrid P50. A glanceable shape of the day under the top bar. */
function Outline() {
  const hybrid = useForecast("hybrid", 48);
  const pts = hybrid.data?.points ?? [];
  const max = Math.max(1, ...pts.map((p) => p.q50));
  return (
    <div className="mx-auto flex h-7 max-w-[1360px] items-end gap-[3px] px-4 sm:px-6" role="img" aria-label="Outline of expected hybrid generation over the next 48 hours">
      {(pts.length ? pts : Array.from({ length: 48 }, () => null)).map((p, i) => (
        <span
          key={p?.target_time_utc ?? i}
          title={p ? `${fmtDayHM(istMs(p.target_time_utc))}: ${p.q50.toFixed(1)} MW` : undefined}
          className="flex-1 rounded-[2px] bg-accent/25"
          style={{ height: p ? `${Math.max(8, (p.q50 / max) * 100)}%` : "12%" }}
        />
      ))}
    </div>
  );
}

const SETTINGS_PAGES: Record<string, string> = { "/location": "location", "/settings": "plant-settings", "/setup": "plant-setup", "/login": "sign-in" };

/** Account entry: "Sign in" when signed out, the user's initial when signed in (links to settings). */
function AccountButton() {
  const auth = useAuth();
  if (auth.user) {
    const initial = (auth.user.name || auth.user.email).trim().charAt(0).toUpperCase();
    return (
      <Link href="/settings" title={`Signed in as ${auth.user.email}`} aria-label={`Account: ${auth.user.email}`}
        className="t-colors inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-[14px] font-semibold text-on-accent hover:opacity-90">{initial}</Link>
    );
  }
  return (
    <Link href="/login" className="t-colors inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 text-[13px] font-medium text-ink hover:bg-sunken">
      <UserRound className="h-4 w-4" aria-hidden /><span className="hidden sm:inline">Sign in</span>
    </Link>
  );
}
/** Pages whose figures come from an evaluation: the operator's measured history when uploaded, otherwise Dewas. */
const EVAL_PAGES = ["/models", "/trust", "/impact", "/deviation"];

/** Always-visible answer to "which plant am I looking at?" for every tab. */
function ContextBar() {
  const ap = useActivePlant();
  if (!ap.ready || !ap.site) return null;
  const busy = ap.run.status === "loading";
  const failed = ap.run.status === "failed";
  return (
    <div className="border-t border-line bg-sunken/60">
      <div className="mx-auto flex min-h-9 max-w-[1360px] flex-wrap items-center gap-x-3 gap-y-1 px-4 py-1.5 text-[13px] sm:px-6">
        <MapPin className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden />
        <span className="font-medium text-ink">{ap.label}</span>
        {ap.label !== `${ap.site.name}, ${ap.site.region}` && <span className="text-muted">{ap.site.name}, {ap.site.region}</span>}
        {busy ? (
          <Pill tone="warn"><Spinner className="h-3 w-3" />Building live forecast</Pill>
        ) : failed ? (
          <Pill tone="bad">Live forecast failed</Pill>
        ) : ap.live ? (
          <Pill tone="good"><Dot color="var(--good)" />Live forecast</Pill>
        ) : (
          <Pill tone="accent">Recorded replay</Pill>
        )}
        {ap.live && !busy && !ap.site.is_home && <span className="text-[12px] text-warn">Not validated at this site</span>}
        {ap.live && !busy && ap.site.is_home && ap.customised && <span className="text-[12px] text-warn">Your layout, transferred through the physics model</span>}
        {ap.store.calibration && Object.keys(ap.store.calibration.factors).length > 0 && <Pill tone="accent" title="Calibrated to your measured history">Calibrated</Pill>}
        <span className="ml-auto flex items-center gap-3 text-[12px]">
          <Link href="/location" className="text-accent underline underline-offset-2">Change location</Link>
          <Link href="/settings" className="text-accent underline underline-offset-2">Plant settings</Link>
        </span>
      </div>
    </div>
  );
}

function Notices({ path }: { path: string }) {
  const ap = useActivePlant();
  const showSetup = ap.ready && !ap.store.onboarded && !ap.store.dismissed && !path.startsWith("/setup");
  const evalPage = EVAL_PAGES.some((p) => path.startsWith(p));
  return (
    <>
      {showSetup && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-[10px] border border-line bg-surface p-4 text-[13px]">
          <div className="min-w-0 flex-1">
            <div className="font-medium text-ink">Set up your plant</div>
            <div className="mt-0.5 text-muted">A few questions about your site, solar, wind, battery and demand make every page about your plant. All optional, about two minutes.</div>
          </div>
          <Link href="/setup" className="t-colors inline-flex min-h-9 items-center rounded-lg bg-accent px-3 text-[13px] font-medium text-on-accent hover:opacity-90">Start setup</Link>
          <button onClick={ap.dismissSetup} className="t-colors rounded-md px-2 py-1.5 text-[13px] text-muted hover:bg-sunken hover:text-ink">Not now</button>
        </div>
      )}
      {evalPage && ap.evaluation && (
        <div role="note" className={cn("mb-5 flex items-start gap-3 rounded-[10px] border p-4 text-[13px]", ap.evalStale ? "border-warn/40 bg-warn-soft" : "border-good/30 bg-good-soft")}>
          <Check className={cn("mt-0.5 h-4 w-4 shrink-0", ap.evalStale ? "text-warn" : "text-good")} aria-hidden />
          <div>
            <div className="font-medium text-ink">Figures for {ap.label}, from your measured history</div>
            <div className="mt-0.5 text-muted">
              {ap.evaluation.test_issues} held-out days ({toIST(ap.evaluation.test_from).split(",")[0]} onwards) out of {ap.evaluation.issues} evaluated, forecasts re-issued each morning from archived weather forecasts exactly as the live system would.
              {ap.evalStale && " Your plant settings changed after this upload, so these numbers describe the earlier settings. Upload the history again to refresh them."}
            </div>
          </div>
        </div>
      )}
      {evalPage && ap.live && !ap.evaluation && (
        <div role="note" className="mb-5 flex flex-wrap items-start gap-3 rounded-[10px] border border-warn/40 bg-warn-soft p-4 text-[13px]">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-ink">These are reference figures from the Dewas plant, not {ap.label}</div>
            <div className="mt-0.5 text-muted">Upload your plant&apos;s measured history and this page shows your own accuracy, trust check, savings and deviation charges, measured on your data.</div>
          </div>
          <Link href="/settings#history" className="t-colors inline-flex min-h-9 items-center rounded-lg bg-accent px-3 text-[13px] font-medium text-on-accent hover:opacity-90">Upload measured history</Link>
        </div>
      )}
    </>
  );
}

/** Red bar on every page while an unacknowledged critical alert is open. */
function CriticalBar({ path }: { path: string }) {
  const alerts = useAlerts();
  const local = useLocalAcks();
  const [now, setNow] = useState(0);
  useEffect(() => { const t = () => setNow(Date.now()); t(); const id = setInterval(t, 30_000); return () => clearInterval(id); }, []);
  const open = (alerts.data ?? []).filter((a) => a.severity === "critical" && !isAcked(a, local) && (!now || Date.parse(a.end_utc) > now))
    .sort((x, y) => x.start_utc.localeCompare(y.start_utc));
  useEffect(() => {
    const base = document.title.replace(/^\(\d+\) ⚠ /, "");
    document.title = open.length ? `(${open.length}) ⚠ ${base}` : base;
  }, [open.length]);
  if (!open.length || path.startsWith("/alerts")) return null;
  const first = open[0];
  return (
    <div role="alert" className="border-b-2 border-bad bg-bad text-white">
      <div className="mx-auto flex max-w-[1360px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2.5 text-[14px] sm:px-6">
        <span className="relative flex h-6 w-6 items-center justify-center">
          <span aria-hidden className="absolute inset-0 rounded-full bg-white/40 motion-safe:animate-ping" />
          <OctagonAlert className="relative h-5 w-5" aria-hidden />
        </span>
        <span className="font-semibold">{open.length} critical alert{open.length === 1 ? "" : "s"}:</span>
        <span className="min-w-0 flex-1 truncate">{ALERT_LABEL[first.type] ?? first.type}, {now ? timeToStart(first, now).toLowerCase() : "open"}. {first.message}</span>
        <Link href="/alerts" className="rounded-md bg-white px-3 py-1 text-[13px] font-semibold text-bad hover:opacity-90">Act now</Link>
      </div>
    </div>
  );
}

function Toast({ alert, onClose }: { alert: AlertOut | null; onClose: () => void }) {
  useEffect(() => {
    if (!alert) return;
    const id = setTimeout(onClose, 8000);
    return () => clearTimeout(id);
  }, [alert, onClose]);
  return (
    <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 max-w-sm">
      {alert && (
        <div className="pointer-events-auto rounded-[10px] border border-line bg-surface px-4 py-3 text-[13px] shadow-[0_8px_28px_rgb(0_0_0/0.14)]">
          <div className="font-medium text-ink">New alert</div>
          <div className="mt-0.5 text-muted">{alert.message}</div>
          <div className="num mt-1 text-[12px] text-faint">{toIST(alert.start_utc)}</div>
        </div>
      )}
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const site = useSite();
  const alerts = useAlerts();
  const [toast, setToast] = useState<AlertOut | null>(null);
  const onAlert = useCallback((a: AlertOut) => setToast(a), []);
  useLiveUpdates(onAlert);

  const local = useLocalAcks();
  const unacked = useMemo(() => (alerts.data ?? []).filter((a) => !isAcked(a, local)).length, [alerts.data, local]);
  const extra = Object.keys(SETTINGS_PAGES).find((p) => path.startsWith(p));
  const current = extra ? { href: extra, label: SETTINGS_PAGES[extra], slug: SETTINGS_PAGES[extra] } : (NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href))) ?? NAV[0]);
  const configError = getApiBaseConfigError();
  const s = site.data;

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:text-ink">Skip to content</a>

      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-14 max-w-[1360px] items-center gap-3 px-4 sm:px-6">
          <Link href="/" aria-label="Vidyut, go to Control Room" className="shrink-0 rounded-md"><Logo /></Link>
          <span className="num ml-1 hidden items-center rounded-md border border-line bg-paper px-2 py-1 text-[12px] text-muted lg:inline-flex">
            vidyut.energy <span className="mx-1.5 text-faint">/</span> <span className="text-ink">{current.slug}</span>
          </span>

          <div className="ml-auto hidden items-center gap-2 md:flex" aria-label="Plant capacity">
            <Pill><Dot color="var(--solar)" />Solar <span className="num text-ink">{s ? `${s.solar_ac_mw} MW` : "—"}</span></Pill>
            <Pill><Dot color="var(--wind)" />Wind <span className="num text-ink">{s ? `${s.wind_mw} MW` : "—"}</span></Pill>
            <Pill><Dot color="var(--battery)" />Battery <span className="num text-ink">{s ? `${s.battery_mwh} MWh` : "—"}</span></Pill>
          </div>

          <div className="ml-auto flex items-center gap-3 md:ml-4">
            <Clock />
            <ModePill />
            <AccountButton />
            <SettingsMenu />
          </div>
        </div>
        <Outline />
        <nav aria-label="Pages" className="border-t border-line">
          <div className="no-scrollbar mx-auto flex max-w-[1360px] gap-1 overflow-x-auto px-3 py-2 sm:px-5">
            {NAV.map((n) => {
              const on = n.href === current.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={on ? "page" : undefined}
                  className={cn("t-colors relative inline-flex min-h-9 shrink-0 items-center gap-2 rounded-lg px-3 text-[13px] font-medium", on ? "bg-sunken text-ink shadow-[0_0_0_1px_var(--line)]" : "text-muted hover:text-ink")}
                >
                  {n.label}
                  {n.slug === "alerts" && unacked > 0 && (
                    <span className="num inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-bad px-1 text-[11px] font-semibold text-white" aria-label={`${unacked} unacknowledged alerts`}>{unacked}</span>
                  )}
                </Link>
              );
            })}
          </div>
        </nav>
        <ContextBar />
      </header>
      <CriticalBar path={path} />

      <main id="main" className="mx-auto w-full max-w-[1360px] flex-1 px-4 py-6 sm:px-6">
        {configError && (
          <div role="alert" className="mb-5 flex items-start gap-3 rounded-[10px] border border-warn/40 bg-warn-soft p-4 text-[13px]">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
            <div>
              <div className="font-medium text-ink">The API address isn&apos;t configured for this build</div>
              <div className="mt-0.5 text-muted">{configError}</div>
            </div>
          </div>
        )}
        <Notices path={path} />
        {children}
      </main>

      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-[1360px] flex-wrap items-center justify-between gap-x-6 gap-y-1 px-4 py-3 text-[12px] text-muted sm:px-6">
          <span>
            Weather data by <a className="underline underline-offset-2 hover:text-ink" href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a> (CC BY 4.0)
          </span>
          <span>Plant: Vidyut virtual digital twin at a real location, calibrated on real data. Times are in IST.</span>
        </div>
      </footer>
      <Toast alert={toast} onClose={() => setToast(null)} />
    </div>
  );
}
