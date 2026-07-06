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
      {/* planner timeline — the rail is bounded to the planner stages so it does
          not trail down into the Specialists section past the last stage */}
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
      </div>

      <div className="mb-2.5 ml-0.5 mt-4 flex items-center gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
          Specialists
        </span>
        <span className="h-px flex-1 bg-[rgba(235,230,220,0.08)]" />
      </div>

      {run.lanes.map((lane) => (
        <SpecialistLane key={lane.id} lane={lane} />
      ))}

      {/* Skipped & unsupported — only rendered when there is data */}
      {(run.federated.skipped.length > 0 || run.federated.unsupported.length > 0) && (
        <div className="mt-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
              Skipped &amp; unsupported
            </span>
            <span className="h-px flex-1 bg-[rgba(235,230,220,0.08)]" />
          </div>

          {run.federated.skipped.length > 0 && (
            <div className="mb-3">
              <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.08em] text-text-muted">
                Skipped sub-questions
              </div>
              <div className="flex flex-col gap-[4px]">
                {run.federated.skipped.map((item, i) => {
                  const source = typeof item["source"] === "string" ? item["source"] : "";
                  const reason = typeof item["reason"] === "string" ? item["reason"] : JSON.stringify(item);
                  const subQ = typeof item["sub_question"] === "string" ? item["sub_question"] : "";
                  return (
                    <div
                      key={i}
                      className="rounded-[6px] px-2.5 py-[6px] font-mono text-[10.5px]"
                      style={{ background: "rgba(201,146,74,0.07)", color: "var(--color-text-muted)" }}
                    >
                      {source && (
                        <span style={{ color: "rgba(201,146,74,0.85)" }} className="mr-1.5">
                          {source}
                        </span>
                      )}
                      {subQ && <span className="mr-1.5 text-[#c9c6bd]">{subQ}</span>}
                      <span>· {reason}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {run.federated.unsupported.length > 0 && (
            <div>
              <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.08em] text-text-muted">
                Unsupported parts
              </div>
              <div className="flex flex-col gap-[4px]">
                {run.federated.unsupported.map((item, i) => (
                  <div
                    key={i}
                    className="rounded-[6px] px-2.5 py-[6px] font-mono text-[10.5px]"
                    style={{ background: "rgba(201,146,74,0.07)", color: "var(--color-text-muted)" }}
                  >
                    <span className="mr-1.5 text-[#c9c6bd]">{item.description}</span>
                    <span>· {item.reason}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
