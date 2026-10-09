"use client";
/** Alerts: every alert window for the latest run, with severity, how sure the model is, and acknowledge. */
import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { Button, PageHeader, Panel, Pill, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { ackAlert, useAlerts } from "@/hooks/api";
import { ALERT_LABEL, alertValue, severityTone } from "@/lib/alerts";
import { toISTTimeOnly } from "@/lib/format";

type Filter = "all" | "critical" | "warning" | "info";

export default function AlertsPage() {
  const alerts = useAlerts();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const list = (alerts.data ?? []).filter((a) => filter === "all" || a.severity === filter);

  const ack = async (id: string) => {
    setBusy(id); setFailed(null);
    try {
      await ackAlert(id);
      await qc.invalidateQueries({ queryKey: ["alerts"] });
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
        description="Windows where generation is expected to be low or high, ramps, demand shortfalls and low-confidence hours. Acknowledge an alert once someone has seen it."
        actions={<Segmented label="Severity" value={filter} onChange={setFilter} options={(["all", "critical", "warning", "info"] as const).map((v) => ({ value: v, label: v === "all" ? "All" : v[0].toUpperCase() + v.slice(1) }))} />}
      />
      {failed && <div role="alert" className="mb-4 rounded-lg border border-bad/30 bg-bad-soft px-4 py-2.5 text-[13px] text-bad">{failed}</div>}
      <QueryState isLoading={alerts.isLoading} error={alerts.error} refetch={alerts.refetch} empty={!list.length}>
        <Panel>
          <ul className="divide-y divide-line">
            {list.map((a) => (
              <li key={a.id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={severityTone(a.severity)}>{a.severity}</Pill>
                    <span className="text-[14px] font-medium">{ALERT_LABEL[a.type] ?? a.type}</span>
                    <span className="text-[12px] capitalize text-faint">{a.source}</span>
                  </div>
                  <p className="mt-1.5 text-[13px] text-ink/90">{a.message}</p>
                  <p className="num mt-1 text-[12px] text-muted">
                    {toISTTimeOnly(a.start_utc)} to {toISTTimeOnly(a.end_utc)} IST, model confidence {(100 * a.probability).toFixed(0)}%, {alertValue(a)}
                  </p>
                </div>
                <Button disabled={a.acknowledged || busy === a.id} onClick={() => ack(a.id)} className="shrink-0 self-start sm:self-center">
                  {a.acknowledged ? <><Check className="h-3.5 w-3.5 text-good" aria-hidden />Acknowledged</> : busy === a.id ? "Saving" : "Acknowledge"}
                </Button>
              </li>
            ))}
          </ul>
        </Panel>
      </QueryState>
    </>
  );
}
