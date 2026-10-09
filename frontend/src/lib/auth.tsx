"use client";
/** Optional login. The token lives in localStorage; the API client attaches it to every request. */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import React, { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import { api, ApiError, readToken, TOKEN_KEY } from "@/lib/api/client";
import type { AuthOut, UserOut } from "@/lib/api/types";

const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
function setToken(t: string | null) {
  try { if (t) localStorage.setItem(TOKEN_KEY, t); else localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}

export interface Auth {
  user: UserOut | null;
  token: string | null;
  checking: boolean;
  signIn: (email: string, password: string) => Promise<UserOut>;
  signUp: (email: string, password: string, name: string) => Promise<UserOut>;
  signOut: () => Promise<void>;
  deleteAccount: () => Promise<void>;
}

const Ctx = createContext<Auth | null>(null);
export const useAuth = (): Auth => {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside <AuthProvider>");
  return c;
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribe, readToken, () => null);
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["auth-me", token],
    enabled: !!token,
    queryFn: async () => {
      try {
        return await api<UserOut>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) setToken(null);   // expired or revoked
        throw e;
      }
    },
    retry: false,
    staleTime: 5 * 60_000,
  });

  const done = useCallback((r: AuthOut) => { setToken(r.token); qc.setQueryData(["auth-me", r.token], r.user); return r.user; }, [qc]);
  const value: Auth = {
    user: token ? me.data ?? null : null,
    token,
    checking: !!token && me.isLoading,
    signIn: async (email, password) => done(await api<AuthOut>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) })),
    signUp: async (email, password, name) => done(await api<AuthOut>("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) })),
    signOut: async () => {
      try { await api("/auth/logout", { method: "POST" }); } catch { /* the token is dropped locally anyway */ }
      setToken(null);
      qc.removeQueries({ queryKey: ["auth-me"] });
    },
    deleteAccount: async () => {
      await api("/auth/me", { method: "DELETE" });
      setToken(null);
      qc.removeQueries({ queryKey: ["auth-me"] });
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
