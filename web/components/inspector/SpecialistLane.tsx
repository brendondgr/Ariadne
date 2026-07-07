"use client";

import { useState } from "react";
import { motion } from "motion/react";
import type { SpecialistLane as Lane } from "@/lib/types";
import { ACCENT, CONSOLE_BG, SHADOW } from "@/lib/ui";
import { popIn, staggerContainer } from "@/lib/motion";
import { Pill } from "@/components/ui/Pill";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { MicroStepPill } from "./MicroStepPill";
import { LaneRecordRow } from "./LaneRecordRow";
import { LaneTraceRow } from "./LaneTraceRow";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

const INITIAL_RECORDS = 8;
const RECORDS_PAGE = 8;

/** One source-specific specialist lane. The six canonical micro-step checkpoints
 *  cascade in once the lane's pipeline event activates. Also shows the full
 *  evaluator trace (with retries) and per-specialist task metadata. */
export function SpecialistLane({ lane }: { lane: Lane }) {
  const { statusOf, replaying } = useWorkbench();
  const status = statusOf(lane.id, "pass");
  const active = status !== "pending";
  const [recordsRevealed, setRecordsRevealed] = useState(INITIAL_RECORDS);

  // In-flight lane: the plan routed it but its result hasn't arrived yet.
  if (lane.placeholder) {
    const started = lane.arrival?.startedMs != null;
    const seeds = lane.arrival?.seedCount ?? 0;
    const caption = started
      ? `querying ${lane.backend}…${seeds ? ` (seeded with ${seeds} id(s) from ${lane.arrival?.producer})` : ""}`
      : "queued — waiting to run";
    return (
      <div
        id={lane.id}
        className="mb-3 overflow-hidden rounded-[11px] bg-bg"
        style={{ boxShadow: SHADOW.lightRing }}
      >
        <div
          className="flex items-center gap-[9px] px-[13px] py-[11px]"
          style={{ boxShadow: SHADOW.insetTop }}
        >
          <Pill accent={lane.accent} className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
            {lane.badge}
          </Pill>
          <span className="flex-1 text-[12.5px] font-semibold">{lane.title}</span>
          <motion.span
            className="font-mono text-[11px] text-text-muted"
            animate={started ? { opacity: [1, 0.35, 1] } : undefined}
            transition={{ duration: 1.1, repeat: Infinity }}
          >
            {caption}
          </motion.span>
        </div>
        <div className="flex flex-col gap-2 px-[13px] pb-[13px] pt-1">
          <div className="animate-skel h-3 w-[88%] rounded bg-[rgba(235,230,220,0.08)]" />
          <div className="animate-skel h-3 w-[72%] rounded bg-[rgba(235,230,220,0.08)]" />
          <div className="animate-skel h-3 w-[80%] rounded bg-[rgba(235,230,220,0.08)]" />
        </div>
      </div>
    );
  }

  /** Build a compact task JSON for display. */
  const taskJson = JSON.stringify(
    {
      source: lane.task.source,
      entities: lane.task.entities,
      seed_ids: lane.task.seedIds,
      join_key: lane.task.joinKey,
      limits: JSON.parse(lane.task.limitsJson),
    },
    null,
    2,
  );

  const visibleRecords = lane.records.slice(0, recordsRevealed);
  const remainingRecords = lane.records.length - visibleRecords.length;

  return (
    <div
      id={lane.id}
      className="mb-3 overflow-hidden rounded-[11px] bg-bg"
      style={{ boxShadow: SHADOW.lightRing }}
    >
      <div
        className="flex items-center gap-[9px] px-[13px] py-[11px]"
        style={{ boxShadow: SHADOW.insetTop }}
      >
        <Pill accent={lane.accent} className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
          {lane.badge}
        </Pill>
        <span className="flex-1 text-[12.5px] font-semibold">{lane.title}</span>
        <motion.span
          className="font-mono text-[11px]"
          style={{ color: ACCENT.teal.fg }}
          animate={{ opacity: active ? 1 : 0.25 }}
        >
          {lane.rows} rows · {lane.ms}ms
        </motion.span>
      </div>

      <div className="px-[13px] pb-[13px] pt-2.5">
        {/* Error line */}
        {lane.error && (
          <div
            className="mb-[9px] font-mono text-[10.5px]"
            style={{ color: ACCENT.amber.fg }}
          >
            Error: {lane.error}
          </div>
        )}

        {/* Canonical micro-step pills row (deduped, last-trace wins) */}
        <motion.div
          className="mb-[11px] flex flex-wrap gap-1.5"
          variants={staggerContainer}
          initial="hidden"
          animate={active ? "show" : "hidden"}
        >
          {lane.steps.map((step) => (
            <motion.span key={step.key} variants={popIn}>
              <MicroStepPill step={step} />
            </motion.span>
          ))}
        </motion.div>

        {/* Task metadata */}
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Task
        </div>
        <CodeBlock code={taskJson} lang="json" className="mb-[5px] leading-[1.6]" />
        {lane.task.rationale && (
          <div
            className="mb-[11px] font-mono text-[10.5px] leading-[1.5]"
            style={{ color: "var(--color-text-muted)" }}
          >
            {lane.task.rationale}
          </div>
        )}

        {/* Validated query */}
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Validated query
        </div>
        <CodeBlock code={lane.query} lang={lane.language} emphasis className="mb-[11px] leading-[1.6]" />

        {/* Full evaluator trace (includes retries) */}
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Evaluator trace
        </div>
        <div className="mb-[11px] flex flex-col gap-[5px]">
          {lane.traceEntries.map((entry, i) => (
            <LaneTraceRow key={`${entry.step}-${i}`} entry={entry} />
          ))}
        </div>

        {/* Evidence records — incremental reveal, never silently cap */}
        <div className="mb-1.5 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
          Evidence records ({lane.records.length} total · showing {visibleRecords.length})
          {lane.arrival?.arrivedMs != null && (
            <span className="normal-case tracking-normal">
              {" "}· arrived {lane.arrival.order ? `#${lane.arrival.order} ` : ""}at +
              {(lane.arrival.arrivedMs / 1000).toFixed(1)}s
            </span>
          )}
        </div>
        <motion.div
          className="flex flex-col gap-[5px]"
          variants={staggerContainer}
          initial={replaying ? "hidden" : false}
          animate="show"
        >
          {visibleRecords.map((record) => (
            <motion.div key={record.id} variants={popIn}>
              <LaneRecordRow key={record.id} record={record} language={lane.language} />
            </motion.div>
          ))}
        </motion.div>

        {/* Show-more affordance */}
        {remainingRecords > 0 && (
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={() => setRecordsRevealed((r) => r + RECORDS_PAGE)}
              className="rounded-lg px-3 py-1 font-mono text-[10.5px] text-text-muted hover:text-text"
              style={{ boxShadow: SHADOW.hairline, background: CONSOLE_BG }}
            >
              Show {Math.min(RECORDS_PAGE, remainingRecords)} more
            </button>
            <button
              type="button"
              onClick={() => setRecordsRevealed(lane.records.length)}
              className="font-mono text-[10.5px] text-text-muted hover:text-text"
            >
              Show all ({lane.records.length})
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
