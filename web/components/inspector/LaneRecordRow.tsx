"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { CodeLang, LaneRecord } from "@/lib/types";
import { ACCENT, CONSOLE_BG, SHADOW } from "@/lib/ui";
import { collapse } from "@/lib/motion";
import { CodeBlock } from "@/components/ui/CodeBlock";

/** A compact, expandable normalized evidence record inside a specialist lane. */
export function LaneRecordRow({
  record,
  language = "json",
}: {
  record: LaneRecord;
  language?: CodeLang;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-[7px]" style={{ background: CONSOLE_BG, boxShadow: SHADOW.hairline }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-[9px] border-0 bg-transparent px-2.5 py-[7px] text-left font-mono text-[11px]"
      >
        {record.order !== undefined && (
          <span className="w-[26px] shrink-0 text-right text-[9.5px] text-text-muted">
            #{record.order}
          </span>
        )}
        <span style={{ color: ACCENT[record.accent].fg }}>{record.id}</span>
        <span className="flex-1 text-[#c9c6bd]">{record.name}</span>
        <span
          className="text-[9px] text-text-muted transition-transform"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        >
          ▶
        </span>
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div variants={collapse} initial="hidden" animate="show" exit="hidden" className="overflow-hidden">
            <div className="px-2.5 pb-2.5">
              {/* Full record JSON */}
              <CodeBlock
                code={record.fullJson}
                lang="json"
                className="rounded-t-none text-[10.5px] leading-[1.6]"
                style={{ boxShadow: "none" }}
              />

              {/* Provenance query (if present) */}
              {record.query && (
                <>
                  <div className="mb-1 mt-2 font-mono text-[9.5px] uppercase tracking-[0.08em] text-text-muted">
                    query:
                  </div>
                  <CodeBlock
                    code={record.query}
                    lang={language}
                    emphasis
                    className="text-[10.5px] leading-[1.6]"
                  />
                </>
              )}

              {/* Compact provenance line */}
              {record.provenanceMeta && record.provenanceMeta !== "—" && (
                <div className="mt-1.5 font-mono text-[9.5px] text-text-muted">
                  provenance: {record.provenanceMeta}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
