/** Plain-language reading of the forecast and dispatch numbers.
 *
 *  Everything here is a deterministic function of the API data: every figure in the returned text is computed from
 *  the inputs, nothing is hard-coded, and missing inputs yield `null`/empty results (the UI then shows "—").
 *  Points are hour-ending: a point stamped 06:30 IST describes 05:30-06:30 IST. */
import type { DispatchResponse, ForecastPoint } from "@/lib/api/types";
import { toISTTimeOnly } from "@/lib/format";

type DispatchPoint = DispatchResponse["points"][number];
const HOUR = 3_600_000;
const BACKUP_EPS = 0.05; // MW below which backup / discharge counts as zero

export interface Window { start: number; end: number } // inclusive indexes

export function windows(flags: boolean[]): Window[] {
  const out: Window[] = [];
  let s = -1;
  flags.forEach((f, i) => {
    if (f && s < 0) s = i;
    if (!f && s >= 0) { out.push({ start: s, end: i - 1 }); s = -1; }
  });
  if (s >= 0) out.push({ start: s, end: flags.length - 1 });
  return out;
}

const sum = (xs: number[]) => xs.reduce((a, b) => a + b, 0);
const mean = (xs: number[]) => (xs.length ? sum(xs) / xs.length : 0);
const fmt0 = (v: number) => Math.round(v).toLocaleString("en-IN");
const fmt1 = (v: number) => v.toFixed(1);

/** "05:30 to 11:30 IST" for a window of hour-ending points. */
export function rangeLabel(times: string[], w: Window): string {
  if (w.start === 0 && w.end === times.length - 1) return `the whole ${times.length} hours`;
  const start = new Date(Date.parse(times[w.start]) - HOUR).toISOString();
  return `${toISTTimeOnly(start)} to ${toISTTimeOnly(times[w.end])} IST`;
}

const argMax = (xs: number[]) => xs.reduce((best, v, i) => (v > xs[best] ? i : best), 0);

export interface Inputs {
  solar: ForecastPoint[];
  wind: ForecastPoint[];
  hybrid: ForecastPoint[];
  dispatch?: DispatchPoint[];
  advisorBackupMwh?: number;
}

const ready = (i: Inputs) => i.solar.length > 0 && i.solar.length === i.wind.length && i.solar.length === i.hybrid.length;

export interface Briefing { headline: string; facts: string[] }

export function buildBriefing(i: Inputs): Briefing | null {
  if (!ready(i)) return null;
  const energy = sum(i.hybrid.map((p) => p.q50));
  const times = i.hybrid.map((p) => p.target_time_utc);
  const hours = i.hybrid.length;
  const backup = i.advisorBackupMwh;
  const backupText =
    backup == null ? "" : backup < 0.5 ? " No backup is planned." : ` Plan for ${fmt0(backup)} MWh of backup.`;
  const headline = `About ${fmt0(energy)} MWh expected over the next ${hours} hours.${backupText}`;

  const facts: string[] = [];
  const sIdx = argMax(i.solar.map((p) => p.q50));
  if (i.solar[sIdx].q50 > 0.5) facts.push(`Solar peaks at ${fmt1(i.solar[sIdx].q50)} MW around ${toISTTimeOnly(i.solar[sIdx].target_time_utc)} IST.`);
  const wIdx = argMax(i.wind.map((p) => p.q50));
  facts.push(`Wind averages ${fmt1(mean(i.wind.map((p) => p.q50)))} MW and tops out at ${fmt1(i.wind[wIdx].q50)} MW.`);
  if (i.dispatch?.length && i.dispatch.length === i.hybrid.length) {
    const demand = sum(i.dispatch.map((d) => d.demand_mw));
    const met = sum(i.hybrid.map((p, k) => Math.min(p.q50, i.dispatch![k].demand_mw)));
    if (demand > 0) facts.push(`Expected generation meets ${fmt0((met / demand) * 100)}% of demand; the battery and backup cover the rest.`);
    const wins = windows(i.dispatch.map((d) => d.backup_mw > BACKUP_EPS));
    const covered = sum(wins.map((w) => w.end - w.start + 1));
    if (wins.length && covered < 0.9 * hours) {
      const big = wins
        .map((w) => ({ w, mwh: sum(i.dispatch!.slice(w.start, w.end + 1).map((d) => d.backup_mw)) }))
        .sort((a, b) => b.mwh - a.mwh)[0];
      facts.push(`Largest shortfall: ${rangeLabel(times, big.w)} (${fmt0(big.mwh)} MWh of backup).`);
    } else if (wins.length) {
      facts.push(`Backup is needed in ${covered} of ${hours} hours.`);
    }
  }
  return { headline, facts };
}

export interface Chapter { id: string; title: string; range: string; value: string; body: string[] }

export function buildChapters(i: Inputs): Chapter[] {
  if (!ready(i)) return [];
  const times = i.hybrid.map((p) => p.target_time_utc);
  const solar = i.solar.map((p) => p.q50);
  const wind = i.wind.map((p) => p.q50);
  const maxS = Math.max(...solar);
  const chapters: Chapter[] = [];

  // Solar peak: the run of hours at or above 80% of the maximum that contains the maximum.
  if (maxS > 1) {
    const peakWins = windows(solar.map((v) => v >= 0.8 * maxS));
    const around = peakWins.find((w) => solar.slice(w.start, w.end + 1).includes(maxS)) ?? peakWins[0];
    const inPeakShare = (sum(solar.filter((v) => v >= 0.8 * maxS)) / sum(solar)) * 100;
    chapters.push({
      id: "solar-peak", title: "Solar peak", range: rangeLabel(times, around), value: `${fmt1(maxS)} MW max`,
      body: [`Solar reaches ${fmt1(maxS)} MW in this window.`, `Hours above 80% of that peak carry ${fmt0(inPeakShare)}% of the expected solar energy over the horizon.`],
    });
  }

  // Evening hand-over: from the first hour after the peak where solar drops under 20% of its maximum,
  // to the end of the first run of battery discharge that follows.
  if (maxS > 1) {
    const peakIdx = solar.indexOf(maxS);
    const startIdx = solar.findIndex((v, k) => k > peakIdx && v < 0.2 * maxS);
    if (startIdx >= 0) {
      const disch = i.dispatch ? windows(i.dispatch.map((d, k) => k >= startIdx && d.discharge_mw > BACKUP_EPS))[0] : undefined;
      const w: Window = { start: startIdx, end: disch ? disch.end : startIdx };
      const dMwh = i.dispatch && disch ? sum(i.dispatch.slice(disch.start, disch.end + 1).map((d) => d.discharge_mw)) : 0;
      chapters.push({
        id: "evening", title: "Evening hand-over to the battery", range: rangeLabel(times, w),
        value: i.dispatch ? `${fmt0(dMwh)} MWh discharged` : "—",
        body: [
          `Solar falls below 20% of its peak at ${toISTTimeOnly(times[startIdx])} IST.`,
          i.dispatch ? (disch ? `The advisor discharges the battery for ${disch.end - disch.start + 1} hours, ${fmt0(dMwh)} MWh in total.` : "The advisor does not discharge the battery after sunset in this plan.") : "Dispatch data is not available.",
        ],
      });
    }
  }

  // Overnight wind: the first run of hours where solar is effectively off.
  const peakAt = solar.indexOf(maxS);
  const night = windows(solar.map((v, k) => k > peakAt && v < 1))[0];
  if (night) {
    const nw = wind.slice(night.start, night.end + 1);
    chapters.push({
      id: "overnight", title: "Overnight wind", range: rangeLabel(times, night), value: `${fmt1(mean(nw))} MW average`,
      body: [`With solar off, wind averages ${fmt1(mean(nw))} MW and peaks at ${fmt1(Math.max(...nw))} MW over ${nw.length} hours.`],
    });
  }

  // Backup windows from the dispatch plan.
  if (i.dispatch?.length) {
    const wins = windows(i.dispatch.map((d) => d.backup_mw > BACKUP_EPS));
    const total = sum(i.dispatch.map((d) => d.backup_mw));
    chapters.push({
      id: "backup", title: "Backup needed", range: wins.length ? wins.map((w) => rangeLabel(times, w)).slice(0, 2).join(" and ") : "None in this horizon",
      value: `${fmt0(total)} MWh`,
      body: wins.length
        ? wins.slice(0, 4).map((w) => `${rangeLabel(times, w)}: ${fmt0(sum(i.dispatch!.slice(w.start, w.end + 1).map((d) => d.backup_mw)))} MWh.`)
        : ["Generation plus the battery covers demand in every hour."],
    });
  }
  return chapters;
}

export interface Diagnosis { title: string; body: string; caveat: string }

export function buildDiagnosis(i: Inputs): Diagnosis | null {
  if (!ready(i)) return null;
  const solarE = sum(i.solar.map((p) => p.q50));
  const windE = sum(i.wind.map((p) => p.q50));
  const solarShare = (solarE / (solarE + windE)) * 100;
  const trust = mean(i.hybrid.map((p) => p.trust_score));
  const low = i.hybrid.filter((p) => p.trust_level === "low").length;
  const widest = i.hybrid.reduce((b, p, k) => (p.q90 - p.q10 > i.hybrid[b].q90 - i.hybrid[b].q10 ? k : b), 0);
  const wpt = i.hybrid[widest];

  let title = "Generation covers demand across the horizon";
  const backupIdx = (i.dispatch ?? []).map((d, k) => (d.backup_mw > BACKUP_EPS ? k : -1)).filter((k) => k >= 0);
  if (backupIdx.length) {
    const solarOff = backupIdx.filter((k) => i.solar[k].q50 < 1).length / backupIdx.length;
    title = solarOff >= 0.7 ? "Shortfall sits in the hours when solar is off" : solarOff <= 0.3 ? "Shortfall falls in daylight hours" : "Shortfall spans both daylight and night";
  }
  const body = [
    `Solar supplies ${fmt0(solarShare)}% of the expected energy and wind ${fmt0(100 - solarShare)}%.`,
    `Average confidence is ${fmt0(trust)} out of 100, with ${low} of ${i.hybrid.length} hours rated low.`,
    `The widest 80% band is ${fmt1(wpt.q90 - wpt.q10)} MW, at ${toISTTimeOnly(wpt.target_time_utc)} IST.`,
  ].join(" ");
  return { title, body, caveat: "A rule-based summary of the numbers on this page. It is not a separate forecast." };
}
