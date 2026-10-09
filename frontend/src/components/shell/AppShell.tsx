"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { useAlerts, useForecast, useHealth, useLiveUpdates, useSite } from "@/hooks/api";
import { getApiBaseConfigError } from "@/lib/api/client";
import type { AlertOut } from "@/lib/api/types";
import { toIST } from "@/lib/format";
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
  if (health.isError) return <Pill tone="bad"><Dot color="var(--bad)" />Offline</Pill>;
  if (!health.data) return <Pill tone="warn"><Spinner className="h-3 w-3" />Waking up</Pill>;
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

  const unacked = useMemo(() => (alerts.data ?? []).filter((a) => !a.acknowledged).length, [alerts.data]);
  const current = NAV.find((n) => (n.href === "/" ? path === "/" : path.startsWith(n.href))) ?? NAV[0];
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
      </header>

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
