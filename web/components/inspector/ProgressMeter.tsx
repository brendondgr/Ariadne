"use client";

import { motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { EASE_OUT } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

/** Whole-run progress summary. The bar tracks completed planner stages live. */
export function ProgressMeter({ run }: { run: WorkbenchRun }) {
  const { completedStages, totalStages, replaying, statusOf } = useWorkbench();
  const specialistsDone = run.lanes.filter((l) => statusOf(l.id, "pass") === "pass").length;
  const fraction = totalStages ? completedStages / totalStages : 1;

  return (
    <div
      className="flex-[0_0_auto] px-4 pb-3 pt-[11px]"
      style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
    >
      <div className="mb-[7px] flex items-center justify-between">
        <span className="font-mono text-[11px] text-text-muted">
          {completedStages} / {totalStages} stages · {specialistsDone} specialists {specialistsDone === run.lanes.length ? "complete" : "running"}
        </span>
        <span className="font-mono text-[11px] text-primary">
          {replaying ? "running" : "done"} · {run.elapsedMs}ms
        </span>
      </div>
      <div className="h-1 overflow-hidden rounded-full bg-[rgba(235,230,220,0.08)]">
        <motion.div
          className="h-full rounded-full"
          style={{ background: "linear-gradient(90deg,#8A9E98,#4E9E96)" }}
          animate={{ width: `${fraction * 100}%` }}
          transition={{ duration: 0.4, ease: EASE_OUT }}
        />
      </div>
    </div>
  );
}
