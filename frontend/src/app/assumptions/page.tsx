"use client";
/** Assumptions and provenance: the generated documents that explain where every number comes from. */
import React from "react";
import Markdown from "@/components/ui/Markdown";
import { Panel, PageHeader, PanelHeader } from "@/components/ui/primitives";
import { QueryState } from "@/components/ui/states";
import { useAssumptions } from "@/hooks/api";

const SECTIONS: [string, string, string][] = [
  ["data_assumptions_md", "Data and provenance", "Which inputs are real, which are simulated, and the assumptions behind them."],
  ["calibration_md", "Calibration on real data", "How the digital twin was tuned against real plant and grid data."],
  ["real_data_results_md", "Results on real generation data", "Benchmarks against measured generation from other plants and the national grid."],
];

export default function AssumptionsPage() {
  const q = useAssumptions();
  return (
    <>
      <PageHeader title="Assumptions and data" description="The plant is a digital twin at a real location, driven by real weather. These notes show exactly what is measured and what is modelled." />
      <QueryState isLoading={q.isLoading} error={q.error} refetch={q.refetch} height="h-80">
        <div className="space-y-6">
          {SECTIONS.map(([key, title, note]) => (
            <Panel key={key}>
              <PanelHeader title={title} note={note} />
              <div className="px-4 pb-5 pt-2 sm:px-5"><Markdown>{q.data?.[key] ?? ""}</Markdown></div>
            </Panel>
          ))}
        </div>
      </QueryState>
    </>
  );
}
