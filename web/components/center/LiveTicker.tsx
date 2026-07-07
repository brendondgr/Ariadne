"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { StampedQueryEvent } from "@/lib/types";
import { tickerLines } from "@/lib/ticker";
import { EASE_OUT } from "@/lib/motion";

const ACCENT_TEXT: Record<string, string> = {
  teal: "text-primary",
  amber: "text-secondary",
  sage: "text-text-muted",
};

/**
 * Terminal-style narration of the live pipeline: one line per SSE event with
 * its elapsed time, appended the instant the event arrives. While streaming it
 * renders as a live console with a breathing caret; once the run finishes it
 * collapses to a one-line "activity log" disclosure so the record of what
 * happened stays a click away.
 */
export function LiveTicker({
  events,
  streaming,
}: {
  events: StampedQueryEvent[];
  streaming: boolean;
}) {
  const lines = tickerLines(events);
  const [open, setOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();

  // Keep the newest line in view while streaming.
  useEffect(() => {
    if (streaming && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streaming, lines.length]);

  if (lines.length === 0) return null;

  const total = lines[lines.length - 1]?.time ?? "";

  if (!streaming && !open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="mb-2 inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[10.5px] text-text-muted transition-colors hover:text-text"
      >
        <span aria-hidden>▸</span>
        activity log ({lines.length} events{total ? ` · ${total}` : ""})
      </button>
    );
  }

  return (
    <div className="mb-2.5 rounded-[9px] bg-bg/60 px-3 py-2.5" style={{ boxShadow: "rgba(235, 230, 220, 0.08) 0px 0px 0px 1px" }}>
      {!streaming && (
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="mb-1.5 inline-flex items-center gap-1.5 border-0 bg-transparent p-0 font-mono text-[10.5px] text-text-muted transition-colors hover:text-text"
        >
          <span aria-hidden>▾</span>
          activity log ({lines.length} events{total ? ` · ${total}` : ""})
        </button>
      )}
      <div
        ref={scrollRef}
        className="flex max-h-[168px] flex-col gap-[3px] overflow-y-auto font-mono text-[11px] leading-[1.5]"
        role="log"
        aria-live={streaming ? "polite" : "off"}
        aria-label="Pipeline activity"
      >
        <AnimatePresence initial={false}>
          {lines.map((line) => (
            <motion.div
              key={line.key}
              initial={reduceMotion ? false : { opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.22, ease: EASE_OUT }}
              className="flex items-baseline gap-2"
            >
              <span className="w-[34px] shrink-0 text-right text-[10px] text-text-muted">
                {line.time}
              </span>
              <span className={ACCENT_TEXT[line.accent] ?? "text-text-soft"}>{line.text}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {streaming && (
          <div className="flex items-baseline gap-2">
            <span className="w-[34px] shrink-0" />
            <motion.span
              aria-hidden
              className="text-primary"
              animate={reduceMotion ? undefined : { opacity: [1, 0.25, 1] }}
              transition={{ duration: 1.1, repeat: Infinity }}
            >
              ▮
            </motion.span>
          </div>
        )}
      </div>
    </div>
  );
}
