"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { LaneTraceEntry } from "@/lib/types";
import { ACCENT, CONSOLE_BG, SHADOW, statusAccent } from "@/lib/ui";
import { collapse } from "@/lib/motion";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { ShieldIcon } from "@/components/ui/icons";

const GLYPH: Record<LaneTraceEntry["status"], string> = {
  pending: "·",
  running: "…",
  pass: "✓",
  partial: "!",
  fail: "✕",
};

/** One evaluator trace entry row — label + status glyph, expandable to show
 *  reasons list and detail JSON. Gate/normalize rows get shield emphasis. */
export function LaneTraceRow({ entry }: { entry: LaneTraceEntry }) {
  const [open, setOpen] = useState(false);
  const accent = ACCENT[statusAccent(entry.status)];
  const hasReasons = entry.reasons.length > 0;
  const hasDetail = entry.detailJson && entry.detailJson !== "{}";
  const expandable = hasReasons || hasDetail;

  return (
    <div className="rounded-[7px]" style={{ background: CONSOLE_BG, boxShadow: SHADOW.hairline }}>
      <button
        type="button"
        onClick={() => expandable && setOpen((o) => !o)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
        className="flex w-full items-center gap-[9px] border-0 bg-transparent px-2.5 py-[7px] text-left font-mono text-[11px] disabled:cursor-default"
      >
        {entry.emphasis && (
          <span style={{ color: accent.fg }}>
            <ShieldIcon size={9} />
          </span>
        )}
        <span
          className="min-w-[80px]"
          style={{ color: entry.emphasis ? accent.fg : "var(--color-text-muted)" }}
        >
          {entry.label}
        </span>
        <span
          className="font-bold"
          style={{ color: accent.fg }}
          title={entry.status}
        >
          {GLYPH[entry.status]}
        </span>
        {hasReasons && (
          <span className="text-[9.5px]" style={{ color: "var(--color-text-muted)" }}>
            {entry.reasons.length} reason{entry.reasons.length !== 1 ? "s" : ""}
          </span>
        )}
        {expandable && (
          <span
            className="ml-auto text-[9px] text-text-muted transition-transform"
            style={{ transform: open ? "rotate(90deg)" : "none" }}
          >
            ▶
          </span>
        )}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            variants={collapse}
            initial="hidden"
            animate="show"
            exit="hidden"
            className="overflow-hidden"
          >
            <div className="px-2.5 pb-2.5">
              {hasReasons && (
                <div className="mb-2">
                  <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.08em] text-text-muted">
                    Reasons
                  </div>
                  <ul className="m-0 list-none p-0">
                    {entry.reasons.map((r, i) => (
                      <li
                        key={i}
                        className="mb-0.5 font-mono text-[10.5px] leading-[1.5]"
                        style={{ color: ACCENT.amber.fg }}
                      >
                        · {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {hasDetail && (
                <>
                  <div className="mb-1 font-mono text-[9px] uppercase tracking-[0.08em] text-text-muted">
                    Detail
                  </div>
                  <CodeBlock
                    code={entry.detailJson}
                    lang="json"
                    emphasis={entry.emphasis}
                    className="text-[10.5px] leading-[1.6]"
                    style={{ boxShadow: "none" }}
                  />
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
