"use client";
/** Optional sign-in. Signing in keeps the plant profile, location and calibration in the user's account. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { Button, Panel, Segmented, Spinner } from "@/components/ui/primitives";
import { useAuth } from "@/lib/auth";

const INPUT = "t-colors mt-1.5 h-10 w-full rounded-lg border border-line bg-surface px-3 text-[14px] text-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent";

export default function LoginPage() {
  const auth = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const next = () => {
    const n = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("next") : null;
    router.push(n && n.startsWith("/") ? n : "/");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      if (mode === "in") await auth.signIn(email, password);
      else await auth.signUp(email, password, name);
      next();
    } catch (x) {
      setErr(x instanceof Error ? x.message : "Something went wrong.");
    } finally { setBusy(false); }
  };

  if (auth.user) {
    return (
      <div className="mx-auto max-w-md">
        <Panel className="p-6 text-[14px]">
          <p className="text-ink">You are signed in as <b className="font-medium">{auth.user.email}</b>.</p>
          <div className="mt-4 flex gap-2">
            <Link href="/" className="t-colors inline-flex min-h-9 items-center rounded-lg bg-accent px-3 text-[13px] font-medium text-on-accent hover:opacity-90">Open the dashboard</Link>
            <Button onClick={() => auth.signOut()}>Sign out</Button>
          </div>
        </Panel>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-[26px] font-semibold leading-tight tracking-[-0.02em] text-ink">{mode === "in" ? "Sign in" : "Create an account"}</h1>
      <p className="mt-1 text-[14px] text-muted">An account keeps your plant, location and calibration safe and the same on every browser. The dashboard works without one.</p>
      <Panel className="mt-5 p-5">
        <Segmented label="Account" value={mode} onChange={(m) => { setMode(m); setErr(null); }} options={[{ value: "in", label: "Sign in" }, { value: "up", label: "Create account" }]} />
        <form onSubmit={submit} className="mt-4 space-y-4">
          {mode === "up" && (
            <label className="block text-[14px] font-medium text-ink">Name
              <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" className={INPUT} />
            </label>
          )}
          <label className="block text-[14px] font-medium text-ink">Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" className={INPUT} />
          </label>
          <label className="block text-[14px] font-medium text-ink">Password
            <input type="password" required minLength={mode === "up" ? 8 : undefined} value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "in" ? "current-password" : "new-password"} className={INPUT} />
            {mode === "up" && <span className="mt-1 block text-[12px] font-normal text-muted">At least 8 characters.</span>}
          </label>
          {err && <p role="alert" className="text-[13px] text-bad">{err}</p>}
          <Button variant="primary" type="submit" disabled={busy} className="w-full">
            {busy ? <><Spinner className="h-3.5 w-3.5" />{mode === "in" ? "Signing in" : "Creating account"}</> : mode === "in" ? "Sign in" : "Create account"}
          </Button>
        </form>
      </Panel>
      <p className="mt-3 text-[12px] text-faint">Your plant settings in this browser are copied into a new account the first time you sign in.</p>
    </div>
  );
}
