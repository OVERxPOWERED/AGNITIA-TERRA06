"use client";
/** Field rendering shared by the onboarding wizard and the Settings page, driven by the API's field table. */
import React from "react";
import { Pill } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import type { FieldDef, ProfileSchema, Values } from "@/lib/plant";
import { isEntered } from "@/lib/plant";
import type { LocationInfo } from "@/lib/api/types";

export const EFFECT: Record<FieldDef["effect"] | "display", { label: string; tip: string; tone: "accent" | "neutral" | "warn" }> = {
  forecast: { label: "Changes the forecast", tip: "The forecast is scaled to this value (same technology as the trained plant is assumed).", tone: "accent" },
  plan: { label: "Changes planning", tip: "Used by the battery, backup, demand and alert planning.", tone: "accent" },
  display: { label: "Shown on every page", tip: "Used as the plant name across the dashboard.", tone: "accent" },
  recorded: { label: "Recorded only", tip: "Saved and shown, but the current models were trained for the default layout and do not use it yet.", tone: "neutral" },
};

export function clientError(f: FieldDef, raw: string | number | undefined): string | null {
  if (!isEntered(raw)) return null;
  if (f.kind !== "number") return null;
  const x = Number(raw);
  if (!Number.isFinite(x)) return "Enter a number.";
  if (f.min != null && x < f.min) return `Must be at least ${f.min}${f.unit ? ` ${f.unit}` : ""}.`;
  if (f.max != null && x > f.max) return `Must be at most ${f.max}${f.unit ? ` ${f.unit}` : ""}.`;
  return null;
}

export function FieldRow({ f, value, defaults, sites, error, onChange }: {
  f: FieldDef; value: string | number | undefined; defaults: ProfileSchema["defaults"]; sites: LocationInfo[]; error?: string | null;
  onChange: (key: string, v: string | undefined) => void;
}) {
  const entered = isEntered(value);
  const id = `f-${f.key}`;
  const def = defaults[f.key];
  const input = "t-colors h-10 w-full rounded-lg border bg-surface px-3 text-[14px] text-ink placeholder:text-faint focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent";
  const e = EFFECT[f.effect];
  return (
    <div className="min-w-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <label htmlFor={id} className="text-[14px] font-medium text-ink">{f.label}</label>
        <Pill tone={e.tone} title={e.tip}>{e.label}</Pill>
        {f.verify && <Pill tone="warn" title="Unverified figure. Treated as illustrative until you confirm it.">Illustrative</Pill>}
        <span className="ml-auto text-[12px] text-faint">{entered ? "Entered by you" : "Assumed default"}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        {f.kind === "select" ? (
          <select id={id} value={String(value ?? def ?? "")} onChange={(ev) => onChange(f.key, ev.target.value)} className={cn(input, error ? "border-bad" : "border-line")}>
            {sites.map((s) => <option key={s.id} value={s.id}>{s.name}, {s.region}</option>)}
          </select>
        ) : (
          <div className="relative w-full">
            <input
              id={id} type={f.kind === "number" ? "number" : "text"} inputMode={f.kind === "number" ? "decimal" : undefined}
              min={f.min ?? undefined} max={f.max ?? undefined} step={f.step_size ?? undefined}
              value={entered ? String(value) : ""} placeholder={def !== undefined && def !== "" ? String(def) : "Optional"}
              onChange={(ev) => onChange(f.key, ev.target.value === "" ? undefined : ev.target.value)}
              aria-invalid={!!error} aria-describedby={`${id}-h`}
              className={cn(input, f.unit && "pr-20", error ? "border-bad" : "border-line")}
            />
            {f.unit && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-muted">{f.unit}</span>}
          </div>
        )}
        {entered && f.kind !== "select" && (
          <button type="button" onClick={() => onChange(f.key, undefined)} className="t-colors shrink-0 rounded-md px-2 py-1 text-[12px] text-muted hover:bg-sunken hover:text-ink">Use default</button>
        )}
      </div>
      <p id={`${id}-h`} className={cn("mt-1 text-[12px]", error ? "text-bad" : "text-muted")}>{error ?? f.help}</p>
    </div>
  );
}

export function StepFields({ schema, step, values, sites, errors, onChange }: {
  schema: ProfileSchema; step: string; values: Values; sites: LocationInfo[]; errors: Record<string, string>;
  onChange: (key: string, v: string | undefined) => void;
}) {
  return (
    <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
      {schema.fields.filter((f) => f.step === step).map((f) => (
        <FieldRow key={f.key} f={f} value={values[f.key]} defaults={schema.defaults} sites={sites} error={errors[f.key] ?? clientError(f, values[f.key])} onChange={onChange} />
      ))}
    </div>
  );
}

export function setValue(values: Values, key: string, v: string | undefined): Values {
  const next = { ...values };
  if (v === undefined || v === "") delete next[key];
  else next[key] = v;
  return next;
}
