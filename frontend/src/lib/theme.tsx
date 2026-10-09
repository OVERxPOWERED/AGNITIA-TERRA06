"use client";
import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useSyncExternalStore,
} from "react";

export type Theme = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export interface ThemeColors {
  bg: string;
  panel: string;
  panelMuted: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  accentSubtle: string;
  solar: string;
  wind: string;
  hybrid: string;
  demand: string;
  battery: string;
  backup: string;
  good: string;
  warn: string;
  bad: string;
}

export const THEME_COLORS: Record<ResolvedTheme, ThemeColors> = {
  light: {
    bg: "#F8F8F6",
    panel: "#FFFFFF",
    panelMuted: "#F1F1ED",
    border: "#E2E2DC",
    text: "#18181B",
    muted: "#64645E",
    accent: "#4338CA",
    accentSubtle: "#EEF2FF",
    solar: "#B45309",
    wind: "#0F766E",
    hybrid: "#4338CA",
    demand: "#475569",
    battery: "#6D28D9",
    backup: "#78716C",
    good: "#15803D",
    warn: "#B45309",
    bad: "#B91C1C",
  },
  dark: {
    bg: "#14181F",
    panel: "#1C2230",
    panelMuted: "#242B3D",
    border: "#2A344A",
    text: "#F1F5F9",
    muted: "#94A0B8",
    accent: "#818CF8",
    accentSubtle: "#252D47",
    solar: "#F59E0B",
    wind: "#2DD4BF",
    hybrid: "#818CF8",
    demand: "#94A0B8",
    battery: "#A78BFA",
    backup: "#A8A29E",
    good: "#34D399",
    warn: "#FBBF24",
    bad: "#F87171",
  },
};

export function getThemeColors(theme?: ResolvedTheme): ThemeColors {
  if (theme) return THEME_COLORS[theme];
  if (typeof document !== "undefined" && document.documentElement.classList.contains("dark")) {
    return THEME_COLORS.dark;
  }
  return THEME_COLORS.light;
}

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  colors: ThemeColors;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "system",
  resolvedTheme: "light",
  colors: THEME_COLORS.light,
  setTheme: () => {},
});

function subscribeTheme(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("vidyut:theme-set", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("vidyut:theme-set", callback);
  };
}

function getThemeSnapshot(): Theme {
  try {
    const stored = localStorage.getItem("vidyut_theme");
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // Ignore storage errors
  }
  return "system";
}

function getServerThemeSnapshot(): Theme {
  return "system";
}

function subscribeSystemDark(callback: () => void) {
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}

function getSystemDarkSnapshot(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function getServerSystemDarkSnapshot(): boolean {
  return false;
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const storedTheme = useSyncExternalStore(subscribeTheme, getThemeSnapshot, getServerThemeSnapshot);
  const systemIsDark = useSyncExternalStore(subscribeSystemDark, getSystemDarkSnapshot, getServerSystemDarkSnapshot);
  const [theme, setThemeState] = useState<Theme>(storedTheme);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setThemeState(storedTheme);
  }, [storedTheme]);

  const resolvedTheme: ResolvedTheme =
    theme === "dark" ? "dark" : theme === "light" ? "light" : systemIsDark ? "dark" : "light";

  const applyThemeToDOM = useCallback((resolved: ResolvedTheme) => {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    if (resolved === "dark") {
      root.classList.add("dark");
      root.setAttribute("data-theme", "dark");
    } else {
      root.classList.remove("dark");
      root.setAttribute("data-theme", "light");
    }
    window.dispatchEvent(new CustomEvent("vidyut:theme-change", { detail: { theme: resolved } }));
  }, []);

  useEffect(() => {
    applyThemeToDOM(resolvedTheme);
  }, [resolvedTheme, applyThemeToDOM]);

  const setTheme = useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme);
      try {
        localStorage.setItem("vidyut_theme", newTheme);
      } catch {
        // Ignore storage errors
      }
      window.dispatchEvent(new CustomEvent("vidyut:theme-set"));
    },
    []
  );

  const colors = THEME_COLORS[resolvedTheme];

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, colors, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
