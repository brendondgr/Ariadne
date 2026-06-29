"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { EASE_OUT } from "@/lib/motion";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { TraceStage } from "./TraceStage";
import { SpecialistLane } from "./SpecialistLane";

/** Ordered planner timeline + specialist lanes. Owns planner-stage expansion,
 *  reacts to cross-panel focus, and grows the thread as stages complete. */
export function TraceTab({ run }: { run: WorkbenchRun }) {
  const { focusStageId, focusNonce, statusOf, completedStages, totalStages } = useWorkbench();
  const [openMap, setOpenMap] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      run.plannerStages.map((s) => [s.id, s.id === "stage-probe" || s.id === "stage-gate"]),
    ),
  );

  const [seenNonce, setSeenNonce] = useState(focusNonce);
  if (focusNonce !== seenNonce) {
    setSeenNonce(focusNonce);
    if (focusStageId && openMap[focusStageId] === false) {
      setOpenMap((m) => ({ ...m, [focusStageId]: true }));
    }
  }

  useEffect(() => {
    if (!focusStageId) return;
    document.getElementById(focusStageId)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusStageId, focusNonce]);

  return (
    <div className="relative">
      {/* the thread: a dim rail with a teal fill that grows as stages pass */}
      <div
        aria-hidden
        className="absolute bottom-[18px] left-2 top-2 w-[1.5px]"
        style={{ background: "rgba(78,158,150,0.18)" }}
      />
      <motion.div
        aria-hidden
        className="absolute bottom-[18px] left-2 top-2 w-[1.5px] origin-top bg-primary"
        animate={{ scaleY: totalStages ? completedStages / totalStages : 1 }}
        transition={{ duration: 0.4, ease: EASE_OUT }}
      />

      {run.plannerStages.map((stage) => (
        <TraceStage
          key={stage.id}
          stage={stage}
          status={statusOf(stage.id, stage.status)}
          open={!!openMap[stage.id]}
          onToggle={() => setOpenMap((m) => ({ ...m, [stage.id]: !m[stage.id] }))}
        />
      ))}

      <div className="mb-2.5 ml-0.5 mt-4 flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
          Specialists
        </span>
        <span className="h-px flex-1 bg-[rgba(235,230,220,0.08)]" />
      </div>

      {run.lanes.map((lane) => (
        <SpecialistLane key={lane.id} lane={lane} />
      ))}
    </div>
  );
}
