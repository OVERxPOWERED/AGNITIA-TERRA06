"use client";
/** Plant settings: every onboarding answer, editable at any time. Stored in this browser; the API validates on save. */
import Link from "next/link";
import React, { useRef, useState } from "react";
import { Check } from "lucide-react";
import { StepFields, clientError, setValue } from "@/components/plant/PlantFields";
import { Button, PageHeader, Panel, PanelHeader, Spinner } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { checkProfile } from "@/lib/profile-api";
import { isEntered, useActivePlant, type Values } from "@/lib/plant";

export default function PlantSettings() {
  const ap = useActivePlant();
  const [draft, setDraft] = useState<Values | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const schema = ap.schema;
  const values = draft ?? ap.store.values;
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(ap.store.values);

  const change = (k: string, v: string | undefined) => { setDraft(setValue(values, k, v)); setNote(null); setErrors((e) => { const n = { ...e }; delete n[k]; return n; }); };

  const save = async () => {
    if (!schema) return;
    const local: Record<string, string> = {};
    for (const f of schema.fields) { const e = clientError(f, values[f.key]); if (e) local[f.key] = e; }
    if (Object.keys(local).length) { setErrors(local); return; }
    setBusy(true); setNote(null);
    try {
      const c = await checkProfile(values, String(values.location_id ?? schema.defaults.location_id));
      setErrors(c.errors);
      if (Object.keys(c.errors).length) return;
      ap.saveProfile(values, true);
      if (values.location_id) ap.setSite(String(values.location_id));
      setDraft(null);
      setNote("Saved. Every page now follows these settings.");
    } catch (err) {
      setNote(err instanceof Error ? err.message : "The server could not check the settings.");
    } finally { setBusy(false); }
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify({ vidyut_plant_profile: 1, values }, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "vidyut-plant-profile.json"; a.click();
    URL.revokeObjectURL(a.href);
  };
  const importJson = async (f: File | undefined) => {
    if (!f || !schema) return;
    try {
      const raw = JSON.parse(await f.text()) as { values?: Record<string, unknown> };
      const known = new Set(schema.fields.map((x) => x.key));
      const next: Values = {};
      for (const [k, v] of Object.entries(raw.values ?? {})) if (known.has(k) && (typeof v === "string" || typeof v === "number") && isEntered(v)) next[k] = v;
      setDraft(next); setNote(`Loaded ${Object.keys(next).length} values. Review them, then save.`);
    } catch { setNote("That file is not a Vidyut plant profile."); }
    if (file.current) file.current.value = "";
  };

  return (
    <>
      <PageHeader
        title="Plant settings"
        description="The same answers as the setup wizard, all in one place. Anything you leave empty uses an assumed default."
        actions={<>
          <Link href="/setup" className="t-colors inline-flex min-h-9 items-center rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink hover:bg-sunken">Run the setup wizard</Link>
          <Button variant="primary" onClick={save} disabled={!dirty || busy}>{busy ? <><Spinner className="h-3.5 w-3.5" />Checking</> : "Save changes"}</Button>
        </>}
      />
      {note && <p role="status" className="mb-4 flex items-center gap-2 text-[13px] text-ink"><Check className="h-4 w-4 text-accent" aria-hidden />{note}</p>}
      <QueryState isLoading={!schema && !ap.ready} error={null} refetch={() => {}} height="h-60">
        {schema && (
          <div className="space-y-6">
            {schema.steps.map((s) => (
              <Panel key={s.id}>
                <PanelHeader title={s.title} note={s.blurb} />
                <div className="px-4 pb-5 pt-4 sm:px-5">
                  <StepFields schema={schema} step={s.id} values={values} sites={ap.sites} errors={errors} onChange={change} />
                </div>
              </Panel>
            ))}
            <Panel>
              <PanelHeader title="Your data" note="Settings live in this browser only. Export them to keep a copy or move them to another browser." />
              <div className="flex flex-wrap gap-2 px-4 pb-5 pt-4 sm:px-5">
                <Button onClick={exportJson}>Export as file</Button>
                <Button onClick={() => file.current?.click()}>Import from file</Button>
                <input ref={file} type="file" accept="application/json" className="sr-only" aria-label="Import plant profile file" onChange={(e) => importJson(e.target.files?.[0])} />
                <Button variant="ghost" onClick={() => { ap.resetProfile(); setDraft(null); setErrors({}); setNote("Back to the assumed defaults."); }}>Reset everything to defaults</Button>
              </div>
            </Panel>
          </div>
        )}
      </QueryState>
    </>
  );
}
