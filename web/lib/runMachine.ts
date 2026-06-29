"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { StageStatus } from "./types";

/**
 * A tiny event-driven run-state machine. `replay()` emits a timed sequence of
 * status transitions across the pipeline nodes — the same shape a live
 * streaming backend would dispatch (`stage_started` / `stage_result`). The UI
 * animates off these status changes, so swapping the timer for a real event
 * source needs no component changes.
 */

export interface RunFrame {
  at: number;
  set: Record<string, StageStatus>;
}

/** Planner-stage node ids that count toward the progress meter. */
export const PLANNER_STAGE_IDS = ["stage-probe", "stage-draft", "stage-gate", "stage-emit"];

export const REPLAY_FRAMES: RunFrame[] = [
  { at: 0, set: { probe: "running", "stage-probe": "running" } },
  { at: 450, set: { "stage-probe": "pass", probe: "pass", plan: "running", "stage-draft": "running" } },
  { at: 900, set: { "stage-draft": "pass", "stage-gate": "running" } },
  { at: 1250, set: { "stage-gate": "pass", "stage-emit": "running" } },
  {
    at: 1600,
    set: {
      "stage-emit": "pass",
      plan: "pass",
      specialists: "running",
      "lane-neo4j": "running",
      "lane-gremlin": "running",
    },
  },
  {
    at: 2150,
    set: { "lane-neo4j": "pass", "lane-gremlin": "pass", specialists: "pass", evidence: "running" },
  },
  { at: 2500, set: { evidence: "pass", answer: "running" } },
  { at: 2800, set: { answer: "pass" } },
];

const LAST_AT = REPLAY_FRAMES[REPLAY_FRAMES.length - 1].at;

export interface RunMachine {
  replaying: boolean;
  liveStatus: Record<string, StageStatus>;
  replay: () => void;
  /** Effective status for a node: live during replay, otherwise the static value. */
  statusOf: (id: string, fallback: StageStatus) => StageStatus;
  completedStages: number;
  totalStages: number;
}

export function useRunMachine(): RunMachine {
  const [liveStatus, setLiveStatus] = useState<Record<string, StageStatus>>({});
  const [replaying, setReplaying] = useState(false);
  const timers = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const replay = useCallback(() => {
    clearTimers();
    setReplaying(true);
    setLiveStatus({});
    for (const frame of REPLAY_FRAMES) {
      timers.current.push(
        window.setTimeout(() => setLiveStatus((prev) => ({ ...prev, ...frame.set })), frame.at),
      );
    }
    timers.current.push(window.setTimeout(() => setReplaying(false), LAST_AT + 250));
  }, [clearTimers]);

  const statusOf = useCallback(
    (id: string, fallback: StageStatus): StageStatus =>
      replaying ? (liveStatus[id] ?? "pending") : fallback,
    [replaying, liveStatus],
  );

  const completedStages = replaying
    ? PLANNER_STAGE_IDS.filter((id) => liveStatus[id] === "pass").length
    : PLANNER_STAGE_IDS.length;

  return {
    replaying,
    liveStatus,
    replay,
    statusOf,
    completedStages,
    totalStages: PLANNER_STAGE_IDS.length,
  };
}
