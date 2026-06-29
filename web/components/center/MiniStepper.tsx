"use client";

import { Fragment } from "react";
import type { ExitCode, MiniStep, RunStatus } from "@/lib/types";
import { ACCENT, statusAccent } from "@/lib/ui";
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
}

/** The Probe › Plan › Specialists › Evidence › Answer header strip on the
 *  Answer Card. Each segment jumps the inspector to its stage. */
export function MiniStepper({ steps, status, exitCode }: MiniStepperProps) {
  const { focusStage } = useWorkbench();
  const chip = STATUS_CHIP[status];
  const chipAccent = ACCENT[chip.accent];

  return (
    <div
      className="flex items-center gap-0 bg-[rgba(27,33,34,0.6)] px-4 py-3"
      style={{ boxShadow: "rgba(235,230,220,0.07) 0 -1px 0 0 inset" }}
    >
      <div className="flex flex-1 flex-wrap items-center gap-2">
        {steps.map((step, idx) => {
          const isLast = idx === steps.length - 1;
          const color = isLast ? "var(--color-text)" : ACCENT[statusAccent(step.status)].fg;
          return (
            <Fragment key={step.key}>
              <button
                type="button"
                onClick={() => step.target && focusStage(step.target)}
                className="flex cursor-pointer items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[10.5px] uppercase tracking-[0.05em] transition-opacity hover:opacity-80"
                style={{ color }}
              >
                <span
                  aria-hidden
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: ACCENT[statusAccent(step.status)].fg }}
                />
                {step.label}
              </button>
              {!isLast && <span className="text-[10px] text-text-muted">›</span>}
            </Fragment>
          );
        })}
      </div>
      <span
        className="flex items-center gap-1.5 rounded-full px-2.5 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.05em]"
        style={{ color: chipAccent.fg, background: chipAccent.tintBg }}
      >
        {status === "answered" && <CheckIcon />}
        {chip.label(exitCode)}
      </span>
    </div>
  );
}
