"use client";
/** Assumptions & provenance: renders generated markdown docs from the backend. */
import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Card } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions } from "@/hooks/api";

const SECTIONS: [string, string][] = [
  ["data_assumptions_md", "Data assumptions & provenance"],
  ["calibration_md", "Calibration on real data"],
  ["real_data_results_md", "Results on real generation data"],
];

export default function AssumptionsPage() {
  const q = useAssumptions();

  return (
    <div className="space-y-6">
      <div className="border-b border-border/60 pb-3">
        <h1 className="text-2xl font-bold tracking-tight text-text">Assumptions & Data</h1>
        <p className="text-xs text-muted mt-0.5">
          Digital twin calibration parameters, data provenance, and empirical ground-truth validation
        </p>
      </div>

      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch}>
        {SECTIONS.map(([key, title]) => (
          <Card key={key} className="space-y-3">
            <h2 className="text-base font-semibold text-text border-b border-border/60 pb-2">
              {title}
            </h2>
            <div className="prose-sm max-w-none space-y-3 text-sm text-text/90 break-words [overflow-wrap:anywhere] [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-xs [&_h3]:font-semibold [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2 [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-2 [&_th]:bg-panel-muted/50 [&_th]:text-xs [&_th]:font-semibold [&_p]:leading-relaxed">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="w-full overflow-x-auto my-3 rounded-lg border border-border">
                      <table className="text-sm tabular-nums">{children}</table>
                    </div>
                  ),
                  pre: ({ children }) => (
                    <pre className="overflow-x-auto max-w-full p-3 rounded-lg my-3 text-xs bg-panel-muted border border-border font-mono text-text">
                      {children}
                    </pre>
                  ),
                  code: ({ children, className, ...props }) => (
                    <code className={`${className ?? ""} font-mono text-xs break-all bg-panel-muted px-1 py-0.5 rounded border border-border/60`} {...props}>
                      {children}
                    </code>
                  ),
                  img: ({ src, alt, title }) => {
                    const srcStr = typeof src === "string" ? src : "";
                    const cleanSrc = srcStr.startsWith("/") ? srcStr : `/${srcStr}`;
                    return (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={cleanSrc}
                        alt={alt ?? ""}
                        title={title}
                        className="max-w-full h-auto rounded-lg border border-border shadow-xs my-3"
                      />
                    );
                  },
                }}
              >
                {q.data?.[key] ?? ""}
              </ReactMarkdown>
            </div>
          </Card>
        ))}
      </QueryState>
    </div>
  );
}
