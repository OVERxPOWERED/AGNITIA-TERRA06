"use client";
/** Record the day-ahead schedule the operator submitted to the load despatch centre, so a later forecast can be checked against it. */
import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { api } from "@/lib/api/client";
import { useAuth } from "@/lib/auth";
import { useActivePlant } from "@/lib/plant";

interface Stored { date?: string; revision?: number; submitted_at?: string }

export default function ScheduleSubmit() {
  const ap = useActivePlant();
  const auth = useAuth();
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const blocks = ap.run.result?.dsm_schedule ?? [];
  const date = blocks.length ? new Date(Date.parse(blocks[0].block_end_utc) - 60_000 + 330 * 60_000).toISOString().slice(0, 10) : null;
  const stored = useQuery({ queryKey: ["schedule", date, auth.user?.id], enabled: !!date && !!auth.user, queryFn: () => api<Stored>(`/me/schedule?date=${date}`), retry: false });

  if (!ap.live) return <p className="text-[13px] text-muted">Schedule tracking works on a live forecast. Pick a site or customise your plant to start one.</p>;
  if (!auth.user) return <p className="text-[13px] text-muted"><Link className="text-accent underline underline-offset-2" href="/login?next=/deviation">Sign in</Link> to record the schedule you submit, so Vidyut can warn you (and WhatsApp you) when a newer forecast drifts outside the tolerance band.</p>;
  if (!date) return <p className="text-[13px] text-muted">The live forecast is still loading.</p>;

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api("/me/schedule", { method: "PUT", body: JSON.stringify({ date, blocks: blocks.map((b) => [b.block_end_utc, b.hybrid]) }) });
      await qc.invalidateQueries({ queryKey: ["schedule"] });
    } catch (e) { setErr(e instanceof Error ? e.message : "Could not save the schedule."); } finally { setBusy(false); }
  };
  const s = stored.data;
  return (
    <div className="flex flex-wrap items-center gap-3 text-[13px]">
      <span className="text-ink">
        {s?.submitted_at ? <>Schedule for <b className="font-medium">{date}</b> recorded{(s.revision ?? 0) > 0 ? ` (revision ${s.revision})` : ""}. Newer forecasts are checked against it.</> : <>Record the schedule for <b className="font-medium">{date}</b> as the one you submitted.</>}
      </span>
      <Button variant={s?.submitted_at ? "default" : "primary"} onClick={submit} disabled={busy}>
        {s?.submitted_at ? <><Check className="h-3.5 w-3.5 text-good" aria-hidden />{busy ? "Saving" : "I revised it: record this version"}</> : busy ? "Saving" : "I submitted this schedule"}
      </Button>
      {err && <span role="alert" className="text-bad">{err}</span>}
    </div>
  );
}
