"use client";

import { motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { EASE_OUT } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { ChevronRight } from "@/components/ui/icons";
import { InspectorContent } from "./InspectorContent";

const LEFT_BORDER = { boxShadow: "rgba(235,230,220,0.14) -1px 0 0 0" } as const;

/** Desktop (lg+) inline inspector. Animates between full width and a slim
 *  reopen rail. The mobile/tablet drawer is a separate component. */
export function InspectorPanel({ run }: { run: WorkbenchRun }) {
  const { inspectorOpen, setInspectorOpen } = useWorkbench();

  return (
    <motion.aside
      className="hidden min-h-0 flex-col overflow-hidden bg-surface lg:flex"
      style={{ ...LEFT_BORDER, flex: "0 0 auto" }}
      animate={{ width: inspectorOpen ? 420 : 44 }}
      transition={{ duration: 0.32, ease: EASE_OUT }}
    >
      {inspectorOpen ? (
        <div className="w-[420px] flex-1 overflow-hidden">
          <InspectorContent run={run} onClose={() => setInspectorOpen(false)} />
        </div>
      ) : (
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
      )}
    </motion.aside>
  );
}
