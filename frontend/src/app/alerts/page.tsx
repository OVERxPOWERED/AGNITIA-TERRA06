"use client";
/** Alerts Center: all alert windows with severity, probability, filters and acknowledge. */
import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, AlertTriangle, Info, AlertOctagon } from "lucide-react";
import { Badge, Button, Card, Segmented } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { ackAlert, useAlerts } from "@/hooks/api";
import { toIST } from "@/lib/format";

type Filter = "all" | "critical" | "warning" | "info";

export default function AlertsPage() {
  const alerts = useAlerts();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<Filter>("all");
  const list = (alerts.data ?? []).filter((a) => filter === "all" || a.severity === filter);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border/60 pb-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text">Alerts Center</h1>
          <p className="text-xs text-muted mt-0.5">
            Operational anomalies, ramp alerts, and high/low generation warnings
          </p>
        </div>
        <Segmented
          label="Severity"
          value={filter}
          onChange={setFilter}
          options={(["all", "critical", "warning", "info"] as const).map((v) => ({
            value: v,
            label: v.charAt(0).toUpperCase() + v.slice(1),
          }))}
        />
      </div>

      <QueryState isLoading={alerts.isLoading} error={alerts.error} refetch={alerts.refetch} empty={!list.length}>
        <div className="space-y-3">
          {list.map((a) => {
            const isCritical = a.severity === "critical";
            const isWarning = a.severity === "warning";
            return (
              <Card
                key={a.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 hover:border-border/80 transition-colors"
              >
                <div className="flex items-start gap-3.5 min-w-0">
                  <div className="mt-0.5 shrink-0">
                    {isCritical ? (
                      <AlertOctagon className="h-5 w-5 text-bad" />
                    ) : isWarning ? (
                      <AlertTriangle className="h-5 w-5 text-warn" />
                    ) : (
                      <Info className="h-5 w-5 text-accent" />
                    )}
                  </div>
                  <div className="space-y-1.5 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={isCritical ? "bad" : isWarning ? "warn" : "neutral"}>
                        {a.severity}
                      </Badge>
                      <Badge tone="neutral" className="uppercase text-[10px]">
                        {a.type.replaceAll("_", " ")}
                      </Badge>
                      <Badge tone="hybrid" className="text-[10px]">
                        {a.source}
                      </Badge>
                    </div>
                    <div className="text-sm font-semibold text-text">{a.message}</div>
                    <div className="text-xs text-muted tabular-nums">
                      {toIST(a.start_utc)} → {toIST(a.end_utc)} · Confidence {(100 * a.probability).toFixed(0)}%
                    </div>
                  </div>
                </div>

                <div className="shrink-0 self-end sm:self-center">
                  <Button
                    disabled={a.acknowledged}
                    onClick={async () => {
                      await ackAlert(a.id);
                      qc.invalidateQueries({ queryKey: ["alerts"] });
                    }}
                    className="min-h-[36px] text-xs"
                  >
                    {a.acknowledged ? (
                      <span className="flex items-center gap-1.5 text-muted">
                        <CheckCircle2 className="h-3.5 w-3.5 text-good" />
                        <span>Acknowledged</span>
                      </span>
                    ) : (
                      "Acknowledge"
                    )}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      </QueryState>
    </div>
  );
}
