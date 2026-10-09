"use client";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCw } from "lucide-react";
import { API_BASE, ApiError } from "@/lib/api/client";
import { Button, Panel, Skeleton, Spinner } from "./primitives";

/** How many failed attempts before we stop blaming a cold start and say what else could be wrong. */
const HINT_AFTER = 3;

export function describeUnreachable(attempt: number): string[] {
  const lines = ["The API is waking up. Free hosting sleeps when idle and can take about a minute to start."];
  if (attempt >= HINT_AFTER) {
    const origin = typeof window !== "undefined" ? window.location.origin : "this site";
    lines.push(
      `Still no answer from ${API_BASE || "the API"}. If it stays like this: check the backend is running, and that its CORS setting (TERRA_CORS_ORIGINS) allows ${origin}.`,
    );
  }
  return lines;
}

/** Loading, waking-up, error and empty handling shared by every query-driven panel. */
export function QueryState({
  isLoading, error, refetch, empty, children, height = "h-72",
}: {
  isLoading: boolean;
  error?: unknown;
  refetch?: () => void;
  empty?: boolean;
  children: React.ReactNode;
  height?: string;
}) {
  const qc = useQueryClient();

  let attempt = 0;
  if (isLoading) {
    try {
      const failing = qc.getQueryCache().getAll().filter(
        (q) => q.state.fetchFailureCount > 0 && q.state.status !== "error" && q.state.fetchStatus !== "idle",
      );
      if (failing.length) attempt = Math.max(...failing.map((q) => q.state.fetchFailureCount));
    } catch {
      /* ignore cache read problems */
    }
  }

  if (isLoading && attempt > 0) {
    const [first, ...rest] = describeUnreachable(attempt);
    return (
      <div role="status" aria-live="polite" className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-warn/30 bg-warn-soft px-6 text-center ${height}`}>
        <div className="flex items-center gap-2 text-[14px] font-medium text-warn">
          <Spinner className="h-4 w-4" />
          <span>{first}</span>
        </div>
        <span className="num text-[12px] text-muted">Retrying automatically. Attempt {attempt}.</span>
        {rest.map((r) => (
          <span key={r} className="max-w-[60ch] text-[12px] text-muted">{r}</span>
        ))}
      </div>
    );
  }

  if (isLoading) return <Skeleton className={`w-full ${height}`} />;

  if (error) {
    const e = error as ApiError;
    let msg = e?.message || (error instanceof Error ? error.message : "The request failed.");
    if (e?.code === "NO_DATA_YET") msg = "No forecast has been produced yet. The first run is on its way.";
    else if (/Failed to fetch|NetworkError|fetch failed/i.test(msg)) {
      msg = "The API can't be reached. Check that it is running and that it allows requests from this address.";
    }
    return (
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-bad/30 bg-bad-soft px-4 py-3">
        <div className="flex items-center gap-2 text-[13px] font-medium text-bad">
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden />
          <span>{msg}</span>
        </div>
        {refetch && (
          <Button onClick={() => refetch()}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden />
            Try again
          </Button>
        )}
      </div>
    );
  }

  if (empty) {
    return (
      <Panel className="flex items-center justify-center px-6 py-10 text-center text-[13px] text-muted">
        Nothing to show for this period.
      </Panel>
    );
  }

  return <>{children}</>;
}
