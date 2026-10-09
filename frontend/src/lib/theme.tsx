"use client";
/** Theme: light | dark | system. The mode is stored in localStorage; layout.tsx applies it before first paint. */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

export type ThemeMode = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const KEY = "vidyut_theme";
const listeners = new Set<() => void>();

function readMode(): ThemeMode {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* storage can be unavailable (private mode) */
  }
  return "system";
}

function systemDark(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  mq.addEventListener("change", cb);
  return () => {
    listeners.delete(cb);
    mq.removeEventListener("change", cb);
  };
}

/** Colours that canvas charts need as literal strings (CSS variables cannot be used inside ECharts). */
export interface Palette {
  paper: string; surface: string; ink: string; muted: string; faint: string; line: string; lineStrong: string;
  accent: string; solar: string; wind: string; hybrid: string; demand: string; battery: string; backup: string;
  good: string; warn: string; bad: string;
}

export const PALETTE: Record<ResolvedTheme, Palette> = {
  light: {
    paper: "#edf0e8", surface: "#fafbf7", ink: "#17251e", muted: "#586a60", faint: "#8a998f",
    line: "#d5dcce", lineStrong: "#bcc7b3", accent: "#1e5a43", solar: "#b0700f", wind: "#1f8a7d",
    hybrid: "#1e5a43", demand: "#5a6b8a", battery: "#6d5fb8", backup: "#8b8578",
    good: "#2b7a4f", warn: "#a2690a", bad: "#b5472e",
  },
  dark: {
    paper: "#0f1512", surface: "#161e1a", ink: "#e7efe9", muted: "#93a39a", faint: "#667870",
    line: "#25312b", lineStrong: "#364639", accent: "#5fc49a", solar: "#f0b13c", wind: "#4ccfc0",
    hybrid: "#5fc49a", demand: "#9cabc8", battery: "#a99bf0", backup: "#a8a293",
    good: "#5fc49a", warn: "#e9b24a", bad: "#ee8d74",
  },
};

interface Ctx {
  mode: ThemeMode;
  resolved: ResolvedTheme;
  colors: Palette;
  setMode: (m: ThemeMode) => void;
}

const ThemeCtx = createContext<Ctx | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const mode = useSyncExternalStore(subscribe, readMode, () => "system" as ThemeMode);
  const dark = useSyncExternalStore(subscribe, systemDark, () => false);
  const resolved: ResolvedTheme = mode === "dark" || (mode === "system" && dark) ? "dark" : "light";

  useEffect(() => {
    const el = document.documentElement;
    el.classList.toggle("dark", resolved === "dark");
    el.dataset.theme = resolved;
  }, [resolved]);

  const setMode = useCallback((m: ThemeMode) => {
    try {
      localStorage.setItem(KEY, m);
    } catch {
      /* ignore */
    }
    listeners.forEach((l) => l());
  }, []);

  const value = useMemo(() => ({ mode, resolved, colors: PALETTE[resolved], setMode }), [mode, resolved, setMode]);
  return <ThemeCtx.Provider value={value}>{children}</ThemeCtx.Provider>;
}

export function useTheme(): Ctx {
  const c = useContext(ThemeCtx);
  if (!c) throw new Error("useTheme must be used inside ThemeProvider");
  return c;
}
