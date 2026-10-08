"use client";
import { ApiError } from "@/lib/api/client";
import { Button, Card, Skeleton } from "./primitives";

/** Standard loading / error / empty handling for every query-driven panel. */
export function QueryState({ isLoading, error, refetch, empty, children, height = "h-72" }: {
  isLoading: boolean; error: unknown; refetch?: () => void; empty?: boolean; children: React.ReactNode; height?: string;
}) {
  if (isLoading) return <Skeleton className={`w-full ${height}`} />;
  if (error) {
    const e = error as ApiError;
    const msg = e?.code === "NO_DATA_YET" ? "No forecast yet — the first run is being produced." : e?.message ?? "Request failed";
    return (
      <Card className="flex items-center justify-between gap-4">
        <span className="text-sm text-bad">{msg}</span>
        {refetch && <Button onClick={() => refetch()}>Retry</Button>}
      </Card>
    );
  }
  if (empty) return <Card className="text-sm text-muted">Nothing to show for this period.</Card>;
  return <>{children}</>;
}
