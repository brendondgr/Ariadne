"use client";

import { AnimatePresence, motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { EASE_OUT, tabFade } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { ChevronRight } from "@/components/ui/icons";
import { InspectorTabs } from "./InspectorTabs";
import { ProgressMeter } from "./ProgressMeter";
import { RunController } from "./RunController";
import { TraceTab } from "./TraceTab";
import { EvidenceTab } from "./EvidenceTab";
import { JoinIndexTab } from "./JoinIndexTab";
import { RawJsonTab } from "./RawJsonTab";

const LEFT_BORDER = { boxShadow: "rgba(235,230,220,0.14) -1px 0 0 0" } as const;

/** The right inspector region. Animates between full width and a slim reopen
 *  rail, and cross-fades between tabs. */
export function InspectorPanel({ run }: { run: WorkbenchRun }) {
  const { activeTab, inspectorOpen, setInspectorOpen } = useWorkbench();

  return (
    <motion.aside
      className="flex min-h-0 flex-col overflow-hidden bg-surface"
      style={{ ...LEFT_BORDER, flex: "0 0 auto" }}
      animate={{ width: inspectorOpen ? 420 : 44 }}
      transition={{ duration: 0.32, ease: EASE_OUT }}
    >
      {!inspectorOpen ? (
        <div className="flex flex-col items-center pt-3.5">
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
        </div>
      ) : (
        <>
          <div className="w-[420px] flex-[0_0_auto] px-4 pt-[13px]">
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
                  onClick={() => setInspectorOpen(false)}
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

          <div className="w-[420px] flex-[0_0_auto]">
            <ProgressMeter run={run} />
          </div>

          <div className="w-[420px] flex-1 overflow-y-auto px-4 pb-6 pt-3.5">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div key={activeTab} variants={tabFade} initial="hidden" animate="show" exit="exit">
                {activeTab === "trace" && <TraceTab run={run} />}
                {activeTab === "evidence" && <EvidenceTab evidence={run.evidence} />}
                {activeTab === "join" && <JoinIndexTab candidates={run.joinIndex} joinKey={run.joinKey} />}
                {activeTab === "raw" && <RawJsonTab federated={run.federated} />}
              </motion.div>
            </AnimatePresence>
          </div>
        </>
      )}
    </motion.aside>
  );
}
