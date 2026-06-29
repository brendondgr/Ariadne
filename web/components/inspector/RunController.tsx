"use client";

import { motion } from "motion/react";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { PlayIcon } from "@/components/ui/icons";

/** Replays the trace as a timed sequence of pipeline events — the same status
 *  transitions a live streaming backend would emit — so the whole UI animates
 *  on events, not on load. */
export function RunController() {
  const { replay, replaying } = useWorkbench();
  return (
    <button
      type="button"
      onClick={replay}
      disabled={replaying}
      title="Replay the pipeline as live events"
      className="flex items-center gap-1.5 rounded-md border-0 bg-transparent px-2 py-1 font-mono text-[10.5px] uppercase tracking-[0.05em] text-text-muted shadow-border transition-colors hover:text-primary disabled:opacity-60"
    >
      <motion.span
        animate={replaying ? { rotate: 360 } : { rotate: 0 }}
        transition={replaying ? { duration: 1, repeat: Infinity, ease: "linear" } : { duration: 0 }}
        className="flex"
      >
        <PlayIcon size={10} />
      </motion.span>
      {replaying ? "Running" : "Replay"}
    </button>
  );
}
