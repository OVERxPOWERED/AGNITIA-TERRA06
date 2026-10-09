"use client";
import React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { Button, Card, Skeleton, Spinner } from "./primitives";

/** Standard loading / waking up / error / empty handling for every query-driven panel. */
export function QueryState({
  isLoading,
  error,
  refetch,
  empty,
  children,
  height = "h-72",
  isRetrying,
  retryCount,
}: {
  isLoading: boolean;
  error?: unknown;
  refetch?: () => void;
  empty?: boolean;
  children: React.ReactNode;
  height?: string;
  isRetrying?: boolean;
  retryCount?: number;
}) {
  const qc = useQueryClient();

  // Determine if the backend is waking up (actively retrying network/gateway failures)
  let retrying = isRetrying ?? false;
  let attempt = retryCount ?? 1;

  if (isLoading && !retrying) {
    try {
      const allQueries = qc.getQueryCache().getAll();
      const activeRetrying = allQueries.filter(
        (q) => q.state.fetchFailureCount > 0 && q.state.status !== "error" && q.state.fetchStatus !== "idle",
      );
      if (activeRetrying.length > 0) {
        retrying = true;
        attempt = Math.max(...activeRetrying.map((q) => q.state.fetchFailureCount));
      }
    } catch {
      /* ignore cache read issues */
    }
  }

  // Waking up state while retries are in progress
  if (retrying) {
    return (
      <Card
        className={`flex flex-col items-center justify-center gap-2.5 p-6 text-center border-warn/30 bg-warn/5 ${height}`}
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-2.5 text-sm font-semibold text-warn">
          <Spinner className="h-5 w-5" />
          <span>
            The API is waking up (free hosting sleeps when idle). Retrying automatically… attempt {attempt}
          </span>
        </div>
        <span className="text-xs text-muted max-w-md">
          Render free instances take ~30–60 seconds to cold start. Panel will load automatically once ready.
        </span>
      </Card>
    );
  }

  if (isLoading) return <Skeleton className={`w-full ${height}`} />;

  // Retries exhausted or hard error
  if (error) {
    const e = error as ApiError;
    let msg = "Request failed";
    if (e?.code === "NO_DATA_YET") {
      msg = "No forecast yet — the first run is being produced.";
    } else if (e?.message) {
      msg = e.message;
    } else if (error instanceof Error) {
      msg = error.message;
    }

    if (msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("fetch failed")) {
      msg = "The API server is unreachable. Free hosting may still be starting or temporarily offline.";
    }

    return (
      <Card className="flex flex-wrap items-center justify-between gap-4 border-bad/30 bg-bad/5 p-4">
        <div className="flex items-center gap-2.5 text-sm text-bad font-medium">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{msg}</span>
        </div>
        {refetch && (
          <Button onClick={() => refetch()} className="gap-1.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Retry</span>
          </Button>
        )}
      </Card>
    );
  }

  if (empty) {
    return (
      <Card className="flex items-center justify-center p-8 text-center text-sm text-muted">
        Nothing to show for this period.
      </Card>
    );
  }

  return <>{children}</>;
}
