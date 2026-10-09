"use client";
import React from "react";
import { Sun, Moon, Laptop } from "lucide-react";
import { useTheme, type Theme } from "@/lib/theme";
import { cn } from "@/lib/cn";

export function ThemeToggle({ collapsed = false }: { collapsed?: boolean }) {
  const { theme, setTheme, resolvedTheme } = useTheme();

  if (collapsed) {
    // Cycle toggle when sidebar is collapsed
    const nextTheme: Record<Theme, Theme> = {
      light: "dark",
      dark: "system",
      system: "light",
    };

    return (
      <button
        type="button"
        onClick={() => setTheme(nextTheme[theme])}
        title={`Theme: ${theme} (click to cycle)`}
        aria-label={`Toggle theme, current is ${theme}`}
        className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-panel-muted/50 text-muted transition-colors hover:bg-border/60 hover:text-text focus-visible:ring-2 focus-visible:ring-accent"
      >
        {theme === "system" ? (
          <Laptop className="h-4 w-4" />
        ) : resolvedTheme === "dark" ? (
          <Moon className="h-4 w-4" />
        ) : (
          <Sun className="h-4 w-4" />
        )}
      </button>
    );
  }

  return (
    <div
      role="radiogroup"
      aria-label="Theme mode"
      className="inline-flex w-full items-center justify-between rounded-lg border border-border bg-panel-muted/40 p-0.5 text-xs"
    >
      <button
        type="button"
        role="radio"
        aria-checked={theme === "light"}
        aria-label="Light theme"
        onClick={() => setTheme("light")}
        className={cn(
          "flex flex-1 items-center justify-center gap-1.5 rounded-md py-1 px-2 font-medium transition-all duration-150",
          theme === "light"
            ? "bg-panel text-text shadow-xs"
            : "text-muted hover:text-text hover:bg-panel/40"
        )}
      >
        <Sun className="h-3.5 w-3.5" />
        <span>Light</span>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={theme === "dark"}
        aria-label="Dark theme"
        onClick={() => setTheme("dark")}
        className={cn(
          "flex flex-1 items-center justify-center gap-1.5 rounded-md py-1 px-2 font-medium transition-all duration-150",
          theme === "dark"
            ? "bg-panel text-text shadow-xs"
            : "text-muted hover:text-text hover:bg-panel/40"
        )}
      >
        <Moon className="h-3.5 w-3.5" />
        <span>Dark</span>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={theme === "system"}
        aria-label="System theme"
        onClick={() => setTheme("system")}
        className={cn(
          "flex flex-1 items-center justify-center gap-1.5 rounded-md py-1 px-2 font-medium transition-all duration-150",
          theme === "system"
            ? "bg-panel text-text shadow-xs"
            : "text-muted hover:text-text hover:bg-panel/40"
        )}
      >
        <Laptop className="h-3.5 w-3.5" />
        <span>Sys</span>
      </button>
    </div>
  );
}
