"use client";
/** Small set of building blocks. One radius family (10px panels, 8px controls), hairline borders, no shadows to speak of. */
import React, { useRef } from "react";
import { cn } from "@/lib/cn";

export function Panel({ className, children, ...rest }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("rounded-[10px] border border-line bg-surface shadow-[var(--shadow)]", className)} {...rest}>
      {children}
    </section>
  );
}

/** Title + optional note on the left, optional controls on the right. */
export function PanelHeader({ title, note, actions, className }: {
  title: React.ReactNode; note?: React.ReactNode; actions?: React.ReactNode; className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-start justify-between gap-x-6 gap-y-2 px-4 pt-4 sm:px-5", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
        {note && <p className="mt-0.5 max-w-[68ch] text-[13px] text-muted">{note}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function PageHeader({ title, description, actions }: {
  title: string; description?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-[70ch] text-[14px] text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** A figure with a plain label: no box, so a row of these reads as one strip. */
export function Stat({ label, value, note, tone, className }: {
  label: string; value: React.ReactNode; note?: React.ReactNode; tone?: "good" | "warn" | "bad"; className?: string;
}) {
  const toneCls = tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "good" ? "text-good" : "text-ink";
  return (
    <div className={cn("min-w-0", className)}>
      <div className="text-[13px] text-muted">{label}</div>
      <div className={cn("num mt-1 text-[24px] font-medium leading-none", toneCls)}>{value}</div>
      {note && <div className="mt-1.5 text-[12px] text-faint">{note}</div>}
    </div>
  );
}

type Tone = "neutral" | "accent" | "good" | "warn" | "bad";
const TONES: Record<Tone, string> = {
  neutral: "bg-sunken text-muted border-line",
  accent: "bg-accent-soft text-accent border-transparent",
  good: "bg-good-soft text-good border-transparent",
  warn: "bg-warn-soft text-warn border-transparent",
  bad: "bg-bad-soft text-bad border-transparent",
};

export function Pill({ tone = "neutral", className, children, ...rest }: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[12px] font-medium leading-5", TONES[tone], className)}
      {...rest}
    >
      {children}
    </span>
  );
}

export function Dot({ color, className }: { color: string; className?: string }) {
  return <span aria-hidden className={cn("inline-block h-2 w-2 shrink-0 rounded-full", className)} style={{ background: color }} />;
}

export function Button({ className, variant = "default", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "ghost" }) {
  const v =
    variant === "primary"
      ? "bg-accent text-on-accent border-transparent hover:opacity-90"
      : variant === "ghost"
        ? "border-transparent text-muted hover:bg-sunken hover:text-ink"
        : "border-line bg-surface text-ink hover:bg-sunken";
  return (
    <button
      className={cn("t-colors inline-flex min-h-9 items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-[13px] font-medium disabled:cursor-not-allowed disabled:opacity-50", v, className)}
      {...props}
    />
  );
}

/** Radio-group style switch. Arrow keys move the selection; options wrap on narrow screens. */
export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (e: React.KeyboardEvent, i: number) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = options[(i + d + options.length) % options.length];
    onChange(next.value);
    requestAnimationFrame(() => ref.current?.querySelectorAll<HTMLButtonElement>("button")[(i + d + options.length) % options.length]?.focus());
  };
  return (
    <div ref={ref} role="radiogroup" aria-label={label} className="inline-flex max-w-full flex-wrap gap-0.5 rounded-lg border border-line bg-sunken p-0.5">
      {options.map((o, i) => {
        const on = value === o.value;
        return (
          <button
            key={o.value}
            role="radio"
            aria-checked={on}
            tabIndex={on ? 0 : -1}
            onClick={() => onChange(o.value)}
            onKeyDown={(e) => move(e, i)}
            className={cn(
              "t-colors min-h-8 rounded-md px-3 py-1 text-[13px] font-medium",
              on ? "bg-surface text-ink shadow-[0_0_0_1px_var(--line)]" : "text-muted hover:text-ink",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function RangeInput({ label, value, min, max, step, onChange, format }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format?: (v: number) => string;
}) {
  return (
    <label className="block text-[13px]">
      <span className="flex items-baseline justify-between gap-3">
        <span className="text-ink">{label}</span>
        <span className="num text-muted">{format ? format(value) : value}</span>
      </span>
      <input
        type="range"
        className="mt-2 h-1.5 w-full cursor-pointer accent-[var(--accent)]"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("skeleton", className)} />;
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="0 0 24 24" className={cn("spin h-4 w-4", className)} fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

/* Table styling shared by every data table. Header text is sentence case; numbers use the mono face. */
export const tableCls = "w-full border-collapse text-[13px]";
export const thCls = "whitespace-nowrap border-b border-line px-3 py-2 text-left text-[12px] font-medium text-muted";
export const tdCls = "whitespace-nowrap border-b border-line/70 px-3 py-2 text-ink";
export const tdNum = `${tdCls} num`;
