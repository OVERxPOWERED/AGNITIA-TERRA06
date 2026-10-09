import { ApiError } from "@/lib/api/client";

/**
 * TanStack Query retry policy for waking up cold backend instances (e.g. Render free tier).
 * - Up to 12 retries for network errors and HTTP 502/503/504
 * - Explicitly skips 4xx client errors and 503 NO_DATA_YET (which is a valid state)
 * - Exponential backoff capped at 8 seconds
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 12) return false;
  if (error instanceof ApiError) {
    if (error.status >= 400 && error.status < 500) return false;
    if (error.status === 503 && error.code === "NO_DATA_YET") return false;
    if ([502, 503, 504].includes(error.status)) return true;
    return false;
  }
  // Network errors (Failed to fetch, server offline, DNS failure, etc.)
  return true;
}

export function retryDelay(attemptIndex: number): number {
  return Math.min(1000 * 2 ** attemptIndex, 8000);
}

export const RETRY_CONFIG = {
  retry: shouldRetry,
  retryDelay,
};
