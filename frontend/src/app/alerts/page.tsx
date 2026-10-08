"use client";
/** Alerts Center: all alert windows with severity, probability, filters and acknowledge. */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="mr-auto text-2xl font-semibold">Alerts</h1>
        <Segmented label="Severity" value={filter} onChange={setFilter}
          options={(["all", "critical", "warning", "info"] as const).map((v) => ({ value: v, label: v }))} />
      </div>
      <QueryState isLoading={alerts.isLoading} error={alerts.error} refetch={alerts.refetch} empty={!list.length}>
        <div className="space-y-2">
          {list.map((a) => (
            <Card key={a.id} className="flex flex-wrap items-center gap-3">
              <Badge tone={a.severity === "critical" ? "bad" : a.severity === "warning" ? "warn" : "neutral"}>{a.severity}</Badge>
              <Badge>{a.type.replaceAll("_", " ")}</Badge>
              <Badge tone="hybrid">{a.source}</Badge>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{a.message}</div>
                <div className="text-xs text-muted">{toIST(a.start_utc)} → {toIST(a.end_utc)} · probability {(100 * a.probability).toFixed(0)}%</div>
              </div>
              <Button disabled={a.acknowledged} onClick={async () => { await ackAlert(a.id); qc.invalidateQueries({ queryKey: ["alerts"] }); }}>
                {a.acknowledged ? "Acknowledged" : "Acknowledge"}
              </Button>
            </Card>
          ))}
        </div>
      </QueryState>
    </div>
  );
}
