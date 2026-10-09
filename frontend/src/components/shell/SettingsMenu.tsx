"use client";
import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Factory, MapPin, Monitor, Moon, Settings, Sun } from "lucide-react";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { cn } from "@/lib/cn";

const OPTIONS: { value: ThemeMode; label: string; Icon: typeof Sun }[] = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
  { value: "system", label: "Match system", Icon: Monitor },
];

/** Gear button with a small popover for the colour theme. Escape or an outside click closes it. */
export default function SettingsMenu() {
  const { mode, setMode } = useTheme();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => !box.current?.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  return (
    <div ref={box} className="relative">
      <button
        aria-label="Settings"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="t-colors inline-flex h-9 w-9 items-center justify-center rounded-lg border border-line bg-surface text-muted hover:text-ink"
      >
        <Settings className="h-4 w-4" aria-hidden />
      </button>
      {open && (
        <div role="menu" aria-label="Settings" className="absolute right-0 z-50 mt-2 w-52 rounded-[10px] border border-line bg-surface p-1.5 shadow-[0_8px_28px_rgb(0_0_0/0.14)]">
          <div className="px-2 pb-1 pt-1 text-[12px] text-muted">Colour theme</div>
          {OPTIONS.map(({ value, label, Icon }) => (
            <button
              key={value}
              role="menuitemradio"
              aria-checked={mode === value}
              onClick={() => { setMode(value); setOpen(false); }}
              className={cn("t-colors flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-[13px]", mode === value ? "bg-accent-soft text-accent" : "text-ink hover:bg-sunken")}
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </button>
          ))}
          <div className="my-1.5 border-t border-line" />
          <Link
            href="/location"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="t-colors flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-[13px] text-ink hover:bg-sunken"
          >
            <MapPin className="h-4 w-4" aria-hidden />
            Location
          </Link>
          <Link
            href="/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="t-colors flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-[13px] text-ink hover:bg-sunken"
          >
            <Factory className="h-4 w-4" aria-hidden />
            Plant settings
          </Link>
        </div>
      )}
    </div>
  );
}
