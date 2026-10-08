"use client";
/** Assumptions & provenance: renders the generated markdown docs from the backend. */
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
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Assumptions & Data</h1>
      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch}>
        {SECTIONS.map(([key, title]) => (
          <Card key={key}>
            <h2 className="mb-2 text-lg font-semibold">{title}</h2>
            <div className="prose-sm max-w-none space-y-2 text-sm [&_table]:w-full [&_td]:border [&_td]:border-border [&_td]:px-2 [&_th]:border [&_th]:border-border [&_th]:px-2">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{q.data?.[key] ?? ""}</ReactMarkdown>
            </div>
          </Card>
        ))}
      </QueryState>
    </div>
  );
}
