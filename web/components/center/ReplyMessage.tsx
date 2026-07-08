"use client";

import { useState } from "react";
import { motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { fadeSlideUp } from "@/lib/motion";
import { Pill } from "@/components/ui/Pill";
import { ChevronRight } from "@/components/ui/icons";
import { RefText } from "./RefText";

/** Small route indicator: "Answered from memory" (quick path, no graph
 *  extraction ran) vs "Queried the graphs" (the federated pipeline ran). */
function RouteIndicator({ route }: { route: "quick" | "graph" }) {
  return (
    <Pill accent={route === "graph" ? "teal" : "sage"} className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]">
      {route === "graph" ? "Queried the graphs" : "Answered from memory"}
    </Pill>
  );
}

/** A validation-retry indicator: only rendered when the answer required at
 *  least one insufficiency retry (iteration > 1) or hit the retry cap. */
function ValidationIndicator({
  validation,
}: {
  validation: NonNullable<WorkbenchRun["validation"]>;
}) {
  if (validation.verdict === "pass" && validation.iteration <= 1) return null;
  const label = validation.capped
    ? `Validation capped after ${validation.iteration} attempt${validation.iteration === 1 ? "" : "s"}`
    : validation.verdict === "pass"
      ? `Passed validation after ${validation.iteration} attempt${validation.iteration === 1 ? "" : "s"}`
      : `Retrying — ${validation.reason || "insufficient evidence"}`;
  return (
    <Pill accent="amber" className="px-2 py-0.5 text-[9.5px] tracking-[0.06em]" title={validation.reason}>
      {label}
    </Pill>
  );
}

/**
 * The primary assistant message: the conversational reply prose (from the
 * `final` event / stored `payload.final_answer`). This is the trust-neutral
 * conversational surface — the grounded `AnswerCard` (rendered by the caller
 * beneath this, collapsible) remains the actual trust surface for graph-path
 * turns; this bubble never introduces claims the grounded card doesn't back.
 */
export function ReplyMessage({
  run,
  live,
  hasGroundedCard,
  cardOpen,
  onToggleCard,
}: {
  run: WorkbenchRun;
  live: boolean;
  hasGroundedCard: boolean;
  cardOpen: boolean;
  onToggleCard: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const reply = run.reply;
  if (!reply) return null;

  const copyReply = async () => {
    try {
      await navigator.clipboard?.writeText(reply.text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      // Clipboard blocked — leave state as-is.
    }
  };

  return (
    <motion.div
      variants={fadeSlideUp}
      initial={live ? "hidden" : false}
      animate="show"
      className="max-w-[92%] overflow-hidden rounded-[4px_13px_13px_13px] bg-surface px-[18px] py-4"
      style={{ boxShadow: SHADOW.answerCard }}
    >
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <RouteIndicator route={reply.route} />
        {run.validation && <ValidationIndicator validation={run.validation} />}
      </div>

      <p className="m-0 text-sm leading-[1.62] text-text-soft">
        <RefText text={reply.text} />
      </p>

      <div
        className="mt-3 flex items-center gap-3.5 pt-3"
        style={{ boxShadow: SHADOW.insetTop }}
      >
        <button
          type="button"
          onClick={copyReply}
          aria-live="polite"
          className="inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[11.5px] text-text-muted transition-colors hover:text-text"
        >
          {copied ? "Copied" : "Copy reply"}
        </button>
        {hasGroundedCard && (
          <button
            type="button"
            onClick={onToggleCard}
            aria-expanded={cardOpen}
            className="inline-flex items-center gap-1 border-0 bg-transparent p-0 font-mono text-[11.5px] text-primary"
          >
            <motion.span
              className="flex"
              animate={{ rotate: cardOpen ? 90 : 0 }}
              transition={{ duration: 0.18 }}
            >
              <ChevronRight size={11} />
            </motion.span>
            {cardOpen ? "Hide evidence & sources" : "Show evidence & sources"}
          </button>
        )}
      </div>
    </motion.div>
  );
}
