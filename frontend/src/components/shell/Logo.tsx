import React from "react";
import { cn } from "@/lib/cn";

export function VidyutIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("shrink-0", className)}
      aria-hidden="true"
    >
      {/* Crisp geometric 'V' built from a lightning bolt motif: down from top-left, kicks out right, steps up to top-right */}
      <path d="M4.5 4.5L11 19.5L14.5 13.5H12.5L19.5 4.5" />
    </svg>
  );
}

export function Logo({
  collapsed = false,
  className,
}: {
  collapsed?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-white shadow-xs">
        <VidyutIcon className="h-5 w-5" />
      </div>
      {!collapsed && (
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-base font-bold tracking-tight text-text leading-none">
              Vidyut
            </span>
            <span className="rounded bg-accent/15 px-1 py-0.2 text-[9px] font-semibold uppercase tracking-wider text-accent leading-tight">
              Hybrid
            </span>
          </div>
          <span className="text-[11px] font-medium text-muted truncate mt-0.5 leading-tight">
            Dewas hybrid · Indore region
          </span>
        </div>
      )}
    </div>
  );
}
