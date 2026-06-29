"use client";

import { useEffect, useState } from "react";
import type { WorkbenchRun } from "@/lib/types";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { TraceStage } from "./TraceStage";
import { SpecialistLane } from "./SpecialistLane";

/** Ordered planner timeline + specialist lanes. Owns planner-stage expansion
 *  and reacts to cross-panel focus requests. */
export function TraceTab({ run }: { run: WorkbenchRun }) {
  const { focusStageId, focusNonce } = useWorkbench();
  const [openMap, setOpenMap] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(
      run.plannerStages.map((s) => [s.id, s.id === "stage-probe" || s.id === "stage-gate"]),
    ),
  );

  // Adjust state during render when a new focus request arrives (the
  // React-recommended alternative to setting state in an effect).
  const [seenNonce, setSeenNonce] = useState(focusNonce);
  if (focusNonce !== seenNonce) {
    setSeenNonce(focusNonce);
    if (focusStageId && openMap[focusStageId] === false) {
      setOpenMap((m) => ({ ...m, [focusStageId]: true }));
    }
  }

  // The scroll itself is a genuine DOM side-effect.
  useEffect(() => {
    if (!focusStageId) return;
    document.getElementById(focusStageId)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focusStageId, focusNonce]);

  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute bottom-[18px] left-2 top-2 w-[1.5px]"
        style={{ background: "rgba(78,158,150,0.3)" }}
      />

      {run.plannerStages.map((stage) => (
        <TraceStage
          key={stage.id}
          stage={stage}
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
