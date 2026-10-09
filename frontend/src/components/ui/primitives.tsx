import React from "react";
import { cn } from "@/lib/cn";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-panel p-5 shadow-xs transition-colors",
        className
      )}
      {...p}
    />
  );
}

export function CardTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn(
        "mb-3 text-[11px] font-semibold tracking-wider text-muted uppercase",
        className
      )}
      {...p}
    />
  );
}

export function Kpi({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  className?: string;
}) {
  return (
    <Card className={cn("p-4 flex flex-col justify-between", className)}>
      <div className="text-xs font-medium text-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums text-text">
        {value}
      </div>
      {hint ? (
        <div className="mt-1 text-[11px] text-muted truncate" title={hint}>
          {hint}
        </div>
      ) : (
        <div className="mt-1 h-[14px]" />
      )}
    </Card>
  );
}

const tones = {
  neutral: "bg-panel-muted text-muted border border-border",
  good: "bg-good/10 text-good border border-good/25",
  warn: "bg-warn/10 text-warn border border-warn/25",
  bad: "bg-bad/10 text-bad border border-bad/25",
  hybrid: "bg-accent/10 text-accent border border-accent/25",
} as const;

export function Badge({
  tone = "neutral",
  className,
  ...p
}: { tone?: keyof typeof tones } & React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap transition-colors",
        tones[tone],
        className
      )}
      {...p}
    />
  );
}

export function Button({
  className,
  active,
  ...p
}: { active?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-lg border border-border bg-panel px-3.5 py-1.5 text-xs md:text-sm font-medium text-text transition-all duration-150 hover:bg-border/50 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-accent",
        active && "bg-accent text-white border-accent hover:bg-accent/90 shadow-xs",
        className
      )}
      {...p}
    />
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex max-w-full flex-wrap gap-1 rounded-lg border border-border bg-panel-muted/50 p-1"
    >
      {options.map((o) => {
        const isSelected = value === o.value;
        return (
          <button
            key={o.value}
            role="radio"
            type="button"
            aria-checked={isSelected}
            onClick={() => onChange(o.value)}
            className={cn(
              "rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-150 select-none focus-visible:ring-2 focus-visible:ring-accent",
              isSelected
                ? "bg-panel text-text shadow-xs font-semibold"
                : "text-muted hover:text-text hover:bg-panel/40"
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function RangeInput({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  return (
    <label className="block text-xs font-medium space-y-1.5">
      <span className="flex items-center justify-between text-muted">
        <span>{label}</span>
        <span className="tabular-nums font-semibold text-text">
          {format ? format(value) : value}
        </span>
      </span>
      <input
        type="range"
        className="w-full h-2 rounded-lg appearance-none bg-border cursor-pointer accent-[var(--accent)]"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={label}
      />
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-border/50", className)} />;
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin shrink-0", className)}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}
