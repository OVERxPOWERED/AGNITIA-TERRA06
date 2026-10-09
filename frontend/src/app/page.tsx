"use client";
/** Control Room: a short written briefing for the next 48 hours, the forecast chart with its confidence strip,
 *  the alerts for this run, and a plain-language day plan. Every figure comes from the API. */
import Link from "next/link";
import React, { useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import ConfidenceStrip from "@/components/charts/ConfidenceStrip";
import EChart from "@/components/charts/EChart";
import { GRID_LEFT, GRID_RIGHT, bandSeries, istMs, lineSeries, timeChart, type BandPoint } from "@/components/charts/series";
import { Panel, PanelHeader, Pill, Segmented, Stat } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAlerts, useDispatch, useForecast, useHealth, useImpact, useModels } from "@/hooks/api";
import type { ForecastPoint } from "@/lib/api/types";
import { ALERT_LABEL, alertValue, severityTone } from "@/lib/alerts";
import { buildBriefing, buildChapters, buildDiagnosis } from "@/lib/analysis";
import { inr, mwh, toIST, toISTTimeOnly } from "@/lib/format";
import { cn } from "@/lib/cn";
import { useTheme } from "@/lib/theme";

type View = "all" | "hybrid" | "split";
type SrcFilter = "all" | "solar" | "wind" | "hybrid";

const toBand = (pts: ForecastPoint[]): BandPoint[] => pts.map((p) => ({ t: istMs(p.target_time_utc), lo: p.q10, mid: p.q50, hi: p.q90 }));

export default function ControlRoom() {
  const { colors: c } = useTheme();
  const solar = useForecast("solar");
  const wind = useForecast("wind");
  const hybrid = useForecast("hybrid");
  const dispatch = useDispatch("advisor");
  const alerts = useAlerts();
  const impact = useImpact();
  const health = useHealth();
  const solarEval = useModels("solar", undefined, true);
  const windEval = useModels("wind");
  const [view, setView] = useState<View>("all");
  const [srcFilter, setSrcFilter] = useState<SrcFilter>("all");
  const [open, setOpen] = useState<string | null>("solar-peak");

  const inputs = useMemo(() => ({
    solar: solar.data?.points ?? [], wind: wind.data?.points ?? [], hybrid: hybrid.data?.points ?? [],
    dispatch: dispatch.data?.points, advisorBackupMwh: dispatch.data?.kpis.advisor.backup_mwh,
  }), [solar.data, wind.data, hybrid.data, dispatch.data]);

  const briefing = useMemo(() => buildBriefing(inputs), [inputs]);
  const chapters = useMemo(() => buildChapters(inputs), [inputs]);
  const diagnosis = useMemo(() => buildDiagnosis(inputs), [inputs]);

  const hp = useMemo(() => hybrid.data?.points ?? [], [hybrid.data]);
  const lowest = hp.length ? Math.min(...hp.map((p) => p.q10)) : null;
  const highest = hp.length ? Math.max(...hp.map((p) => p.q90)) : null;
  const avgTrust = hp.length ? hp.reduce((a, p) => a + p.trust_score, 0) / hp.length : null;
  const energy = hp.reduce((a, p) => a + p.q50, 0);
  const k = dispatch.data?.kpis.advisor;
  const loading = hybrid.isLoading || solar.isLoading || wind.isLoading;

  const chart = useMemo(() => {
    if (!hp.length) return null;
    const hb = toBand(hp);
    const sb = toBand(solar.data?.points ?? []);
    const wb = toBand(wind.data?.points ?? []);
    const demand: [number, number][] = (dispatch.data?.points ?? []).map((d) => [istMs(d.target_time_utc), d.demand_mw]);
    const bands: Record<string, BandPoint[]> = { hybrid: hb, solar: sb, wind: wb };

    const series = [] as ReturnType<typeof bandSeries>;
    if (view === "split") {
      series.push(...bandSeries("Solar", sb, c.solar, "solar", { bandOpacity: 0.16 }), ...bandSeries("Wind", wb, c.wind, "wind", { bandOpacity: 0.16 }));
    } else {
      series.push(...bandSeries("Hybrid", hb, c.hybrid, "hybrid", { width: 2.6, bandOpacity: 0.13 }));
      if (view === "all") {
        series.push(lineSeries("Solar", sb.map((p) => [p.t, p.mid]), c.solar, { dashed: true, id: "solar-mid" }), lineSeries("Wind", wb.map((p) => [p.t, p.mid]), c.wind, { dashed: true, id: "wind-mid" }));
      }
    }
    if (demand.length) series.push(lineSeries("Demand", demand, c.demand, { width: 1.6, id: "demand-line", z: 2 }));

    // Where demand is above the expected generation, fill the gap between the two curves.
    if (view !== "split" && demand.length === hb.length) {
      const base = hb.map((p, k) => [p.t, Math.min(p.mid, demand[k][1])]);
      const gap = hb.map((p, k) => [p.t, Math.max(0, demand[k][1] - p.mid)]);
      series.unshift(
        { id: "gap-lo", name: "Shortfall against demand", type: "line", stack: "gap", data: base, symbol: "none", silent: true, z: 0, lineStyle: { opacity: 0 }, itemStyle: { color: c.bad } },
        { id: "gap-w", name: "Shortfall against demand", type: "line", stack: "gap", data: gap, symbol: "none", silent: true, z: 0, lineStyle: { opacity: 0 }, itemStyle: { color: c.bad }, areaStyle: { color: c.bad, opacity: 0.11 } },
      );
    }
    const sPeak = sb.length ? sb.reduce((b, p) => (p.mid > b.mid ? p : b), sb[0]) : null;
    const solarAnchor = series.find((s) => s.id === "solar-mid");
    if (solarAnchor && sPeak && sPeak.mid > 1) {
      (solarAnchor as Record<string, unknown>).markPoint = {
        silent: true, symbol: "circle", symbolSize: 7, itemStyle: { color: c.solar },
        label: { show: true, position: "bottom", distance: 10, color: c.ink, fontSize: 11, formatter: `Solar peak ${sPeak.mid.toFixed(1)} MW` },
        data: [{ coord: [sPeak.t, sPeak.mid] }],
      };
    }
    return timeChart({ c, unit: "MW", series, bands, tMin: hb[0].t, tMax: hb[hb.length - 1].t });
  }, [hp, solar.data, wind.data, dispatch.data, view, c]);

  const list = (alerts.data ?? []).filter((a) => srcFilter === "all" || a.source === srcFilter);
  const solarRow = solarEval.data?.rows.find((r) => r.model === "ensemble");
  const windRow = windEval.data?.rows.find((r) => r.model === "ensemble");
  const soc = dispatch.data?.points.map((p) => p.soc_mwh) ?? [];

  return (
    <div className="space-y-6">
      {/* Briefing: the answer first, in a sentence, then the figures. */}
      <section aria-labelledby="briefing" className="grid gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:items-end">
        <div>
          <p className="text-[13px] text-muted">
            {hybrid.data ? `Forecast issued ${toIST(hybrid.data.issue_time_utc)}` : "Waiting for the latest forecast"}
          </p>
          {loading && !briefing ? (
            <div className="mt-2 space-y-2"><div className="skeleton h-8 w-4/5" /><div className="skeleton h-8 w-3/5" /></div>
          ) : (
            <h1 id="briefing" className="mt-1 max-w-[30ch] text-[30px] font-semibold leading-[1.15] tracking-[-0.025em] text-ink">
              {briefing?.headline ?? "The forecast is not available yet."}
            </h1>
          )}
          {briefing && (
            <ul className="mt-3 space-y-1 text-[14px] text-muted">
              {briefing.facts.map((f) => <li key={f}>{f}</li>)}
            </ul>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-y-5 sm:grid-cols-4 sm:divide-x sm:divide-line [&>div]:sm:px-5 [&>div:first-child]:sm:pl-0">
          <Stat label="Expected energy" value={hp.length ? mwh(energy) : "—"} note="median, 48 hours" />
          <Stat label="Likely range" value={lowest != null && highest != null ? `${lowest.toFixed(1)}–${highest.toFixed(1)}` : "—"} note="MW, P10 to P90" />
          <Stat label="Backup to plan" value={k ? mwh(k.backup_mwh) : "—"} tone={k && k.backup_mwh > 0.5 ? "warn" : undefined} note="advisor strategy" />
          <Stat label="Confidence" value={avgTrust != null ? `${Math.round(avgTrust)} / 100` : "—"} note="average over the horizon" />
        </dl>
      </section>

      {/* The chart is the page: annotated, with confidence aligned underneath. */}
      <Panel aria-labelledby="chart-title">
        <PanelHeader
          title={<span id="chart-title">Next 48 hours</span>}
          note="Median forecast with its 80% range, against contracted demand. Where demand is above the forecast, the gap is shaded."
          actions={
            <Segmented label="Chart layers" value={view} onChange={setView} options={[
              { value: "all", label: "All layers" }, { value: "hybrid", label: "Hybrid only" }, { value: "split", label: "Solar and wind" },
            ]} />
          }
        />
        <div className="px-2 pb-1 pt-2 sm:px-3">
          <QueryState isLoading={loading} error={hybrid.error ?? solar.error ?? wind.error} refetch={() => { hybrid.refetch(); solar.refetch(); wind.refetch(); dispatch.refetch(); }} height="h-[400px]">
            {chart && <EChart option={chart} height={400} ariaLabel="Forecast for the next 48 hours: hybrid, solar, wind and demand in megawatts" />}
          </QueryState>
        </div>
        {hp.length > 0 && (
          <div className="border-t border-line px-2 pb-4 pt-3 sm:px-3">
            <div className="mb-2 text-[13px] font-medium text-ink" style={{ paddingLeft: GRID_LEFT }}>Forecast confidence by hour</div>
            <ConfidenceStrip points={hp} padLeft={GRID_LEFT} padRight={GRID_RIGHT} />
          </div>
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Panel>
          <PanelHeader
            title="Alerts for this run"
            note={alerts.data ? `${alerts.data.filter((a) => !a.acknowledged).length} open, ${alerts.data.length} in total` : undefined}
            actions={<Segmented label="Alert source" value={srcFilter} onChange={setSrcFilter} options={[
              { value: "all", label: "All" }, { value: "solar", label: "Solar" }, { value: "wind", label: "Wind" }, { value: "hybrid", label: "Hybrid" },
            ]} />}
          />
          <div className="px-2 pb-3 pt-2 sm:px-3">
            <QueryState isLoading={alerts.isLoading} error={alerts.error} refetch={alerts.refetch} empty={!list.length} height="h-60">
              <ul className="divide-y divide-line">
                {list.slice(0, 5).map((a) => (
                  <li key={a.id} className="flex items-start justify-between gap-4 px-2 py-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Pill tone={severityTone(a.severity)}>{a.severity}</Pill>
                        <span className="text-[13px] font-medium text-ink">{ALERT_LABEL[a.type] ?? a.type}</span>
                        <span className="text-[12px] capitalize text-faint">{a.source}</span>
                      </div>
                      <p className="mt-1 text-[13px] text-muted">{a.message}</p>
                      <p className="num mt-0.5 text-[12px] text-faint">{toISTTimeOnly(a.start_utc)} to {toISTTimeOnly(a.end_utc)} IST</p>
                    </div>
                    <span className="num shrink-0 pt-0.5 text-[13px] text-ink">{alertValue(a)}</span>
                  </li>
                ))}
              </ul>
              <div className="border-t border-line px-2 pt-3 text-[13px]"><Link className="text-accent underline underline-offset-2" href="/alerts">{`See all ${list.length} on the alerts page`}</Link></div>
            </QueryState>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Systems at a glance" note="What each part of the platform says for this run." />
          <dl className="px-4 pb-4 pt-3 text-[13px] sm:px-5">
            {[
              { label: "Dispatch advisor", value: k ? `${mwh(k.backup_mwh)} backup` : "—", note: k ? `${mwh(k.curtail_mwh)} curtailed, planned cost ${inr(k.cost_inr)} (illustrative)` : "" },
              { label: "Battery", value: soc.length ? `${Math.min(...soc).toFixed(0)} to ${Math.max(...soc).toFixed(0)} MWh stored` : "—", note: k ? `${k.battery_throughput_mwh.toFixed(0)} MWh moved through the battery` : "" },
              { label: "Deviation shield", value: impact.data?.impact.dsm_charges_saved_inr != null ? `${inr(Number(impact.data.impact.dsm_charges_saved_inr))} avoided` : "—", note: "Over the test period, against persistence scheduling. Illustrative rates." },
              { label: "Solar accuracy", value: solarRow ? `${solarRow.nmae_pct.toFixed(1)}% nMAE` : "—", note: solarRow ? `Daylight hours, test period. Skill ${Math.round(100 * (solarRow.skill_vs_persistence ?? 0))}% over persistence; 80% range covers ${Math.round(100 * solarRow.picp80)}%.` : "" },
              { label: "Wind accuracy", value: windRow ? `${windRow.nmae_pct.toFixed(1)}% nMAE` : "—", note: windRow ? `Test period. Skill ${Math.round(100 * (windRow.skill_vs_persistence ?? 0))}% over persistence; 80% range covers ${Math.round(100 * windRow.picp80)}%.` : "" },
            ].map((r) => (
              <div key={r.label} className="grid grid-cols-[8.5rem_minmax(0,1fr)] gap-x-3 border-b border-line py-3 last:border-0 last:pb-0 first:pt-0">
                <dt className="text-muted">{r.label}</dt>
                <dd>
                  <div className="num font-medium text-ink">{r.value}</div>
                  {r.note && <div className="mt-0.5 text-[12px] text-faint">{r.note}</div>}
                </dd>
              </div>
            ))}
          </dl>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Panel>
          <PanelHeader title="Day plan" note="The next 48 hours in the order they happen, worked out from the forecast and the dispatch plan." />
          <ol className="px-2 pb-3 pt-2 sm:px-3">
            {chapters.length === 0 && <li className="px-3 py-6 text-[13px] text-muted">The day plan appears once the forecast and dispatch plan have loaded.</li>}
            {chapters.map((ch, i) => {
              const isOpen = open === ch.id;
              return (
                <li key={ch.id} className="border-b border-line last:border-0">
                  <button
                    aria-expanded={isOpen}
                    aria-controls={`ch-${ch.id}`}
                    onClick={() => setOpen(isOpen ? null : ch.id)}
                    className="t-colors flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left hover:bg-sunken"
                  >
                    <span className="num w-5 text-[12px] text-faint">{i + 1}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[14px] font-medium text-ink">{ch.title}</span>
                      <span className="num block text-[12px] text-muted">{ch.range}</span>
                    </span>
                    <span className="num text-[13px] text-ink">{ch.value}</span>
                    <ChevronDown className={cn("h-4 w-4 text-faint transition-transform", isOpen && "rotate-180")} aria-hidden />
                  </button>
                  {isOpen && (
                    <div id={`ch-${ch.id}`} className="space-y-1 px-3 pb-3 pl-11 text-[13px] text-muted">
                      {ch.body.map((b) => <p key={b}>{b}</p>)}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        </Panel>

        <Panel>
          <PanelHeader title="Reading of the numbers" />
          <div className="px-4 pb-5 pt-3 sm:px-5">
            {diagnosis ? (
              <div className="rounded-lg bg-accent-soft px-4 py-3.5">
                <div className="text-[15px] font-semibold tracking-tight text-ink">{diagnosis.title}</div>
                <p className="mt-1.5 max-w-[62ch] text-[13px] leading-relaxed text-ink/85">{diagnosis.body}</p>
                <p className="mt-2 text-[12px] text-muted">{diagnosis.caveat}</p>
              </div>
            ) : (
              <p className="text-[13px] text-muted">This summary appears once the forecast has loaded.</p>
            )}
          </div>
        </Panel>
      </div>

      {/* Console bar: the plain facts about where these numbers came from. */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1 rounded-[10px] bg-console px-4 py-2.5 text-[12px] text-console-ink">
        <span className="num">
          <span className="mr-2 rounded bg-white/10 px-1.5 py-0.5">info</span>
          {health.data?.latest_run ? `Run ${health.data.latest_run}` : "Run not loaded"}
          {hybrid.data ? `, issued ${toIST(hybrid.data.issue_time_utc)}` : ""}. Model: ensemble of physics and LightGBM with calibrated bands.
        </span>
        <span className="num">{health.data?.mode === "live" ? "Live" : "Replay"} in IST</span>
      </div>
    </div>
  );
}
