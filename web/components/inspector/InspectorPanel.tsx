"use client";

import type { WorkbenchRun } from "@/lib/types";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { ChevronRight } from "@/components/ui/icons";
import { InspectorTabs } from "./InspectorTabs";
import { ProgressMeter } from "./ProgressMeter";
import { TraceTab } from "./TraceTab";
import { EvidenceTab } from "./EvidenceTab";
import { JoinIndexTab } from "./JoinIndexTab";
import { RawJsonTab } from "./RawJsonTab";

const LEFT_BORDER = { boxShadow: "rgba(235,230,220,0.14) -1px 0 0 0" } as const;

/** The right inspector region. Renders its own aside so it can collapse to a
 *  slim reopen rail (giving the chat full width). */
export function InspectorPanel({ run }: { run: WorkbenchRun }) {
  const { activeTab, inspectorOpen, setInspectorOpen } = useWorkbench();

  if (!inspectorOpen) {
    return (
      <aside className="flex min-h-0 flex-[0_0_44px] flex-col items-center bg-surface pt-3.5" style={LEFT_BORDER}>
        <button
          type="button"
          onClick={() => setInspectorOpen(true)}
          title="Open inspector"
          aria-label="Open inspector"
          className="flex h-[26px] w-[26px] items-center justify-center rounded-md border-0 bg-transparent text-text-muted shadow-border hover:text-primary"
        >
          <span className="rotate-180">
            <ChevronRight />
          </span>
        </button>
        <span
          className="mt-3 font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted"
          style={{ writingMode: "vertical-rl" }}
        >
          Inspector
        </span>
      </aside>
    );
  }

  return (
    <aside className="flex min-h-0 flex-[0_0_420px] flex-col bg-surface" style={LEFT_BORDER}>
      <div className="flex-[0_0_auto] px-4 pt-[13px]">
        <div className="mb-[11px] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Inspector
            </span>
            <span className="text-[12px] text-[#c9c6bd]">— turn #1</span>
          </div>
          <button
            type="button"
            onClick={() => setInspectorOpen(false)}
            title="Collapse inspector"
            aria-label="Collapse inspector"
            className="flex h-[26px] w-[26px] items-center justify-center rounded-md border-0 bg-transparent text-text-muted shadow-border hover:text-primary"
          >
            <ChevronRight />
          </button>
        </div>
        <InspectorTabs />
      </div>

      <ProgressMeter run={run} />

      <div className="flex-1 overflow-y-auto px-4 pb-6 pt-3.5">
        {activeTab === "trace" && <TraceTab run={run} />}
        {activeTab === "evidence" && <EvidenceTab evidence={run.evidence} />}
        {activeTab === "join" && <JoinIndexTab candidates={run.joinIndex} joinKey={run.joinKey} />}
        {activeTab === "raw" && <RawJsonTab federated={run.federated} />}
      </div>
    </aside>
  );
}
