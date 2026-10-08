/** Tiny UI primitives (no external UI kit needed). */
import { cn } from "@/lib/cn";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-border bg-panel p-4", className)} {...p} />;
}

export function CardTitle({ className, ...p }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn("mb-2 text-sm font-semibold tracking-wide text-muted uppercase", className)} {...p} />;
}

export function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </Card>
  );
}

const tones = {
  neutral: "bg-border text-text",
  good: "bg-good/15 text-good",
  warn: "bg-warn/15 text-warn",
  bad: "bg-bad/15 text-bad",
  hybrid: "bg-hybrid/15 text-hybrid",
} as const;

export function Badge({ tone = "neutral", className, ...p }: { tone?: keyof typeof tones } & React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", tones[tone], className)} {...p} />;
}

export function Button({ className, active, ...p }: { active?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={cn("rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-border/60 disabled:opacity-50",
        active && "bg-text text-bg hover:bg-text", className)}
      {...p}
    />
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex gap-1 rounded-lg border border-border p-1">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={cn("rounded-md px-3 py-1 text-sm", value === o.value ? "bg-text text-bg" : "text-muted hover:text-text")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function RangeInput({ label, value, min, max, step, onChange, format }: {
  label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void;
  format?: (v: number) => string;
}) {
  return (
    <label className="block text-sm">
      <span className="flex justify-between"><span>{label}</span><span className="tabular-nums text-muted">{format ? format(value) : value}</span></span>
      <input type="range" className="mt-1 w-full accent-[var(--hybrid)]" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} aria-label={label} />
    </label>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-lg bg-border/60", className)} />;
}
