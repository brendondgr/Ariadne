"use client";

import { useEffect, useState } from "react";
import { motion } from "motion/react";
import type { StampedQueryEvent } from "@/lib/types";

/** Pipeline phase → what the analyst-facing status says it's doing, plus a
 *  rough progress fraction so the bar advances through the run. */
const PHASE: Record<string, { label: string; progress: number }> = {
  probing: { label: "Probing the live graphs", progress: 0.15 },
  planning: { label: "Planning the route", progress: 0.35 },
  querying: { label: "Extracting evidence from the graphs", progress: 0.6 },
  answering: { label: "Reasoning over the evidence", progress: 0.85 },
};

function currentPhase(events: StampedQueryEvent[]): string {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type === "status") {
      return (events[i].data as { phase?: string }).phase ?? "probing";
    }
  }
  return "probing";
}

/** Ticking elapsed label ("3.2s") while the stream is live. */
function Elapsed({ since }: { since: number }) {
  const [now, setNow] = useState(() => since);
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(t);
  }, []);
  return <span>{Math.max(0, (now - since) / 1000).toFixed(1)}s</span>;
}

/** Three dots that pulse in sequence — the "still working" affordance. */
function WorkingDots() {
  return (
    <span aria-hidden className="inline-flex gap-[3px]">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="inline-block h-[3px] w-[3px] rounded-full bg-primary"
          animate={{ opacity: [0.25, 1, 0.25] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
        />
      ))}
    </span>
  );
}

/** The live "answering" surface: says what the pipeline is doing at every phase,
 *  with a pulsing indicator + advancing progress bar so it always reads as busy.
 *  Replaces the old static skeleton. */
export function LiveAnswerStatus({
  events,
  createdAt = 0,
}: {
  events: StampedQueryEvent[];
  createdAt?: number;
}) {
  const phase = currentPhase(events);
  const { label, progress } = PHASE[phase] ?? { label: "Working", progress: 0.1 };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2.5">
        <motion.span
          aria-hidden
          className="h-2 w-2 rounded-full bg-primary"
          animate={{ opacity: [1, 0.35, 1], scale: [1, 0.8, 1] }}
          transition={{ duration: 1.1, repeat: Infinity }}
        />
        <span className="text-sm text-text-soft">{label}</span>
        <WorkingDots />
        {createdAt > 0 && (
          <span className="ml-auto font-mono text-[11px] text-text-muted">
            <Elapsed since={createdAt} />
          </span>
        )}
      </div>

      {/* Phase-advancing progress track with a shimmer sweep. */}
      <div className="relative h-1 w-full overflow-hidden rounded-full bg-[rgba(235,230,220,0.08)]">
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full bg-primary/70"
          animate={{ width: `${Math.round(progress * 100)}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        />
        <motion.div
          aria-hidden
          className="absolute inset-y-0 w-1/3 rounded-full"
          style={{ background: "linear-gradient(90deg, transparent, rgba(78,158,150,0.45), transparent)" }}
          animate={{ x: ["-40%", "340%"] }}
          transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
    </div>
  );
}
