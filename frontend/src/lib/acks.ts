"use client";
/** Acknowledged alerts for live runs (those alerts are not in the server database), kept in this browser. */
import { useSyncExternalStore } from "react";
import type { AlertOut } from "@/lib/api/types";

const KEY = "vidyut_acked_v1";
const listeners = new Set<() => void>();
let cache: string[] | null = null;
const EMPTY: string[] = [];

function read(): string[] {
  if (cache) return cache;
  try { cache = JSON.parse(localStorage.getItem(KEY) ?? "[]") as string[]; } catch { cache = []; }
  return cache;
}
export function ackLocal(id: string) {
  const next = [...read().filter((x) => x !== id), id].slice(-500);
  cache = next;
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}
const subscribe = (cb: () => void) => { listeners.add(cb); return () => { listeners.delete(cb); }; };
export function useLocalAcks(): string[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}
export const isAcked = (a: AlertOut, local: string[]) => a.acknowledged || local.includes(a.id);
