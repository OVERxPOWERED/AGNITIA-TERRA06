"use client";
/** Alerts: critical alerts first, impossible to miss, with what to do and when; then everything else. */
import React, { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, OctagonAlert } from "lucide-react";
import { Button, PageHeader, Panel, Pill, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { ackAlert, useAlerts } from "@/hooks/api";
import { ackLocal, isAcked, useLocalAcks } from "@/lib/acks";
import type { AlertOut } from "@/lib/api/types";
import { ALERT_ACTION, ALERT_LABEL, alertValue, severityTone, timeToStart } from "@/lib/alerts";
import { cn } from "@/lib/cn";
import { toISTTimeOnly } from "@/lib/format";
import { useActivePlant } from "@/lib/plant";

type Filter = "all" | "critical" | "warning" | "info";

function useNow(ms = 30_000) {
  const [now, setNow] = useState(0);
  useEffect(() => {
    const tick = () => setNow(Date.now());
    tick();
    const id = setInterval(tick, ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

function CriticalCard({ a, acked, busy, onAck, now }: { a: AlertOut; acked: boolean; busy: boolean; onAck: () => void; now: number }) {
  const when = now ? timeToStart(a, now) : "";
  return (
    <li className={cn("relative overflow-hidden rounded-[12px] border-2 p-4 sm:p-5", acked ? "border-line bg-surface" : "border-bad bg-bad-soft shadow-[0_10px_30px_rgb(181_71_46/0.18)]")}>
      {!acked && <span aria-hidden className="absolute inset-y-0 left-0 w-1.5 bg-bad" />}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3.5">
          <span className="relative mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center">
            {!acked && <span aria-hidden className="absolute inset-0 rounded-full bg-bad/40 motion-safe:animate-ping" />}
            <span className={cn("relative flex h-10 w-10 items-center justify-center rounded-full", acked ? "bg-sunken text-muted" : "bg-bad text-white")}>
              <OctagonAlert className="h-5 w-5" aria-hidden />
            </span>
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className={cn("text-[12px] font-bold uppercase tracking-[0.08em]", acked ? "text-muted" : "text-bad")}>Critical</span>
              <span className="text-[17px] font-semibold tracking-tight text-ink">{ALERT_LABEL[a.type] ?? a.type}</span>
              <span className="text-[12px] capitalize text-muted">{a.source}</span>
            </div>
            <p className="mt-1.5 max-w-[80ch] text-[14px] leading-relaxed text-ink">{a.message}</p>
            {ALERT_ACTION[a.type] && <p className="mt-2 text-[14px] font-medium text-ink">What to do: <span className="font-normal">{ALERT_ACTION[a.type]}</span></p>}
            <p className="num mt-2 text-[12px] text-muted">{toISTTimeOnly(a.start_utc)} to {toISTTimeOnly(a.end_utc)} IST · {alertValue(a)}</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
          {when && <span className={cn("num rounded-full px-3 py-1 text-[13px] font-semibold", acked ? "bg-sunken text-muted" : when === "Happening now" ? "bg-bad text-white" : "bg-surface text-bad shadow-[0_0_0_1px_var(--bad)]")}>{when}</span>}
          <Button variant={acked ? "default" : "primary"} disabled={acked || busy} onClick={onAck} className={acked ? "" : "!bg-bad hover:!opacity-90"}>
            {acked ? <><Check className="h-3.5 w-3.5 text-good" aria-hidden />Acknowledged</> : busy ? "Saving" : "I'm on it"}
          </Button>
        </div>
      </div>
    </li>
  );
}

export default function AlertsPage() {
  const ap = useActivePlant();
  const alerts = useAlerts();
  const local = useLocalAcks();
  const qc = useQueryClient();
  const now = useNow();
  const [filter, setFilter] = useState<Filter>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const all = alerts.data ?? [];
  const critical = all.filter((a) => a.severity === "critical").sort((x, y) => Number(isAcked(x, local)) - Number(isAcked(y, local)) || x.start_utc.localeCompare(y.start_utc));
  const rest = all.filter((a) => a.severity !== "critical" && (filter === "all" || a.severity === filter));
  const openCritical = critical.filter((a) => !isAcked(a, local)).length;

  const ack = async (id: string) => {
    setBusy(id); setFailed(null);
    try {
      if (ap.live) ackLocal(id);                     // live-run alerts are not stored on the server
      else {
        await ackAlert(id);
        await qc.invalidateQueries({ queryKey: ["alerts"] });
      }
    } catch (e) {
      setFailed(e instanceof Error ? e.message : "Could not acknowledge the alert.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <PageHeader
        title="Alerts"
        description="Critical alerts need action now: what to do and when are on each one. Below them: low or high generation, ramps, shortfalls and low-confidence hours."
        actions={<Segmented label="Severity" value={filter} onChange={setFilter} options={(["all", "critical", "warning", "info"] as const).map((v) => ({ value: v, label: v === "all" ? "All" : v[0].toUpperCase() + v.slice(1) }))} />}
      />
      {failed && <div role="alert" className="mb-4 rounded-lg border border-bad/30 bg-bad-soft px-4 py-2.5 text-[13px] text-bad">{failed}</div>}
      <QueryState isLoading={alerts.isLoading} error={alerts.error} refetch={alerts.refetch} empty={!all.length}>
        <div className="space-y-6">
          {critical.length > 0 && (filter === "all" || filter === "critical") && (
            <section aria-labelledby="crit-h">
              <h2 id="crit-h" className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
                {openCritical > 0 ? <span className="text-bad">{openCritical} critical alert{openCritical === 1 ? "" : "s"} need action</span> : "Critical alerts, all acknowledged"}
              </h2>
              <ul className="space-y-3" role="list">
                {critical.map((a) => <CriticalCard key={a.id} a={a} acked={isAcked(a, local)} busy={busy === a.id} onAck={() => ack(a.id)} now={now} />)}
              </ul>
            </section>
          )}
          {rest.length > 0 && filter !== "critical" && (
            <Panel>
              <ul className="divide-y divide-line">
                {rest.map((a) => {
                  const acked = isAcked(a, local);
                  return (
                    <li key={a.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <Pill tone={severityTone(a.severity)}>{a.severity}</Pill>
                          <span className="text-[14px] font-medium">{ALERT_LABEL[a.type] ?? a.type}</span>
                          <span className="text-[12px] capitalize text-faint">{a.source}</span>
                          {now > 0 && <span className="num text-[12px] text-muted">{timeToStart(a, now)}</span>}
                        </div>
                        <p className="mt-1.5 text-[13px] text-ink/90">{a.message}</p>
                        <p className="num mt-1 text-[12px] text-muted">
                          {toISTTimeOnly(a.start_utc)} to {toISTTimeOnly(a.end_utc)} IST, model confidence {(100 * a.probability).toFixed(0)}%, {alertValue(a)}
                        </p>
                      </div>
                      <Button disabled={acked || busy === a.id} onClick={() => ack(a.id)} className="shrink-0 self-start sm:self-center">
                        {acked ? <><Check className="h-3.5 w-3.5 text-good" aria-hidden />Acknowledged</> : busy === a.id ? "Saving" : "Acknowledge"}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </Panel>
          )}
        </div>
      </QueryState>
    </>
  );
}
