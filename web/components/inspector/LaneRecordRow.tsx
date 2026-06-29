"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { LaneRecord } from "@/lib/types";
import { ACCENT, CONSOLE_BG, SHADOW } from "@/lib/ui";
import { collapse } from "@/lib/motion";
import { CodeBlock } from "@/components/ui/CodeBlock";

/** A compact, expandable normalized evidence record inside a specialist lane. */
export function LaneRecordRow({ record }: { record: LaneRecord }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-[7px]" style={{ background: CONSOLE_BG, boxShadow: SHADOW.hairline }}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex w-full items-center gap-[9px] border-0 bg-transparent px-2.5 py-[7px] text-left font-mono text-[11px]"
      >
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
            <CodeBlock
              code={record.json}
              lang="json"
              className="rounded-t-none text-[10.5px] leading-[1.6]"
              style={{ boxShadow: "none" }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
