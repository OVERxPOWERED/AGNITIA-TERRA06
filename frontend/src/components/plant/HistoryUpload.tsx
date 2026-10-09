"use client";
/** Upload measured history -> data-quality report -> calibration factors, checked on held-out days before use. */
import React, { useMemo, useRef, useState } from "react";
import { AlertTriangle, Check, Upload } from "lucide-react";
import EChart from "@/components/charts/EChart";
import { Button, Pill, Segmented, Spinner } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/cn";
import { useActivePlant, type CalibrationReport, type SourceFit } from "@/lib/plant";
import { useTheme } from "@/lib/theme";

const SAMPLE = "/samples/vidyut-measured-history-sample.csv";
const pct = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${v.toFixed(d)}%`);

function SourceResult({ name, fit }: { name: string; fit: SourceFit }) {
  const { colors: c } = useTheme();
  const option = useMemo(() => {
    const d = fit.daily_mwh ?? [];
    if (!d.length) return null;
    const mono = { color: c.muted, fontSize: 11, fontFamily: "var(--font-geist-mono), monospace" };
    const line = (n: string, k: "measured" | "physics" | "calibrated", col: string, dashed = false) => ({
      name: n, type: "line" as const, symbol: "none", data: d.map((x) => x[k]), lineStyle: { color: col, width: k === "measured" ? 2 : 1.5, type: dashed ? "dashed" as const : "solid" as const }, itemStyle: { color: col },
    });
    return {
      backgroundColor: "transparent", animation: false,
      grid: { left: 48, right: 16, top: 40, bottom: 28 },
      legend: { top: 4, left: 48, textStyle: { color: c.ink, fontSize: 12 }, icon: "roundRect", itemWidth: 14, itemHeight: 4 },
      tooltip: { trigger: "axis" as const, backgroundColor: c.surface, borderColor: c.line, textStyle: { color: c.ink, fontSize: 12 }, valueFormatter: (v: unknown) => `${Number(v).toFixed(1)} MWh` },
      xAxis: { type: "category" as const, data: d.map((x) => x.date), axisLabel: mono, axisLine: { lineStyle: { color: c.line } } },
      yAxis: { type: "value" as const, name: "MWh/day", nameTextStyle: { ...mono, align: "right" as const }, axisLabel: mono, splitLine: { lineStyle: { color: c.line } } },
      series: [line("Measured", "measured", c.ink), line("Physics model", "physics", c.muted, true), line("Calibrated", "calibrated", name === "solar" ? c.solar : c.wind)],
    };
  }, [fit, c, name]);

  if (fit.error) return <p className="text-[13px] text-bad">{name === "solar" ? "Solar" : "Wind"}: {fit.error}</p>;
  return (
    <div className="rounded-lg border border-line p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-[14px] font-semibold text-ink">{name === "solar" ? "Solar" : "Wind"}</h4>
        {fit.adopted ? <Pill tone="good"><Check className="h-3 w-3" aria-hidden />Factor {fit.factor?.toFixed(3)} adopted</Pill>
          : <Pill tone="neutral">Not adopted: did not lower the held-out error</Pill>}
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-4">
        <div><dt className="text-muted">Error before</dt><dd className="num text-ink">{pct(fit.before?.nmae_pct)} of capacity</dd></div>
        <div><dt className="text-muted">Error after</dt><dd className="num text-ink">{pct(fit.after?.nmae_pct)} of capacity</dd></div>
        <div><dt className="text-muted">Bias before / after</dt><dd className="num text-ink">{pct(fit.before?.bias_pct, 0)} / {pct(fit.after?.bias_pct, 0)}</dd></div>
        <div><dt className="text-muted">Hours fitted / tested</dt><dd className="num text-ink">{fit.fit_hours} / {fit.test_hours}</dd></div>
        {fit.corr_openmeteo_ghi != null && <div><dt className="text-muted">Match with Open-Meteo sun</dt><dd className="num text-ink">r = {fit.corr_openmeteo_ghi.toFixed(2)}</dd></div>}
        {fit.corr_nasa_ghi != null && <div><dt className="text-muted">Match with NASA POWER sun</dt><dd className="num text-ink">r = {fit.corr_nasa_ghi.toFixed(2)}</dd></div>}
        {!!fit.excluded_outage_hours && <div><dt className="text-muted">Likely outage hours left out</dt><dd className="num text-ink">{fit.excluded_outage_hours}</dd></div>}
      </dl>
      <p className="mt-2 text-[12px] text-faint">Errors are measured on the last 20% of your data, which the fit never saw. Daylight hours only for solar.</p>
      {option && <div className="mt-3"><EChart option={option} height={240} ariaLabel={`Daily ${name} energy: measured, physics and calibrated`} /></div>}
    </div>
  );
}

export default function HistoryUpload({ values }: { values?: Record<string, unknown> }) {
  const ap = useActivePlant();
  const file = useRef<HTMLInputElement>(null);
  const [tz, setTz] = useState("Asia/Kolkata");
  const [stamp, setStamp] = useState<"start" | "end">("start");
  const [unit, setUnit] = useState<"MW" | "kW">("MW");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<CalibrationReport | null>(null);
  const [name, setName] = useState<string | null>(null);
  const current = ap.store.calibration;

  const send = async (f: File | undefined) => {
    if (!f) return;
    setName(f.name); setErr(null); setReport(null); setBusy(true);
    try {
      const csv = await f.text();
      const r = await api<CalibrationReport>("/calibration", {
        method: "POST",
        body: JSON.stringify({ csv, timezone: tz, stamp, unit, values: values ?? ap.store.values, location_id: (values?.location_id as string | undefined) ?? ap.site?.id }),
      });
      setReport(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "The upload failed.");
    } finally {
      setBusy(false);
      if (file.current) file.current.value = "";
    }
  };

  const adopted = report ? Object.fromEntries(Object.entries(report.sources).filter(([, v]) => v.adopted).map(([k, v]) => [k, v.factor])) : {};

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-muted">
        A CSV with a <code className="num">timestamp</code> column and <code className="num">solar_mw</code> and/or <code className="num">wind_mw</code>, at 15-minute, 30-minute or hourly resolution, up to one year.
        Vidyut checks the data, fetches the actual weather for the same hours (Open-Meteo, with NASA POWER as a second source for sunshine) and fits how your plant compares with its physics model.{" "}
        <a className="text-accent underline underline-offset-2" href={SAMPLE} download>Download a sample file</a> (virtual Dewas twin output, for trying this out).
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-[13px] text-muted">Timezone
          <select value={tz} onChange={(e) => setTz(e.target.value)} className="ml-2 h-9 rounded-lg border border-line bg-surface px-2 text-[13px] text-ink">
            <option value="Asia/Kolkata">IST (Asia/Kolkata)</option>
            <option value="UTC">UTC</option>
          </select>
        </label>
        <Segmented label="Timestamps mark" value={stamp} onChange={setStamp} options={[{ value: "start", label: "Interval start" }, { value: "end", label: "Interval end" }]} />
        <Segmented label="Unit" value={unit} onChange={setUnit} options={[{ value: "MW", label: "MW" }, { value: "kW", label: "kW" }]} />
        <Button variant="primary" onClick={() => file.current?.click()} disabled={busy}>
          {busy ? <><Spinner className="h-3.5 w-3.5" />Checking and fitting</> : <><Upload className="h-4 w-4" aria-hidden />Upload measured history</>}
        </Button>
        <input ref={file} type="file" accept=".csv,text/csv" className="sr-only" aria-label="Measured history CSV" onChange={(e) => send(e.target.files?.[0])} />
      </div>
      {busy && <p className="text-[13px] text-muted" aria-live="polite">Reading {name}, checking quality, fetching weather for the same period and fitting. This can take up to a minute for a full year.</p>}
      {err && <p role="alert" className="text-[13px] text-bad">{err}</p>}

      {current && !report && (
        <div className="rounded-lg bg-accent-soft px-4 py-3 text-[13px] text-ink">
          Calibration in use since {new Date(current.at).toLocaleString("en-IN")}: {Object.entries(current.factors).map(([k, v]) => `${k} ×${Number(v).toFixed(3)}`).join(", ") || "no factors adopted"}.
          <button className="ml-3 text-accent underline underline-offset-2" onClick={() => ap.setCalibration(null)}>Remove</button>
        </div>
      )}

      {report && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-[13px] text-muted">
            <span className="text-ink">{name}</span>
            <span>{String(report.quality.span_days ?? "?")} days</span>
            {Object.entries(report.quality).filter(([, v]) => typeof v === "object" && v).map(([k, v]) => (
              <Pill key={k}>{k}: {(v as { coverage_pct?: number }).coverage_pct}% coverage</Pill>
            ))}
            <Pill tone={report.weather.nasa_power === "ok" ? "good" : "neutral"}>NASA POWER: {report.weather.nasa_power}</Pill>
          </div>
          {report.warnings.length > 0 && (
            <div className="flex items-start gap-3 rounded-lg border border-warn/40 bg-warn-soft p-3.5 text-[13px]">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
              <ul className="space-y-1 text-ink">{report.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            </div>
          )}
          {Object.entries(report.sources).map(([k, v]) => <SourceResult key={k} name={k} fit={v} />)}
          <div className={cn("flex flex-wrap items-center gap-3 rounded-lg border border-line p-3.5 text-[13px]")}>
            <span className="text-ink">
              {Object.keys(adopted).length ? `Use ${Object.entries(adopted).map(([k, v]) => `${k} ×${Number(v).toFixed(3)}`).join(" and ")} in every forecast?` : "Nothing to apply: no factor improved the held-out error, so the forecast stays as it is."}
            </span>
            {Object.keys(adopted).length > 0 && (
              <Button variant="primary" onClick={() => { ap.setCalibration({ factors: adopted, report, at: new Date().toISOString() }); setReport(null); }}>Use this calibration</Button>
            )}
            <Button variant="ghost" onClick={() => setReport(null)}>Discard</Button>
            {ap.sync !== "local" && <span className="text-[12px] text-faint">Saved to your account when you use it.</span>}
          </div>
        </div>
      )}
    </div>
  );
}
