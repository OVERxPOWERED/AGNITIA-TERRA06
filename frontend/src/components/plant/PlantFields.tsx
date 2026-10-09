"use client";
/** Field rendering shared by the onboarding wizard and the Settings page, driven by the API's field table. */
import React from "react";
import { Plus, Trash2 } from "lucide-react";
import { Pill } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import type { LocationInfo } from "@/lib/api/types";
import { isEntered, plantSources, type FieldDef, type MaintenanceWindow, type ProfileSchema, type Value, type Values } from "@/lib/plant";

export const EFFECT: Record<FieldDef["effect"], { label: string; tip: string; tone: "accent" | "neutral" | "warn" }> = {
  forecast: { label: "Changes the forecast", tip: "Applied through the physics model, equipment availability, panel condition or the export limit.", tone: "accent" },
  plan: { label: "Changes planning", tip: "Used by the battery, backup, demand and alert planning.", tone: "accent" },
  display: { label: "Shown on every page", tip: "Used as the plant name across the dashboard.", tone: "accent" },
  notify: { label: "Alert delivery", tip: "Decides who is told about critical alerts, and how.", tone: "accent" },
  recorded: { label: "Recorded only", tip: "Saved and shown in reports. Nothing in the physics depends on it.", tone: "neutral" },
};

const INPUT = "t-colors h-10 w-full rounded-lg border bg-surface px-3 text-[14px] text-ink placeholder:text-faint focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent";

export function clientError(f: FieldDef, raw: Value | undefined): string | null {
  if (!isEntered(raw)) return null;
  if (f.kind === "windows") {
    for (const [i, w] of (raw as MaintenanceWindow[]).entries()) {
      if (!w.start || !w.end || !isEntered(w.units)) return `Window ${i + 1}: fill in the start, end and units.`;
      if (w.end <= w.start) return `Window ${i + 1}: the end must be after the start.`;
    }
    return null;
  }
  if (f.kind !== "number") return null;
  const x = Number(raw);
  if (!Number.isFinite(x)) return "Enter a number.";
  if (f.min != null && x < f.min) return `Must be at least ${f.min}${f.unit ? ` ${f.unit}` : ""}.`;
  if (f.max != null && x > f.max) return `Must be at most ${f.max}${f.unit ? ` ${f.unit}` : ""}.`;
  return null;
}

function Windows({ id, value, onChange }: { id: string; value: MaintenanceWindow[]; onChange: (v: MaintenanceWindow[]) => void }) {
  const set = (i: number, patch: Partial<MaintenanceWindow>) => onChange(value.map((w, k) => (k === i ? { ...w, ...patch } : w)));
  return (
    <div id={id} className="space-y-2">
      {value.length === 0 && <p className="text-[13px] text-muted">No maintenance planned.</p>}
      {value.map((w, i) => (
        <div key={i} className="grid grid-cols-2 gap-2 rounded-lg border border-line p-2.5 sm:grid-cols-[7rem_1fr_1fr_6rem_auto]">
          <select aria-label="Source" value={w.source} onChange={(e) => set(i, { source: e.target.value as "solar" | "wind" })} className={cn(INPUT, "border-line")}>
            <option value="solar">Solar</option>
            <option value="wind">Wind</option>
          </select>
          <input aria-label="Start (IST)" type="datetime-local" value={w.start} onChange={(e) => set(i, { start: e.target.value })} className={cn(INPUT, "border-line")} />
          <input aria-label="End (IST)" type="datetime-local" value={w.end} onChange={(e) => set(i, { end: e.target.value })} className={cn(INPUT, "border-line")} />
          <input aria-label={w.source === "solar" ? "Inverters out" : "Turbines out"} type="number" min={1} placeholder="Units" value={String(w.units ?? "")} onChange={(e) => set(i, { units: e.target.value })} className={cn(INPUT, "border-line")} />
          <button type="button" aria-label="Remove window" onClick={() => onChange(value.filter((_, k) => k !== i))} className="t-colors inline-flex h-10 items-center justify-center rounded-lg px-2 text-muted hover:bg-sunken hover:text-bad">
            <Trash2 className="h-4 w-4" aria-hidden />
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...value, { source: "wind", start: "", end: "", units: 1 }])} className="t-colors inline-flex items-center gap-1.5 rounded-lg border border-dashed border-line-strong px-3 py-2 text-[13px] text-ink hover:bg-sunken">
        <Plus className="h-4 w-4" aria-hidden />Add a maintenance window
      </button>
    </div>
  );
}

export function FieldRow({ f, value, defaults, sites, error, onChange }: {
  f: FieldDef; value: Value | undefined; defaults: ProfileSchema["defaults"]; sites: LocationInfo[]; error?: string | null;
  onChange: (key: string, v: Value | undefined) => void;
}) {
  const entered = isEntered(value);
  const id = `f-${f.key}`;
  const def = defaults[f.key];
  const e = EFFECT[f.effect];
  const wide = f.kind === "windows";
  const options = f.kind === "site" ? sites.map((s) => ({ value: s.id, label: `${s.name}, ${s.region}` })) : f.options;
  return (
    <div className={cn("min-w-0", wide && "sm:col-span-2")}>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <label htmlFor={id} className="text-[14px] font-medium text-ink">{f.label}</label>
        <Pill tone={e.tone} title={e.tip}>{e.label}</Pill>
        {f.verify && <Pill tone="warn" title="Unverified figure. Treated as illustrative until you confirm it.">Illustrative</Pill>}
        <span className="ml-auto text-[12px] text-faint">{entered ? "Entered by you" : "Assumed default"}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        {wide ? (
          <div className="w-full"><Windows id={id} value={(value as MaintenanceWindow[]) ?? []} onChange={(v) => onChange(f.key, v.length ? v : undefined)} /></div>
        ) : f.kind === "select" || f.kind === "site" ? (
          <select id={id} value={String(value ?? def ?? "")} onChange={(ev) => onChange(f.key, ev.target.value)} className={cn(INPUT, error ? "border-bad" : "border-line")}>
            {!options.some((o) => o.value === String(value ?? def)) && <option value={String(value ?? def ?? "")}>{String(value ?? def ?? "")}</option>}
            {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        ) : (
          <div className="relative w-full">
            <input
              id={id} type={f.kind === "number" ? "number" : f.kind === "phone" ? "tel" : "text"} inputMode={f.kind === "number" ? "decimal" : undefined}
              min={f.min ?? undefined} max={f.max ?? undefined} step={f.step_size ?? undefined}
              value={entered ? String(value) : ""} placeholder={def !== undefined && def !== "" ? String(def) : "Optional"}
              onChange={(ev) => onChange(f.key, ev.target.value === "" ? undefined : ev.target.value)}
              aria-invalid={!!error} aria-describedby={`${id}-h`}
              className={cn(INPUT, f.unit && "pr-24", error ? "border-bad" : "border-line")}
            />
            {f.unit && <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-muted">{f.unit}</span>}
          </div>
        )}
        {entered && !wide && (
          <button type="button" onClick={() => onChange(f.key, undefined)} className="t-colors shrink-0 rounded-md px-2 py-1 text-[12px] text-muted hover:bg-sunken hover:text-ink">Use default</button>
        )}
      </div>
      <p id={`${id}-h`} className={cn("mt-1 text-[12px]", error ? "text-bad" : "text-muted")}>{error ?? f.help}</p>
    </div>
  );
}

/** Fields for one step, hiding solar or wind fields the plant does not have. */
export function visibleFields(schema: ProfileSchema, values: Values, step?: string): FieldDef[] {
  const src = plantSources(values, schema.defaults);
  return schema.fields.filter((f) => (!step || f.step === step) && (!f.applies || src.has(f.applies)));
}

export function StepFields({ schema, step, values, sites, errors, onChange }: {
  schema: ProfileSchema; step: string; values: Values; sites: LocationInfo[]; errors: Record<string, string>;
  onChange: (key: string, v: Value | undefined) => void;
}) {
  const fields = visibleFields(schema, values, step);
  if (!fields.length) return <p className="text-[13px] text-muted">Not used: this plant has no {step.startsWith("solar") ? "solar" : "wind"} generation.</p>;
  return (
    <div className="grid gap-x-8 gap-y-5 sm:grid-cols-2">
      {fields.map((f) => (
        <FieldRow key={f.key} f={f} value={values[f.key]} defaults={schema.defaults} sites={sites} error={errors[f.key] ?? clientError(f, values[f.key])} onChange={onChange} />
      ))}
    </div>
  );
}

export function setValue(values: Values, key: string, v: Value | undefined): Values {
  const next = { ...values };
  if (!isEntered(v)) delete next[key];
  else next[key] = v as Value;
  return next;
}
