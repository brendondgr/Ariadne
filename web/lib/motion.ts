import type { Variants } from "motion/react";
import type { StageStatus } from "./types";
import { ACCENT, statusAccent } from "./ui";

/** Shared Motion variants. Centralized so every part animates off the same
 *  vocabulary — and off pipeline *events* (status changes), which is exactly
 *  the seam a live SSE stream plugs into later. */

export const EASE_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** Fade + small slide-up for items entering the screen. */
export const fadeSlideUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.34, ease: EASE_OUT } },
};

/** Container that staggers its children's `fadeSlideUp` / `popIn`. */
export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05, delayChildren: 0.04 } },
};

/** Pop/scale-in for chips, pills, and status chips. */
export const popIn: Variants = {
  hidden: { opacity: 0, scale: 0.82 },
  show: { opacity: 1, scale: 1, transition: { duration: 0.26, ease: EASE_OUT } },
};

/** Height auto-collapse for expandable code/record bodies. */
export const collapse: Variants = {
  hidden: { height: 0, opacity: 0 },
  show: { height: "auto", opacity: 1, transition: { duration: 0.24, ease: EASE_OUT } },
};

/** Cross-fade used when switching inspector tabs. */
export const tabFade: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.2, ease: EASE_OUT } },
  exit: { opacity: 0, y: -6, transition: { duration: 0.12 } },
};

/**
 * The animation target for a status dot/marker, keyed by pipeline status.
 * `running` breathes (the event in flight); `pass`/`fail` settle.
 */
export function dotAnimate(status: StageStatus) {
  const color = ACCENT[statusAccent(status)].fg;
  if (status === "running") {
    return {
      backgroundColor: color,
      scale: [1, 0.82, 1],
      transition: { scale: { duration: 1.1, repeat: Infinity, ease: "easeInOut" } },
    };
  }
  if (status === "pending") {
    return { backgroundColor: ACCENT.sage.fg, scale: 0.85, opacity: 0.6 };
  }
  return {
    backgroundColor: color,
    scale: 1,
    opacity: 1,
    transition: { type: "spring" as const, stiffness: 520, damping: 18 },
  };
}
