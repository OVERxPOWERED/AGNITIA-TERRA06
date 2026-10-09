"use client";
/** Onboarding wizard: a few plain questions about the plant, then a review. Everything is optional; unanswered fields use assumed defaults. */
import { useRouter } from "next/navigation";
import React, { useMemo, useState } from "react";
import { AlertTriangle, Check } from "lucide-react";
import HistoryUpload from "@/components/plant/HistoryUpload";
import { StepFields, clientError, setValue, visibleFields, EFFECT } from "@/components/plant/PlantFields";
import { Button, PageHeader, Panel, PanelHeader, Pill, Spinner } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { cn } from "@/lib/cn";
import { checkProfile, type ProfileCheck } from "@/lib/profile-api";
import { isEntered, useActivePlant, type FieldDef, type MaintenanceWindow, type Value, type Values } from "@/lib/plant";

export default function SetupWizard() {
  const ap = useActivePlant();
  const router = useRouter();
  const [draft, setDraft] = useState<Values | null>(null);
  const [stepIx, setStepIx] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [check, setCheck] = useState<ProfileCheck | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const values = draft ?? ap.store.values;
  const schema = ap.schema;
  const steps = useMemo(() => (schema ? [
    ...schema.steps,
    { id: "history", title: "Measured history", blurb: "Optional. Upload what the plant actually produced and Vidyut calibrates the forecast to it." },
    { id: "review", title: "Review", blurb: "Check everything, then finish." },
  ] : []), [schema]);

  const change = (k: string, v: Value | undefined) => { setDraft(setValue(values, k, v)); setCheck(null); setErrors((e) => { const n = { ...e }; delete n[k]; return n; }); };

  const stepErrors = (id: string) => {
    if (!schema) return {};
    const out: Record<string, string> = {};
    for (const f of visibleFields(schema, values, id)) { const e = clientError(f, values[f.key]); if (e) out[f.key] = e; }
    return out;
  };

  const next = async () => {
    const id = steps[stepIx].id;
    const e = stepErrors(id);
    setErrors(e);
    if (Object.keys(e).length) return;
    if (steps[stepIx + 1]?.id === "history") {
      setBusy(true); setFailure(null);
      try {
        const loc = String(values.location_id ?? schema?.defaults.location_id ?? "");
        const c = await checkProfile(values, loc);
        setCheck(c); setErrors(c.errors);
        const first = schema?.fields.find((f) => c.errors[f.key]);
        if (first) { setStepIx(schema!.steps.findIndex((s) => s.id === first.step)); return; }
      } catch (err) {
        setFailure(err instanceof Error ? err.message : "The server could not check the profile.");
        return;
      } finally { setBusy(false); }
    }
    setStepIx((i) => Math.min(i + 1, steps.length - 1));
  };

  const finish = () => {
    ap.saveProfile(values, true);
    if (values.location_id) ap.setSite(String(values.location_id));
    router.push("/");
  };

  const cur = steps[stepIx];
  const entered = schema ? schema.fields.filter((f) => isEntered(values[f.key])) : [];
  const shownValue = (f: FieldDef, v: Value | undefined): string => {
    if (!isEntered(v)) return "Not set";
    if (f.kind === "windows") { const n = (v as MaintenanceWindow[]).length; return `${n} window${n === 1 ? "" : "s"}`; }
    if (f.kind === "site") return ap.sites.find((s) => s.id === v)?.name ?? String(v);
    if (f.kind === "select") return f.options.find((o) => o.value === String(v))?.label ?? String(v);
    return `${v}${f.unit ? ` ${f.unit}` : ""}`;
  };

  return (
    <>
      <PageHeader title="Set up your plant" description="Tell Vidyut about the plant so every page, forecast and plan is for your site. Every answer is optional: anything you skip uses an assumed default, clearly marked." />
      <QueryState isLoading={!schema && !ap.ready} error={null} refetch={() => {}} height="h-60">
        {schema && cur && (
          <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
            <nav aria-label="Setup steps" className="lg:sticky lg:top-4 lg:self-start">
              <ol className="flex gap-2 overflow-x-auto lg:flex-col lg:gap-1">
                {steps.map((s, i) => (
                  <li key={s.id} className="shrink-0">
                    <button
                      type="button" aria-current={i === stepIx ? "step" : undefined} onClick={() => i <= stepIx && setStepIx(i)}
                      className={cn("t-colors flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-[13px]", i === stepIx ? "bg-sunken font-medium text-ink shadow-[0_0_0_1px_var(--line)]" : i < stepIx ? "text-ink hover:bg-sunken" : "text-muted")}
                    >
                      <span className={cn("flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px]", i < stepIx ? "border-transparent bg-accent text-on-accent" : i === stepIx ? "border-accent text-accent" : "border-line text-faint")}>
                        {i < stepIx ? <Check className="h-3 w-3" aria-hidden /> : i + 1}
                      </span>
                      {s.title}
                    </button>
                  </li>
                ))}
              </ol>
            </nav>

            <Panel>
              <PanelHeader title={cur.title} note={cur.blurb} actions={<span className="text-[12px] text-faint">Step {stepIx + 1} of {steps.length}</span>} />
              <div className="px-4 pb-5 pt-4 sm:px-5">
                {cur.id === "history" ? (
                  <HistoryUpload values={values} />
                ) : cur.id !== "review" ? (
                  <StepFields schema={schema} step={cur.id} values={values} sites={ap.sites} errors={errors} onChange={change} />
                ) : (
                  <div className="space-y-5">
                    <p className="text-[13px] text-muted">{entered.length} of {schema.fields.length} answers entered; the rest use assumed defaults.</p>
                    {check?.summary && (
                      <div className="rounded-lg bg-accent-soft px-4 py-3.5 text-[13px] text-ink">
                        <div className="font-medium">{check.summary.plant_name}</div>
                        <p className="mt-1 text-ink/85">
                          Solar {check.summary.solar_ac_mw} MW, wind {check.summary.wind_mw} MW, battery {check.summary.battery_mw} MW / {check.summary.battery_mwh} MWh, demand peaking at {check.summary.demand_peak_mw} MW
                          {check.summary.export_limit_mw ? `, export limited to ${check.summary.export_limit_mw} MW` : ""}.
                          {" "}Your layout reaches the forecast through the physics model: each hour is scaled by how much more or less your plant would make than the trained plant in that hour&apos;s weather.
                          {ap.store.calibration ? ` Calibration from your measured history is applied (${Object.entries(ap.store.calibration.factors).map(([k, v]) => `${k} ×${Number(v).toFixed(2)}`).join(", ")}).` : ""}
                        </p>
                      </div>
                    )}
                    <dl className="divide-y divide-line rounded-lg border border-line text-[13px]">
                      {visibleFields(schema, values).map((f) => {
                        const on = isEntered(values[f.key]);
                        const shown = on ? values[f.key] : schema.defaults[f.key];
                        return (
                          <div key={f.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-0.5 px-3 py-2 sm:grid-cols-[14rem_minmax(0,1fr)_auto]">
                            <dt className="text-muted">{f.label}</dt>
                            <dd className="num text-ink">{shownValue(f, shown)}</dd>
                            <span className="col-span-2 flex items-center gap-1.5 sm:col-span-1"><Pill tone={on ? "accent" : "neutral"}>{on ? "Entered" : "Assumed"}</Pill><span className="hidden text-[12px] text-faint md:inline">{EFFECT[f.effect].label}</span></span>
                          </div>
                        );
                      })}
                    </dl>
                    <div className="flex items-start gap-3 rounded-lg border border-warn/40 bg-warn-soft p-3.5 text-[13px]">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
                      <p className="text-muted">The models were trained and tested only at the Dewas plant. For any other site or layout the forecast is transferred through the physics model, so it is a live estimate, not verified accuracy. Uploading measured history is how you check and correct it for your plant.</p>
                    </div>
                    <p className="text-[12px] text-muted">{ap.sync === "local" ? "Saved in this browser. Sign in to keep it in your account across browsers." : "Saved in this browser and in your account."} You can change any answer later in Plant settings.</p>
                  </div>
                )}
                {failure && <p role="alert" className="mt-4 text-[13px] text-bad">{failure}</p>}
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 sm:px-5">
                <Button variant="ghost" onClick={() => (stepIx === 0 ? router.push("/") : setStepIx(stepIx - 1))}>{stepIx === 0 ? "Not now" : "Back"}</Button>
                {cur.id === "review" ? (
                  <Button variant="primary" onClick={finish}>Finish and open the dashboard</Button>
                ) : (
                  <Button variant="primary" onClick={next} disabled={busy}>{busy ? <><Spinner className="h-3.5 w-3.5" />Checking</> : stepIx + 2 === steps.length ? "Review" : cur.id === "history" ? "Next (or skip)" : "Next"}</Button>
                )}
              </div>
            </Panel>
          </div>
        )}
      </QueryState>
    </>
  );
}
