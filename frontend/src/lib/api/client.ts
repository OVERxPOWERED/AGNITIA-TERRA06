/** Thin fetch wrapper. Base URL from NEXT_PUBLIC_API_BASE (default http://localhost:8000). */
export const RAW_API_BASE = process.env.NEXT_PUBLIC_API_BASE;
export const IS_PRODUCTION = process.env.NODE_ENV === "production";

export function isLocalhostUrl(url?: string): boolean {
  if (!url) return false;
  return url.includes("localhost") || url.includes("127.0.0.1") || url.includes("0.0.0.0");
}

/** Check whether NEXT_PUBLIC_API_BASE is missing or invalid in a production build. */
export function getApiBaseConfigError(): string | null {
  if (!IS_PRODUCTION) return null;
  if (!RAW_API_BASE || RAW_API_BASE.trim() === "") {
    return "NEXT_PUBLIC_API_BASE is missing from this production build. Configure your backend URL in project settings.";
  }
  if (typeof window !== "undefined") {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("test_config_error") === "1") {
        return "Simulated config error: NEXT_PUBLIC_API_BASE is invalid or pointing to localhost.";
      }
    } catch {
      /* ignore */
    }
    const isLocalHost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
    if (!isLocalHost && isLocalhostUrl(RAW_API_BASE)) {
      return `NEXT_PUBLIC_API_BASE points to localhost (${RAW_API_BASE}) in production. Configure a live HTTPS backend URL in Vercel project settings.`;
    }
  }
  return null;
}

export const API_BASE = RAW_API_BASE ?? (IS_PRODUCTION ? "" : "http://localhost:8000");

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

/** Bearer token of the signed-in user (optional login). Kept in localStorage; see lib/auth.tsx. */
export const TOKEN_KEY = "vidyut_token";
export function readToken(): string | null {
  try { return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY); } catch { return null; }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = readToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let code = "HTTP_" + res.status;
    let message = res.statusText;
    try {
      const body = await res.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? body?.detail ?? message;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, typeof message === "string" ? message : JSON.stringify(message));
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}
