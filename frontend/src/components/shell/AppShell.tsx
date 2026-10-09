"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useState } from "react";
import { useHealth, useLiveUpdates } from "@/hooks/api";
import { getApiBaseConfigError, RAW_API_BASE } from "@/lib/api/client";
import type { AlertOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { toIST } from "@/lib/format";
import { Badge, Spinner } from "../ui/primitives";
import { NAV } from "./nav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const health = useHealth();
  const [toast, setToast] = useState<AlertOut | null>(null);
  const onAlert = useCallback((a: AlertOut) => { if (a.severity !== "info") setToast(a); }, []);
  useLiveUpdates(onAlert);
  const mode = health.data?.mode?.toUpperCase();

  // Fail loudly if NEXT_PUBLIC_API_BASE is missing or misconfigured in production builds
  const configError = getApiBaseConfigError();
  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-text">
        <div className="w-full max-w-lg space-y-4 rounded-2xl border border-bad/50 bg-panel p-6 shadow-xl">
          <div className="flex items-center gap-3 text-lg font-semibold text-bad">
            <span className="text-2xl">⚠️</span>
            Configuration Error: NEXT_PUBLIC_API_BASE
          </div>
          <p className="text-sm text-text/80">{configError}</p>
          <div className="space-y-2 rounded-lg bg-border/40 p-3 text-xs text-muted">
            <p className="font-semibold text-text">How to resolve on Vercel:</p>
            <ol className="list-decimal space-y-1 pl-4">
              <li>Open your project on Vercel → <strong>Settings</strong> → <strong>Environment Variables</strong>.</li>
              <li>Add variable <code className="font-mono text-text">NEXT_PUBLIC_API_BASE</code> with your Render service URL (e.g. <code className="font-mono text-text">https://terra-api.onrender.com</code>).</li>
              <li>Trigger a redeploy (Next.js statically bakes this variable into client bundles during build).</li>
            </ol>
            {RAW_API_BASE && (
              <p className="mt-2 text-muted">
                Current build value: <code className="font-mono text-text">{RAW_API_BASE}</code>
              </p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Waking up indicator in header
  const isWakingUp = health.failureCount > 0 && !health.data;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-border bg-panel md:w-56 md:border-r md:border-b-0">
        <div className="px-4 py-4">
          <div className="text-lg font-bold tracking-tight">TERRA</div>
          <div className="text-xs text-muted">Dewas hybrid · Indore region</div>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-3 md:flex-col md:overflow-visible">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href}
              aria-current={path === n.href ? "page" : undefined}
              className={cn("whitespace-nowrap rounded-lg px-3 py-2 text-sm", path === n.href ? "bg-text text-bg" : "text-muted hover:bg-border/60 hover:text-text")}>
              {n.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-3 md:px-6">
          <div className="text-sm text-muted">
            {isWakingUp ? (
              <div className="flex items-center gap-2 font-medium text-amber-500" role="status" aria-live="polite">
                <Spinner className="h-4 w-4" />
                <span>The API is waking up (free hosting sleeps when idle). Retrying automatically… attempt {health.failureCount}</span>
              </div>
            ) : health.data?.latest_issue_time_utc ? (
              <>Forecast issued {toIST(health.data.latest_issue_time_utc)}</>
            ) : (
              "Waiting for first forecast…"
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {health.data?.mode === "live" && health.data.latest_issue_time_utc &&
              // eslint-disable-next-line react-hooks/purity
              Date.now() - new Date(health.data.latest_issue_time_utc).getTime() > 3 * 3600_000 && (
                <Badge tone="warn">Data stale since {toIST(health.data.latest_issue_time_utc)}</Badge>
            )}
            {mode && <Badge tone={mode === "LIVE" ? "good" : "hybrid"} aria-label={`mode ${mode}`}>● {mode}</Badge>}
          </div>
        </header>
        <main className="flex-1 px-4 py-5 md:px-6">{children}</main>
        <footer className="border-t border-border px-4 py-3 text-xs text-muted md:px-6">
          Weather data by <a className="underline" href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo.com</a> (CC BY 4.0) ·
          Plant: TERRA virtual digital twin at a real location, calibrated on real data · Times in IST
        </footer>
      </div>
      {toast && (
        <div role="status" className="fixed right-4 bottom-4 max-w-sm rounded-xl border border-border bg-panel p-4 shadow-lg">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Badge tone={toast.severity === "critical" ? "bad" : "warn"}>{toast.type.replaceAll("_", " ")}</Badge>
              <p className="mt-2 text-sm">{toast.message}</p>
              <p className="mt-1 text-xs text-muted">{toIST(toast.start_utc)} → {toIST(toast.end_utc)}</p>
            </div>
            <button aria-label="Dismiss" className="text-muted" onClick={() => setToast(null)}>✕</button>
          </div>
        </div>
      )}
    </div>
  );
}
