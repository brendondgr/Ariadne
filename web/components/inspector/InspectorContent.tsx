"use client";

import { AnimatePresence, motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { tabFade } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { ChevronRight } from "@/components/ui/icons";
import { InspectorTabs } from "./InspectorTabs";
import { ProgressMeter } from "./ProgressMeter";
import { RunController } from "./RunController";
import { TraceTab } from "./TraceTab";
import { EvidenceTab } from "./EvidenceTab";
import { JoinIndexTab } from "./JoinIndexTab";
import { RawJsonTab } from "./RawJsonTab";

/** The inspector's inner content (header, tabs, meter, tab body), shared by the
 *  desktop inline panel and the mobile slide-over drawer. */
export function InspectorContent({ run, onClose }: { run: WorkbenchRun; onClose: () => void }) {
  const { activeTab } = useWorkbench();
  return (
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="flex-[0_0_auto] px-4 pt-[13px]">
        <div className="mb-[11px] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-muted">
              Inspector
            </span>
            <span className="text-[12px] text-[#c9c6bd]">— turn #1</span>
          </div>
          <div className="flex items-center gap-1.5">
            <RunController />
            <button
              type="button"
              onClick={onClose}
              title="Collapse inspector"
              aria-label="Collapse inspector"
              className="flex h-[26px] w-[26px] items-center justify-center rounded-md border-0 bg-transparent text-text-muted shadow-border hover:text-primary"
            >
              <ChevronRight />
            </button>
          </div>
        </div>
        <InspectorTabs />
      </div>

      <ProgressMeter run={run} />

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 pt-3.5">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={activeTab} variants={tabFade} initial="hidden" animate="show" exit="exit">
            {activeTab === "trace" && <TraceTab run={run} />}
            {activeTab === "evidence" && <EvidenceTab evidence={run.evidence} />}
            {activeTab === "join" && <JoinIndexTab candidates={run.joinIndex} joinKey={run.joinKey} />}
            {activeTab === "raw" && <RawJsonTab federated={run.federated} />}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
