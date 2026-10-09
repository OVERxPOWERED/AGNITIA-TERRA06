"use client";
/** Location: choose the site every tab shows. Another site, or Dewas on live weather, builds a live forecast. */
import React, { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, MapPin } from "lucide-react";
import ConfidenceStrip from "@/components/charts/ConfidenceStrip";
import SecondOpinions from "@/components/charts/SecondOpinions";
import EChart from "@/components/charts/EChart";
import { GRID_LEFT, GRID_RIGHT, bandSeries, istMs, lineSeries, timeChart, type BandPoint } from "@/components/charts/series";
import { Button, Pill, PageHeader, Panel, PanelHeader, Skeleton, Spinner, Stat } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import type { ForecastPoint } from "@/lib/api/types";
import { ALERT_LABEL, severityTone } from "@/lib/alerts";
import { buildBriefing } from "@/lib/analysis";
import { cn } from "@/lib/cn";
import { toIST } from "@/lib/format";
import { useActivePlant, type RunState } from "@/lib/plant";
import { useTheme } from "@/lib/theme";
import Link from "next/link";

const STEPS: { key: RunState["step"]; label: string; hint: string }[] = [
  { key: "weather", label: "Fetching live weather", hint: "Latest Open-Meteo forecast for this spot" },
  { key: "models", label: "Running the forecast models", hint: "Plant simulation, physics and LightGBM" },
  { key: "plan", label: "Planning battery and backup", hint: "Alerts, dispatch and trust scores" },
];
const toBand = (pts: ForecastPoint[]): BandPoint[] => pts.map((p) => ({ t: istMs(p.target_time_utc), lo: p.q10, mid: p.q50, hi: p.q90 }));

function Progress({ run }: { run: RunState }) {
  const [now, setNow] = useState(() => run.startedAt);
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(id); }, []);
  const elapsed = Math.max(0, Math.round((now - run.startedAt) / 1000));
  const at = STEPS.findIndex((s) => s.key === run.step);
  return (
    <Panel aria-live="polite">
      <PanelHeader title="Building a live forecast" note={`This usually takes under 15 seconds. ${elapsed}s so far.`} />
      <ol className="space-y-3 px-4 pb-5 pt-4 sm:px-5">
        {STEPS.map((s, i) => {
          const state = i < at ? "done" : i === at ? "active" : "todo";
          return (
            <li key={s.key} className="flex items-start gap-3">
              <span className={cn("mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px]",
                state === "done" ? "border-transparent bg-accent text-on-accent" : state === "active" ? "border-accent text-accent" : "border-line text-faint")}>
                {state === "done" ? <Check className="h-3 w-3" aria-hidden /> : state === "active" ? <Spinner className="h-3 w-3" /> : i + 1}
              </span>
              <div>
                <div className={cn("text-[14px]", state === "todo" ? "text-muted" : "font-medium text-ink")}>{s.label}</div>
                <div className="text-[12px] text-faint">{s.hint}</div>
              </div>
            </li>
          );
        })}
      </ol>
      <div className="grid gap-3 border-t border-line px-4 py-4 sm:grid-cols-4 sm:px-5" aria-hidden>
        {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}
      </div>
    </Panel>
  );
}

export default function LocationPage() {
  const { colors: c } = useTheme();
  const ap = useActivePlant();
  const busy = ap.run.status === "loading";
  const r = ap.run.result;
  const inputs = useMemo(() => r ? ({ solar: r.solar, wind: r.wind, hybrid: r.hybrid, dispatch: r.dispatch, advisorBackupMwh: r.kpis.backup_mwh }) : null, [r]);
  const briefing = useMemo(() => (inputs ? buildBriefing(inputs) : null), [inputs]);
  const energy = r ? r.hybrid.reduce((a, p) => a + p.q50, 0) : 0;
  const peak = r ? Math.max(...r.hybrid.map((p) => p.q50)) : 0;
  const trust = r ? r.hybrid.reduce((a, p) => a + p.trust_score, 0) / r.hybrid.length : 0;

  const chart = useMemo(() => {
    if (!r) return null;
    const hb = toBand(r.hybrid), sb = toBand(r.solar), wb = toBand(r.wind);
    const demand: [number, number][] = r.dispatch.map((d) => [istMs(d.target_time_utc), d.demand_mw]);
    return timeChart({
      c, unit: "MW", tMin: hb[0].t, tMax: hb[hb.length - 1].t, bands: { hybrid: hb },
      series: [
        ...bandSeries("Hybrid", hb, c.hybrid, "hybrid", { width: 2.6, bandOpacity: 0.13 }),
        lineSeries("Solar", sb.map((p) => [p.t, p.mid]), c.solar, { dashed: true, id: "solar-mid" }),
        lineSeries("Wind", wb.map((p) => [p.t, p.mid]), c.wind, { dashed: true, id: "wind-mid" }),
        lineSeries("Demand", demand, c.demand, { width: 1.6, id: "demand-line" }),
      ],
    });
  }, [r, c]);

  const homeReplay = !ap.live && ap.site?.is_home;

  return (
    <>
      <PageHeader
        title="Location"
        description="Choose where the plant stands. Every tab then shows that site: the control room, forecast, alerts and dispatch follow your choice."
        actions={<Link href="/settings" className="t-colors inline-flex min-h-9 items-center rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink hover:bg-sunken">Plant settings</Link>}
      />
      <QueryState isLoading={!ap.ready && ap.sites.length === 0} error={null} refetch={() => {}} height="h-40">
        {ap.sites.length === 0 ? (
          <Panel className="p-6 text-[14px] text-muted">The site list is not available from this server yet. If you are running the frontend against the deployed API, it needs the latest backend (this page uses the new /locations endpoints).</Panel>
        ) : (
          <>
            <div role="radiogroup" aria-label="Site" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {ap.sites.map((s) => {
                const on = s.id === ap.site?.id;
                return (
                  <button
                    key={s.id} role="radio" aria-checked={on} disabled={busy && !on}
                    onClick={() => ap.setSite(s.id)}
                    className={cn("t-colors rounded-[10px] border p-3.5 text-left disabled:opacity-60", on ? "border-accent bg-accent-soft" : "border-line bg-surface hover:bg-sunken")}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 text-[14px] font-medium text-ink"><MapPin className="h-3.5 w-3.5 text-muted" aria-hidden />{s.name}</span>
                      {s.is_home && <Pill tone="accent">Trained here</Pill>}
                    </div>
                    <div className="mt-0.5 text-[12px] text-muted">{s.region}</div>
                    <div className="num mt-2 text-[11px] text-faint">{s.latitude.toFixed(2)}°N, {s.longitude.toFixed(2)}°E, {Math.round(s.altitude_m)} m</div>
                    <div className="mt-1 text-[12px] text-muted">{s.note}</div>
                  </button>
                );
              })}
            </div>
            <div className="mt-4 flex flex-wrap items-center gap-3 text-[13px]">
              {homeReplay && <Button variant="primary" onClick={() => ap.setLiveHome(true)}>Run Dewas on live weather</Button>}
              {ap.live && ap.site?.is_home && !ap.customised && <Button onClick={() => ap.setLiveHome(false)}>Back to the recorded replay</Button>}
              {ap.live && !busy && <Button onClick={ap.refresh}>Refresh with latest weather</Button>}
              <span className="text-muted">
                {homeReplay ? "Dewas is showing the recorded replay run (held-out test days), the one the accuracy figures come from." : ap.live ? `All tabs now show ${ap.label}.` : ""}
              </span>
            </div>
          </>
        )}
      </QueryState>

      <div className="mt-6 space-y-6">
        {busy && <Progress run={ap.run} />}
        {ap.run.status === "failed" && (
          <div role="alert" className="flex items-start gap-3 rounded-[10px] border border-bad/40 bg-bad-soft p-4 text-[13px]">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-bad" aria-hidden />
            <div>
              <div className="font-medium text-ink">The live forecast could not be built</div>
              <div className="mt-0.5 text-muted">{ap.run.error} Try Refresh in a moment.</div>
            </div>
          </div>
        )}

        {r && !busy && (
          <>
            <div className={cn("flex items-start gap-3 rounded-[10px] border p-4 text-[13px]", r.validated_here ? "border-line bg-surface" : "border-warn/40 bg-warn-soft")}>
              <AlertTriangle className={cn("mt-0.5 h-4 w-4 shrink-0", r.validated_here ? "text-accent" : "text-warn")} aria-hidden />
              <div>
                <div className="font-medium text-ink">{r.plant.plant_name}: live forecast issued {toIST(r.issue_time_utc)}</div>
                <div className="mt-0.5 text-muted">{r.caveat}</div>
              </div>
            </div>

            <Panel>
              <PanelHeader title={briefing?.headline ?? "Next 48 hours"} note={briefing?.facts.slice(0, 2).join(" ")} />
              <div className="grid grid-cols-2 gap-x-6 gap-y-5 px-4 py-5 sm:px-5 lg:grid-cols-4">
                <Stat label="Expected energy" value={`${Math.round(energy).toLocaleString("en-IN")} MWh`} note="Next 48 hours, hybrid median" />
                <Stat label="Peak output" value={`${peak.toFixed(1)} MW`} note="Highest hourly median" />
                <Stat label="Average confidence" value={`${Math.round(trust)} / 100`} tone={trust >= 70 ? "good" : trust >= 40 ? "warn" : "bad"} note="Trust score, higher is better" />
                <Stat label="Backup needed" value={`${Math.round(r.kpis.backup_mwh).toLocaleString("en-IN")} MWh`} note={r.plant.export_limit_mw ? `With the battery plan. ${Math.round(r.export_curtailed_mwh)} MWh above the ${r.plant.export_limit_mw} MW export limit.` : "With the battery plan"} />
              </div>
              <div className="border-t border-line px-2 pb-3 pt-3 sm:px-3">
                {chart && <EChart option={chart} height={360} ariaLabel={`Forecast for ${r.plant.plant_name}`} />}
              </div>
              <div className="border-t border-line px-2 pb-4 pt-3 sm:px-3">
                <div className="mb-2 text-[13px] font-medium" style={{ paddingLeft: GRID_LEFT }}>Forecast confidence by hour</div>
                <ConfidenceStrip points={r.hybrid} padLeft={GRID_LEFT} padRight={GRID_RIGHT} />
              </div>
            </Panel>

            <Panel>
              <PanelHeader title="Weather second opinions" note="The plant's physics output under each weather model, against the served forecast." />
              <div className="pb-3 pt-2"><SecondOpinions r={r} /></div>
            </Panel>

            <Panel>
              <PanelHeader title="Alerts for this site" note={r.alerts.length ? undefined : "No alerts in the next 48 hours."} />
              {r.alerts.length > 0 && (
                <ul className="divide-y divide-line px-4 pb-2 pt-2 sm:px-5">
                  {r.alerts.map((a) => (
                    <li key={a.id} className="flex flex-wrap items-center gap-2 py-2.5 text-[13px]">
                      <Pill tone={severityTone(a.severity)}>{ALERT_LABEL[a.type] ?? a.type}</Pill>
                      <span className="text-ink">{a.message}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
            <p className="text-[12px] text-muted">Generated {toIST(r.generated_at)}. Weather is live; plant output is simulated from it.</p>
          </>
        )}
      </div>
    </>
  );
}
