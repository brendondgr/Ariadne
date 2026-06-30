"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ExitCode,
  FederatedEvidence,
  Plan,
  ProbeSource,
  RunStatus,
  ServerAnswer,
  SpecialistResult,
  StageStatus,
  WorkbenchRun,
} from "./types";
import { buildRun, type RunInputs } from "./adapt";
import { streamQuery, type QueryRequestBody } from "./api";
import { initialRun } from "./fixtures";

/**
 * The event-driven run controller. `submit()` opens the `/api/query` SSE stream
 * and advances `liveStatus` + rebuilds the `WorkbenchRun` as each real event
 * arrives (probe → plan → per-specialist → evidence → answer → done). The UI
 * animates off `statusOf`, so the same status transitions a live backend emits
 * drive the choreography. `replay()` is the offline demo: a timed sweep over the
 * current run's stages, used by the Run/Replay controls when no query is live.
 */

export interface RunFrame {
  at: number;
  set: Record<string, StageStatus>;
}

/** Planner-stage node ids that count toward the progress meter. */
export const PLANNER_STAGE_IDS = ["stage-probe", "stage-draft", "stage-gate", "stage-emit"];

/** Offline demo timeline (also the shape the live stream reproduces). */
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
  /** The current assistant turn the UI renders. */
  run: WorkbenchRun;
  /** True while a demo replay OR a live query is animating. */
  replaying: boolean;
  /** Last stream error, if any. */
  error: string | null;
  liveStatus: Record<string, StageStatus>;
  /** Offline demo: replay the current run's stages on a timer. */
  replay: () => void;
  /** Run a real question against the backend, streaming the result. */
  submit: (req: QueryRequestBody) => void;
  /** Cancel an in-flight query / demo. */
  cancel: () => void;
  /** Effective status for a node: live during replay/stream, else the static value. */
  statusOf: (id: string, fallback: StageStatus) => StageStatus;
  completedStages: number;
  totalStages: number;
}

function backendOf(result: SpecialistResult): "neo4j" | "gremlin" {
  const prov = result.records.find((r) => r.provenance)?.provenance;
  if (prov?.backend === "neo4j" || prov?.backend === "gremlin") return prov.backend;
  return result.task.source === "capec" ? "gremlin" : "neo4j";
}

/** Evidence stand-in while specialists are still streaming (lanes appear live). */
function inProgressEvidence(
  request: string,
  results: SpecialistResult[],
  skipped: Record<string, unknown>[],
): FederatedEvidence {
  return {
    request,
    results,
    unsupported: [],
    skipped,
    partial: true,
    join_index: {},
    cross_source_join_values: [],
  };
}

export function useRunMachine(): RunMachine {
  const [run, setRun] = useState<WorkbenchRun>(initialRun);
  const [liveStatus, setLiveStatus] = useState<Record<string, StageStatus>>({});
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const timers = useRef<number[]>([]);
  const abort = useRef<AbortController | null>(null);
  const seq = useRef(0);

  // Accumulators for the in-flight stream.
  const meta = useRef({ id: "turn-1", question: "", mode: "query" as "plan" | "query", drafter: "deterministic" as "deterministic" | "llm" });
  const probe = useRef<ProbeSource[]>([]);
  const plan = useRef<Plan | null>(null);
  const results = useRef<SpecialistResult[]>([]);
  const skipped = useRef<Record<string, unknown>[]>([]);
  const evidence = useRef<FederatedEvidence | null>(null);
  const answer = useRef<ServerAnswer | null>(null);
  const status = useRef<RunStatus>("running");
  const exitCode = useRef<ExitCode>(0);
  const startedAt = useRef(0);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  }, []);

  const pushTimer = useCallback((fn: () => void, at: number) => {
    timers.current.push(window.setTimeout(fn, at));
  }, []);

  const mergeStatus = useCallback((patch: Record<string, StageStatus>) => {
    setLiveStatus((prev) => ({ ...prev, ...patch }));
  }, []);

  const rebuild = useCallback(() => {
    const ev =
      evidence.current ??
      (results.current.length || skipped.current.length
        ? inProgressEvidence(meta.current.question, results.current, skipped.current)
        : null);
    const inputs: RunInputs = {
      id: meta.current.id,
      question: meta.current.question,
      mode: meta.current.mode,
      drafter: meta.current.drafter,
      liveSources: probe.current,
      plan: plan.current,
      evidence: ev,
      answer: answer.current,
      status: status.current,
      exitCode: exitCode.current,
      elapsedMs: startedAt.current ? Math.round(performance.now() - startedAt.current) : 0,
    };
    setRun(buildRun(inputs));
  }, []);

  const cancel = useCallback(() => {
    clearTimers();
    abort.current?.abort();
    abort.current = null;
    setReplaying(false);
  }, [clearTimers]);

  useEffect(() => cancel, [cancel]);

  // -- offline demo replay ---------------------------------------------------
  const replay = useCallback(() => {
    cancel();
    setReplaying(true);
    setError(null);
    setLiveStatus({});
    for (const frame of REPLAY_FRAMES) {
      pushTimer(() => setLiveStatus((prev) => ({ ...prev, ...frame.set })), frame.at);
    }
    pushTimer(() => setReplaying(false), LAST_AT + 250);
  }, [cancel, pushTimer]);

  // -- live query ------------------------------------------------------------
  const submit = useCallback(
    (req: QueryRequestBody) => {
      cancel();
      setError(null);
      setReplaying(true);
      setLiveStatus({});

      seq.current += 1;
      meta.current = {
        id: `turn-${seq.current}`,
        question: req.question,
        mode: req.mode,
        drafter: req.drafter,
      };
      probe.current = [];
      plan.current = null;
      results.current = [];
      skipped.current = [];
      evidence.current = null;
      answer.current = null;
      status.current = "running";
      exitCode.current = 0;
      startedAt.current = performance.now();
      rebuild(); // show the question + an empty in-progress turn immediately

      const finish = () => {
        pushTimer(() => setReplaying(false), 320);
        abort.current = null;
      };

      const ac = new AbortController();
      abort.current = ac;

      void streamQuery(
        req,
        (event) => {
          switch (event.type) {
            case "status": {
              const phase = event.data.phase;
              if (phase === "probing") mergeStatus({ probe: "running", "stage-probe": "running" });
              else if (phase === "planning") mergeStatus({ plan: "running", "stage-draft": "running" });
              else if (phase === "querying") mergeStatus({ specialists: "running" });
              else if (phase === "answering") mergeStatus({ answer: "running" });
              break;
            }
            case "probe":
              probe.current = event.data.live_sources;
              mergeStatus({ probe: "pass", "stage-probe": "pass" });
              rebuild();
              break;
            case "plan":
              plan.current = event.data.plan;
              // Reveal the planner sub-stages with a short stagger off one event.
              mergeStatus({ "stage-draft": "pass", "stage-gate": "running" });
              pushTimer(() => mergeStatus({ "stage-gate": "pass", "stage-emit": "running" }), 140);
              pushTimer(() => mergeStatus({ "stage-emit": "pass", plan: "pass" }), 280);
              rebuild();
              break;
            case "specialist": {
              results.current = [...results.current, event.data.result];
              const backend = backendOf(event.data.result);
              const laneStatus: StageStatus = event.data.result.ok
                ? "pass"
                : event.data.result.partial
                  ? "partial"
                  : "fail";
              mergeStatus({ specialists: "running", [`lane-${backend}`]: laneStatus });
              rebuild();
              break;
            }
            case "skipped":
              skipped.current = [...skipped.current, event.data];
              rebuild();
              break;
            case "evidence":
              evidence.current = event.data.evidence;
              mergeStatus({ specialists: "pass", evidence: "pass" });
              rebuild();
              break;
            case "answer":
              answer.current = event.data;
              if (event.data.status) status.current = event.data.status;
              if (typeof event.data.exit_code === "number") exitCode.current = event.data.exit_code;
              mergeStatus({ answer: "pass" });
              rebuild();
              break;
            case "done":
              status.current = event.data.status;
              exitCode.current = event.data.exit_code;
              mergeStatus({
                answer:
                  event.data.status === "answered"
                    ? "pass"
                    : event.data.status === "no_sources"
                      ? "fail"
                      : "partial",
              });
              rebuild();
              finish();
              break;
            case "error":
              setError(event.data.message);
              status.current = "partial";
              rebuild();
              finish();
              break;
          }
        },
        ac.signal,
      ).catch((e: unknown) => {
        if (ac.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        status.current = "partial";
        rebuild();
        finish();
      });
    },
    [cancel, mergeStatus, pushTimer, rebuild],
  );

  const statusOf = useCallback(
    (id: string, fallback: StageStatus): StageStatus =>
      replaying ? (liveStatus[id] ?? "pending") : fallback,
    [replaying, liveStatus],
  );

  const completedStages = replaying
    ? PLANNER_STAGE_IDS.filter((id) => liveStatus[id] === "pass").length
    : PLANNER_STAGE_IDS.length;

  return {
    run,
    replaying,
    error,
    liveStatus,
    replay,
    submit,
    cancel,
    statusOf,
    completedStages,
    totalStages: PLANNER_STAGE_IDS.length,
  };
}
