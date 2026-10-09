"use client";
/** Plant settings: every onboarding answer, editable at any time. Stored in this browser; the API validates on save. */
import Link from "next/link";
import React, { useRef, useState } from "react";
import { Check } from "lucide-react";
import HistoryUpload from "@/components/plant/HistoryUpload";
import { StepFields, clientError, setValue, visibleFields } from "@/components/plant/PlantFields";
import { Button, PageHeader, Panel, PanelHeader, Spinner } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { checkProfile } from "@/lib/profile-api";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { isEntered, useActivePlant, type Value, type Values } from "@/lib/plant";

export default function PlantSettings() {
  const ap = useActivePlant();
  const auth = useAuth();
  const [keys, setKeys] = useState(ap.store.keys);
  const [wa, setWa] = useState<string | null>(null);
  const [draft, setDraft] = useState<Values | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const file = useRef<HTMLInputElement>(null);
  const schema = ap.schema;
  const values = draft ?? ap.store.values;
  const dirty = draft !== null && JSON.stringify(draft) !== JSON.stringify(ap.store.values);

  const change = (k: string, v: Value | undefined) => { setDraft(setValue(values, k, v)); setNote(null); setErrors((e) => { const n = { ...e }; delete n[k]; return n; }); };

  const save = async () => {
    if (!schema) return;
    const local: Record<string, string> = {};
    for (const f of visibleFields(schema, values)) { const e = clientError(f, values[f.key]); if (e) local[f.key] = e; }
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
      for (const [k, v] of Object.entries(raw.values ?? {})) if (known.has(k) && (typeof v === "string" || typeof v === "number" || Array.isArray(v)) && isEntered(v)) next[k] = v as Value;
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
            <Panel id="history">
              <PanelHeader title="Measured history" note="Upload what the plant actually produced. Vidyut checks the data and calibrates the forecast to your plant, but only if that lowers the error on days held back from the fit." />
              <div className="px-4 pb-5 pt-4 sm:px-5"><HistoryUpload /></div>
            </Panel>
            <Panel>
              <PanelHeader title="Weather data sources" note="Every live forecast also asks other weather models what they expect, runs each through your plant's physics model, and raises an alert when they disagree." />
              <div className="space-y-4 px-4 pb-5 pt-4 text-[13px] sm:px-5">
                <ul className="space-y-1.5 text-ink">
                  <li><b className="font-medium">Open-Meteo</b>: ECMWF IFS (drives the forecast), plus NOAA GFS and DWD ICON as second opinions. Free, no key.</li>
                  <li><b className="font-medium">NASA POWER</b>: satellite-based sunshine since 2001, used to cross-check uploaded history. Free, no key; recent months are not available yet.</li>
                </ul>
                <div className="grid gap-4 sm:grid-cols-2">
                  {([["solcast", "Solcast API key", "Adds Solcast's irradiance forecast as a solar second opinion. Free hobbyist keys allow about 10 calls a day."],
                     ["tomorrow", "Tomorrow.io API key", "Adds Tomorrow.io's wind forecast as a wind second opinion (free plan: 500 calls a day)."]] as const).map(([k, label, help]) => (
                    <label key={k} className="block">
                      <span className="text-[14px] font-medium text-ink">{label}</span>
                      <input type="password" autoComplete="off" value={keys[k] ?? ""} onChange={(e) => setKeys({ ...keys, [k]: e.target.value })} placeholder="Optional"
                        className="t-colors mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[14px] text-ink focus-visible:outline-2 focus-visible:outline-accent" />
                      <span className="mt-1 block text-[12px] text-muted">{help}</span>
                    </label>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <Button onClick={() => { ap.setKeys(keys); setNote("Keys saved in this browser. They are sent with each live forecast and never stored on the server."); }}>Save keys</Button>
                  <span className="text-[12px] text-muted">Keys stay in this browser, even when you are signed in.</span>
                </div>
              </div>
            </Panel>
            <Panel id="whatsapp">
              <PanelHeader title="WhatsApp alerts" note="Critical alerts, including the warning to revise your schedule with the load despatch centre, are sent to the number in the Alerts section above. The server checks your plant every 30 minutes, even when this page is closed." />
              <div className="space-y-3 px-4 pb-5 pt-4 text-[13px] sm:px-5">
                {!auth.user ? <p className="text-muted">Sign in first: alerts are sent from the server, which needs your plant saved in an account.</p> : (
                  <>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={async () => { setWa("Sending…"); try { const r = await api<{ status: string; detail: string }>("/me/notify/test", { method: "POST" }); setWa(r.status === "sent" ? "Test message sent." : r.status === "logged" ? "No WhatsApp provider is set up on the server yet: the message was only logged." : `Failed: ${r.detail}`); } catch (e) { setWa(e instanceof Error ? e.message : "Failed."); } }}>Send a test message</Button>
                      <Button onClick={async () => { setWa("Checking your plant…"); try { const r = await api<Record<string, number>>("/me/notify/check", { method: "POST" }); setWa(`Checked ${r.plants} plant: ${r.sent} sent, ${r.logged} logged, ${r.failed} failed.`); } catch (e) { setWa(e instanceof Error ? e.message : "Failed."); } }}>Check now</Button>
                    </div>
                    {wa && <p role="status" className="text-ink">{wa}</p>}
                    <p className="text-muted">Save your settings first; the number and the on/off choice are read from your saved plant.</p>
                  </>
                )}
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Account" note={auth.user ? `Signed in as ${auth.user.email}. Your plant, location and calibration are saved to your account.` : "You are not signed in. Everything is kept in this browser only."} />
              <div className="flex flex-wrap gap-2 px-4 pb-5 pt-4 sm:px-5">
                {auth.user ? (
                  <>
                    <Button onClick={() => auth.signOut()}>Sign out</Button>
                    <Button variant="ghost" onClick={async () => { if (window.confirm("Delete your account and the plant saved in it? This cannot be undone.")) { await auth.deleteAccount(); setNote("Account deleted. This browser keeps its local copy."); } }}>Delete account</Button>
                  </>
                ) : (
                  <Link href="/login?next=/settings" className="t-colors inline-flex min-h-9 items-center rounded-lg bg-accent px-3 text-[13px] font-medium text-on-accent hover:opacity-90">Sign in or create an account</Link>
                )}
              </div>
            </Panel>
            <Panel>
              <PanelHeader title="Your data" note="Export your settings to keep a copy or move them to another browser." />
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
