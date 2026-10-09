"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import React, {
  useCallback,
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";
import {
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  WifiOff,
} from "lucide-react";
import { useHealth, useLiveUpdates } from "@/hooks/api";
import { getApiBaseConfigError, RAW_API_BASE } from "@/lib/api/client";
import type { AlertOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { toIST } from "@/lib/format";
import { Badge, Spinner } from "../ui/primitives";
import { Logo } from "./Logo";
import { NAV_GROUPS } from "./nav";
import { ThemeToggle } from "./ThemeToggle";

function subscribeSidebar(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("vidyut:sidebar-change", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("vidyut:sidebar-change", callback);
  };
}

function getSidebarSnapshot(): boolean {
  try {
    return localStorage.getItem("vidyut_sidebar_collapsed") === "true";
  } catch {
    return false;
  }
}

function getServerSidebarSnapshot(): boolean {
  return false;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const health = useHealth();
  const [toast, setToast] = useState<AlertOut | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);

  const storedCollapsed = useSyncExternalStore(
    subscribeSidebar,
    getSidebarSnapshot,
    getServerSidebarSnapshot
  );
  const [collapsed, setCollapsed] = useState(storedCollapsed);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setCollapsed(storedCollapsed);
  }, [storedCollapsed]);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("vidyut_sidebar_collapsed", String(next));
      } catch {
        // Ignore storage write issues
      }
      window.dispatchEvent(new CustomEvent("vidyut:sidebar-change"));
      return next;
    });
  }, []);

  // Handle escape key to close mobile drawer
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileOpen) {
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mobileOpen]);

  const onAlert = useCallback((a: AlertOut) => {
    if (a.severity !== "info") setToast(a);
  }, []);
  useLiveUpdates(onAlert);

  const mode = health.data?.mode?.toUpperCase();
  const isWakingUp = health.failureCount > 0 && !health.data;
  const isHealthy = Boolean(health.data);
  const isError = health.isError;

  // Fail loudly if NEXT_PUBLIC_API_BASE is missing or misconfigured in production builds
  const configError = getApiBaseConfigError();
  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg p-6 text-text">
        <div className="w-full max-w-lg space-y-4 rounded-2xl border border-bad/40 bg-panel p-6 shadow-xl">
          <div className="flex items-center gap-3 text-lg font-semibold text-bad">
            <AlertCircle className="h-6 w-6 shrink-0" />
            <span>Configuration Error: NEXT_PUBLIC_API_BASE</span>
          </div>
          <p className="text-sm text-text/90 leading-relaxed">{configError}</p>
          <div className="space-y-2 rounded-xl bg-panel-muted p-4 text-xs text-muted border border-border">
            <p className="font-semibold text-text">How to resolve on Vercel:</p>
            <ol className="list-decimal space-y-1.5 pl-4">
              <li>
                Open your project on Vercel → <strong>Settings</strong> → <strong>Environment Variables</strong>.
              </li>
              <li>
                Add variable <code className="font-mono text-text">NEXT_PUBLIC_API_BASE</code> with your backend URL (e.g. <code className="font-mono text-text">https://terra-api.onrender.com</code>).
              </li>
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

  return (
    <div className="flex min-h-screen flex-col md:flex-row bg-bg text-text">
      {/* Mobile Top Bar (< 768px) */}
      <div className="flex md:hidden items-center justify-between border-b border-border bg-panel px-4 py-3 sticky top-0 z-30">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation menu"
            className="flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted hover:text-text hover:bg-border/40 focus-visible:ring-2 focus-visible:ring-accent"
          >
            <Menu className="h-5 w-5" />
          </button>
          <Logo collapsed={false} />
        </div>
        <div className="flex items-center gap-2">
          {/* Mode badge is rendered in the header bar below on mobile to prevent showing it twice */}
        </div>
      </div>

      {/* Mobile Off-canvas Drawer Backdrop */}
      {mobileOpen && (
        <div
          role="presentation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-xs transition-opacity duration-150 md:hidden"
        />
      )}

      {/* Mobile Off-canvas Drawer Content */}
      <aside
        aria-label="Mobile navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col justify-between border-r border-border bg-panel p-4 shadow-2xl transition-transform duration-200 ease-out md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex flex-col gap-5 overflow-y-auto">
          <div className="flex items-center justify-between pb-2 border-b border-border">
            <Logo collapsed={false} />
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close navigation menu"
              className="flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted hover:text-text hover:bg-border/40"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav aria-label="Mobile Main" className="space-y-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.title} className="space-y-1">
                <div className="px-2 text-[11px] font-semibold tracking-wider text-muted uppercase">
                  {group.title}
                </div>
                {group.items.map((n) => {
                  const Icon = n.icon;
                  const isActive = path === n.href;
                  return (
                    <Link
                      key={n.href}
                      href={n.href}
                      onClick={() => setMobileOpen(false)}
                      aria-current={isActive ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium min-h-[40px] transition-colors",
                        isActive
                          ? "bg-accent/15 text-accent font-semibold"
                          : "text-muted hover:bg-border/50 hover:text-text"
                      )}
                    >
                      <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-accent" : "text-muted")} />
                      <span>{n.label}</span>
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        <div className="space-y-3 pt-3 border-t border-border">
          <div className="flex items-center justify-between text-xs text-muted px-1">
            <span className="font-medium">Theme</span>
            <div className="w-40">
              <ThemeToggle />
            </div>
          </div>
          <div className="flex items-center justify-between px-1 text-xs text-muted">
            <span className="flex items-center gap-1.5">
              {isWakingUp ? (
                <Spinner className="h-3.5 w-3.5 text-warn" />
              ) : isError ? (
                <WifiOff className="h-3.5 w-3.5 text-bad" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-good" />
              )}
              {isWakingUp ? "API waking up…" : isError ? "API offline" : "API connected"}
            </span>
            {mode && <Badge tone={mode === "LIVE" ? "good" : "hybrid"}>● {mode}</Badge>}
          </div>
        </div>
      </aside>

      {/* Desktop Sidebar (>= 768px) */}
      <aside
        aria-label="Sidebar navigation"
        className={cn(
          "hidden md:flex flex-col justify-between border-r border-border bg-panel shrink-0 transition-[width] duration-150 ease-out select-none",
          collapsed ? "w-[68px]" : "w-60"
        )}
      >
        <div className="flex flex-col min-h-0">
          {/* Header & Logo */}
          <div className="flex items-center justify-between border-b border-border px-3.5 py-4">
            <Logo collapsed={collapsed} />
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="flex h-7 w-7 items-center justify-center rounded-md border border-border text-muted hover:text-text hover:bg-border/60 focus-visible:ring-2 focus-visible:ring-accent"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            >
              {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            </button>
          </div>

          {/* Grouped Nav */}
          <nav aria-label="Main" className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.title} className="space-y-0.5">
                {!collapsed && (
                  <div className="px-2.5 py-1 text-[11px] font-semibold tracking-wider text-muted uppercase">
                    {group.title}
                  </div>
                )}
                {group.items.map((n) => {
                  const Icon = n.icon;
                  const isActive = path === n.href;
                  return (
                    <Link
                      key={n.href}
                      href={n.href}
                      title={collapsed ? n.label : undefined}
                      aria-label={collapsed ? n.label : undefined}
                      aria-current={isActive ? "page" : undefined}
                      className={cn(
                        "group relative flex items-center gap-2.5 rounded-lg py-2 text-sm font-medium transition-colors",
                        collapsed ? "justify-center px-2" : "px-2.5",
                        isActive
                          ? "bg-accent/15 text-accent font-semibold"
                          : "text-muted hover:bg-border/50 hover:text-text"
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-4 w-4 shrink-0 transition-colors",
                          isActive ? "text-accent" : "text-muted group-hover:text-text"
                        )}
                      />
                      {!collapsed && <span className="truncate">{n.label}</span>}

                      {/* Tooltip on collapsed hover */}
                      {collapsed && (
                        <div className="pointer-events-none absolute left-full ml-2 hidden whitespace-nowrap rounded-md border border-border bg-panel px-2.5 py-1 text-xs font-medium text-text shadow-md group-hover:block z-50">
                          {n.label}
                        </div>
                      )}
                    </Link>
                  );
                })}
              </div>
            ))}
          </nav>
        </div>

        {/* Sidebar Footer Area */}
        <div className="border-t border-border p-2.5 space-y-2.5">
          {/* Status and Mode */}
          <div
            className={cn(
              "flex items-center gap-2 text-xs text-muted",
              collapsed ? "justify-center" : "justify-between px-1"
            )}
          >
            <div
              className="flex items-center gap-1.5"
              title={
                isWakingUp
                  ? `API waking up (attempt ${health.failureCount})`
                  : isError
                  ? "API unreachable"
                  : isHealthy
                  ? "API online"
                  : "Checking status…"
              }
            >
              {isWakingUp ? (
                <Spinner className="h-3.5 w-3.5 text-warn shrink-0" />
              ) : isError ? (
                <WifiOff className="h-3.5 w-3.5 text-bad shrink-0" />
              ) : isHealthy ? (
                <span className="h-2 w-2 rounded-full bg-good shrink-0" />
              ) : (
                <span className="h-2 w-2 rounded-full bg-muted/50 animate-pulse shrink-0" />
              )}
              {!collapsed && (
                <span className="text-[11px] truncate">
                  {isWakingUp ? `Waking up (${health.failureCount})` : isError ? "Offline" : "Online"}
                </span>
              )}
            </div>
            {!collapsed && mode && (
              <Badge tone={mode === "LIVE" ? "good" : "hybrid"} className="text-[10px] py-0 px-1.5">
                ● {mode}
              </Badge>
            )}
          </div>

          {/* Theme Toggle */}
          <div className={cn("flex", collapsed ? "justify-center" : "w-full")}>
            <ThemeToggle collapsed={collapsed} />
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Header */}
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-panel/70 backdrop-blur-xs px-4 py-3 md:px-6">
          <div className="text-xs text-muted">
            {isWakingUp ? (
              <div className="flex items-center gap-2 font-medium text-warn" role="status" aria-live="polite">
                <Spinner className="h-3.5 w-3.5" />
                <span>The API is waking up (free hosting sleeps when idle). Retrying automatically… attempt {health.failureCount}</span>
              </div>
            ) : health.data?.latest_issue_time_utc ? (
              <span>Forecast issued <strong className="text-text font-semibold">{toIST(health.data.latest_issue_time_utc)}</strong></span>
            ) : (
              "Waiting for first forecast…"
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {health.data?.mode === "live" &&
              health.data.latest_issue_time_utc &&
              // eslint-disable-next-line react-hooks/purity
              Date.now() - new Date(health.data.latest_issue_time_utc).getTime() > 3 * 3600_000 && (
                <Badge tone="warn">Data stale since {toIST(health.data.latest_issue_time_utc)}</Badge>
              )}
            {mode && (
              <Badge tone={mode === "LIVE" ? "good" : "hybrid"} aria-label={`mode ${mode}`}>
                ● {mode}
              </Badge>
            )}
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 px-4 py-6 md:px-8 max-w-7xl w-full mx-auto">{children}</main>

        {/* Footer */}
        <footer className="border-t border-border bg-panel/40 px-4 py-3 text-xs text-muted md:px-8 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1.5">
          <div>
            Weather data by{" "}
            <a className="underline hover:text-text transition-colors" href="https://open-meteo.com/" target="_blank" rel="noreferrer">
              Open-Meteo.com
            </a>{" "}
            (CC BY 4.0) · Plant: Vidyut virtual digital twin at a real location, calibrated on real data
          </div>
          <div className="text-muted/80">Times in IST</div>
        </footer>
      </div>

      {/* Floating Alert Toast */}
      {toast && (
        <div
          role="status"
          className="fixed right-4 bottom-4 z-50 max-w-sm rounded-xl border border-border bg-panel p-4 shadow-xl animate-fade-in"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <Badge tone={toast.severity === "critical" ? "bad" : "warn"}>
                {toast.type.replaceAll("_", " ")}
              </Badge>
              <p className="text-sm font-medium text-text">{toast.message}</p>
              <p className="text-xs text-muted">
                {toIST(toast.start_utc)} → {toIST(toast.end_utc)}
              </p>
            </div>
            <button
              type="button"
              aria-label="Dismiss alert toast"
              className="flex h-6 w-6 items-center justify-center rounded text-muted hover:text-text hover:bg-border/60 transition-colors"
              onClick={() => setToast(null)}
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
