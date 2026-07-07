"use client";

import { Fragment, useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { ExitCode, MiniStep, RunStatus } from "@/lib/types";
import { ACCENT, statusAccent } from "@/lib/ui";
import { dotAnimate, popIn } from "@/lib/motion";
import { CheckIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

const STATUS_CHIP: Record<RunStatus, { label: (e: ExitCode) => string; accent: "teal" | "amber" | "sage" }> = {
  answered: { label: (e) => `Answered · exit ${e}`, accent: "teal" },
  partial: { label: (e) => `Partial · exit ${e}`, accent: "amber" },
  no_sources: { label: (e) => `No sources · exit ${e}`, accent: "sage" },
  running: { label: () => "Running…", accent: "teal" },
  idle: { label: () => "Idle", accent: "sage" },
};

interface MiniStepperProps {
  steps: MiniStep[];
  status: RunStatus;
  exitCode: ExitCode;
  /** True only for the streaming turn; past turns render their baked statuses. */
  live?: boolean;
  /** Current phase message from the latest status event (live turns). */
  phase?: string | null;
  /** Wall-clock submit time — drives the ticking elapsed counter. */
  createdAt?: number;
}

/** Ticking elapsed label ("3.2s") while the stream is live. */
function TickingElapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(t);
  }, []);
  return <span>{Math.max(0, (now - since) / 1000).toFixed(1)}s</span>;
}

/** The Probe › Plan › Specialists › Evidence › Answer header strip. Each dot
 *  animates as the matching pipeline event fires; the outcome chip pops in
 *  once the answer stage completes. */
export function MiniStepper({
  steps,
  status,
  exitCode,
  live = true,
  phase = null,
  createdAt = 0,
}: MiniStepperProps) {
  const { focusStage, statusOf, replaying } = useWorkbench();
  const chip = STATUS_CHIP[status];
  const chipAccent = ACCENT[chip.accent];
  const stepperReplaying = live && replaying;
  const showChip = !stepperReplaying || statusOf("answer", "pass") === "pass";

  return (
    <div
      className="flex items-center gap-0 bg-[rgba(27,33,34,0.6)] px-4 py-3"
      style={{ boxShadow: "rgba(235,230,220,0.07) 0 -1px 0 0 inset" }}
    >
      <div className="flex flex-1 flex-wrap items-center gap-2">
        {steps.map((step, idx) => {
          const isLast = idx === steps.length - 1;
          const effective = live ? statusOf(step.key, step.status) : step.status;
          const color = isLast && effective === "pass" ? "var(--color-text)" : ACCENT[statusAccent(effective)].fg;
          return (
            <Fragment key={step.key}>
              <button
                type="button"
                onClick={() => step.target && focusStage(step.target)}
                className="flex cursor-pointer items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[10.5px] uppercase tracking-[0.05em] transition-opacity hover:opacity-80"
                style={{ color }}
              >
                <motion.span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  animate={dotAnimate(effective)}
                />
                {step.label}
              </button>
              {!isLast && <span className="text-[10px] text-text-muted">›</span>}
            </Fragment>
          );
        })}
      </div>
      <AnimatePresence mode="wait">
        {!showChip && (
          <motion.span
            key={phase ?? "working"}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-1.5 font-mono text-[10.5px] text-text-muted"
          >
            <motion.span
              aria-hidden
              className="h-1.5 w-1.5 rounded-full"
              style={{ background: ACCENT.teal.fg }}
              animate={{ opacity: [1, 0.35, 1], scale: [1, 0.82, 1] }}
              transition={{ duration: 1.1, repeat: Infinity }}
            />
            {phase ?? "working…"}
            {createdAt > 0 && (
              <span className="text-text-soft">
                · <TickingElapsed since={createdAt} />
              </span>
            )}
          </motion.span>
        )}
        {showChip && (
          <motion.span
            variants={popIn}
            initial="hidden"
            animate="show"
            exit="hidden"
            className="flex items-center gap-1.5 rounded-full px-2.5 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.05em]"
            style={{ color: chipAccent.fg, background: chipAccent.tintBg }}
          >
            {status === "answered" && <CheckIcon />}
            {chip.label(exitCode)}
          </motion.span>
        )}
      </AnimatePresence>
    </div>
  );
}
