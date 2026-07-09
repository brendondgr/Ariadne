"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { WorkbenchRun } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { collapse } from "@/lib/motion";
import { ThreadHeader } from "./ThreadHeader";
import { UserMessage } from "./UserMessage";
import { ReplyMessage } from "./ReplyMessage";
import { AnswerCard } from "./AnswerCard";
import { Composer } from "./Composer";

/** A graph-path turn has grounded content worth showing beneath the reply
 *  bubble once it has evidence or an answer payload; a quick-path turn (or one
 *  still probing/planning with nothing back yet) has none. */
function hasGroundedContent(run: WorkbenchRun): boolean {
  if (run.reply && run.reply.route === "quick") return false;
  return run.federated.results.length > 0 || run.answer.paragraphs.length > 0 || run.rawAnswer !== null;
}

interface ChatThreadProps {
  title: string;
  /** Every turn in the conversation, oldest first. */
  runs: WorkbenchRun[];
  /** The selected turn (drives the title strip + inspector elsewhere). */
  activeRun: WorkbenchRun;
  activeRunId: string;
  /** The turn currently streaming, or null when idle. */
  streamingRunId: string | null;
  onSelectRun: (id: string) => void;
}

/** A question + its assistant reply. Clicking anywhere selects the turn so the
 *  inspector follows it. Only the streaming turn animates (`live`).
 *
 *  Render order: the user's question bubble, then the conversational REPLY
 *  bubble (`run.reply.text`) as the primary assistant message, then — only for
 *  graph-path turns with grounded content — the existing tabbed `AnswerCard`
 *  beneath it, collapsed by default so the reply stays the focal point. A
 *  turn with no `reply` yet (mid-stream, or a pre-conversational fixture) just
 *  shows the grounded card, matching the previous behavior. */
function TurnBlock({
  run,
  active,
  live,
  onSelect,
}: {
  run: WorkbenchRun;
  active: boolean;
  live: boolean;
  onSelect: () => void;
}) {
  const [cardOpen, setCardOpen] = useState(false);
  const grounded = hasGroundedContent(run);

  return (
    <div
      onClick={onSelect}
      className={`flex cursor-pointer flex-col gap-[22px] rounded-[16px] p-2 transition-colors ${
        active ? "bg-[rgba(78,158,150,0.05)]" : "hover:bg-[rgba(235,230,220,0.02)]"
      }`}
    >
      <UserMessage text={run.question} />
      {run.reply ? (
        // Reply bubble + (optional) evidence card as ONE continuous container:
        // the wrapper owns the surface + shadow, the reply is the head section,
        // and the expanded evidence extends seamlessly beneath it (a hairline
        // seam, no gap) instead of floating as a separate standalone card.
        <div
          className="max-w-[92%] overflow-hidden rounded-[4px_13px_13px_13px] bg-surface"
          style={{ boxShadow: SHADOW.answerCard }}
        >
          <ReplyMessage
            run={run}
            live={live}
            hasGroundedCard={grounded}
            cardOpen={cardOpen}
            onToggleCard={() => setCardOpen((v) => !v)}
            docked
          />
          <AnimatePresence initial={false}>
            {grounded && cardOpen && (
              <motion.div
                key="grounded-card"
                variants={collapse}
                initial="hidden"
                animate="show"
                exit="hidden"
                className="overflow-hidden"
                style={{ boxShadow: SHADOW.insetTop }}
              >
                <AnswerCard run={run} live={live} docked />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      ) : (
        <AnswerCard run={run} live={live} />
      )}
    </div>
  );
}

function EmptyThread() {
  return (
    <div className="flex flex-1 items-center justify-center">
      <p className="max-w-sm text-center font-mono text-[12px] leading-relaxed text-text-muted">
        Ask a question below to route it across the live graphs and watch the
        evidence-backed pipeline run end to end.
      </p>
    </div>
  );
}

/** The center conversation pane: title strip, scrolling multi-turn list, and the
 *  docked composer. */
export function ChatThread({
  title,
  runs,
  activeRun,
  activeRunId,
  streamingRunId,
  onSelectRun,
}: ChatThreadProps) {
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ThreadHeader title={title} run={activeRun} runs={runs} />
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-[14px] pb-2 pt-6">
        {runs.length === 0 ? (
          <EmptyThread />
        ) : (
          runs.map((r) => (
            <TurnBlock
              key={r.id}
              run={r}
              active={r.id === activeRunId}
              live={r.id === streamingRunId}
              onSelect={() => onSelectRun(r.id)}
            />
          ))
        )}
      </div>
      <Composer />
    </div>
  );
}
