"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  ConversationalReply,
  ConversationSummaryDTO,
  ExitCode,
  FederatedEvidence,
  LaneArrival,
  Plan,
  ProbeSource,
  QueryEvent,
  RunStatus,
  ServerAnswer,
  SpecialistResult,
  StageStatus,
  StampedQueryEvent,
  ValidationResult,
  WorkbenchRun,
} from "./types";
import { buildRun, type RunInputs } from "./adapt";
import type { QueryRequestBody } from "./api";
import { streamConversation, type ConversationQueryBody } from "./conversations";
import * as conversationsApi from "./conversations";

/**
 * The event-driven, multi-turn run controller. `submit()` appends a NEW turn to
 * the conversation and opens the `/api/conversation-query` SSE stream, advancing
 * `liveStatus` + rebuilding that turn's `WorkbenchRun` as each real event arrives
 * (context → route → [pipeline events] → validation → final → conversation → done)
 * while also retaining the literal ordered event log + raw payloads on the turn.
 * Past turns render statically from their own baked status; only the streaming
 * turn is "live" (`streamingRunId`). `replay()` is the offline demo over the
 * active turn.
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

/** A blank turn used as the active-run fallback for a fresh (empty) conversation. */
export const EMPTY_RUN: WorkbenchRun = buildRun({
  id: "empty",
  question: "",
  mode: "query",
  drafter: "deterministic",
  liveSources: [],
  plan: null,
  evidence: null,
  answer: null,
  status: "idle",
  exitCode: 0,
  elapsedMs: 0,
});

export interface RunMachine {
  /** Every assistant turn in the conversation, oldest first. */
  runs: WorkbenchRun[];
  /** The selected turn the inspector + header reflect. */
  run: WorkbenchRun;
  activeRunId: string;
  /** The turn currently streaming (live animation), or null when idle. */
  streamingRunId: string | null;
  /** True while a demo replay OR a live query is animating. */
  replaying: boolean;
  /** Last stream error, if any. */
  error: string | null;
  liveStatus: Record<string, StageStatus>;
  /** Offline demo: replay the active turn's stages on a timer. */
  replay: () => void;
  /** Run a real question against the backend, appending + streaming a new turn. */
  submit: (req: QueryRequestBody) => void;
  /** Select a turn (drives the inspector + header). */
  selectRun: (id: string) => void;
  /** Cancel an in-flight query / demo. */
  cancel: () => void;
  /** Effective status for a node: live during replay/stream, else the static value. */
  statusOf: (id: string, fallback: StageStatus) => StageStatus;
  completedStages: number;
  totalStages: number;

  /* -- persisted conversation threads (sidebar) -------------------------- */
  /** Persisted threads from the backend, most-recently-updated first. */
  conversations: ConversationSummaryDTO[];
  /** The active persisted thread id ("" when none is active yet). */
  conversationId: string;
  /** True while the thread list is (re)loading. */
  conversationsLoading: boolean;
  /** Re-fetch the thread list from the backend. */
  refreshConversations: () => Promise<void>;
  /** Create a new persisted thread via POST, make it active, clear the turn
   *  list, and refresh the sidebar list. */
  newConversation: () => Promise<void>;
  /** Load a persisted thread's turns and rehydrate them into `runs`. */
  selectConversation: (id: string) => Promise<void>;
  /** Delete a persisted thread; if it was active, reset to a fresh empty state. */
  deleteConversation: (id: string) => Promise<void>;
  /** Rename a persisted thread. */
  renameConversation: (id: string, title: string) => Promise<void>;
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

/**
 * The mutable fold state one conversational turn accumulates as its events
 * arrive — whether that's live SSE frames or a stored turn's replayed
 * `payload.events`. Both `submit()` (live) and `buildRunFromStoredTurn()`
 * (rehydration) fold events through {@link applyConversationEvent} into one of
 * these, then hand it to `buildRun`.
 */
export interface ConversationAccumulator {
  question: string;
  mode: "plan" | "query";
  drafter: "deterministic" | "llm";
  probe: ProbeSource[];
  plan: Plan | null;
  results: SpecialistResult[];
  skipped: Record<string, unknown>[];
  evidence: FederatedEvidence | null;
  answer: ServerAnswer | null;
  status: RunStatus;
  exitCode: ExitCode;
  events: StampedQueryEvent[];
  laneMeta: Record<string, LaneArrival>;
  reply: ConversationalReply | null;
  route: "quick" | "graph" | null;
  validation: ValidationResult | null;
  conversationId: string | null;
  conversationTitle: string | null;
}

/** A fresh accumulator for a new turn. */
export function emptyAccumulator(
  question: string,
  mode: "plan" | "query",
  drafter: "deterministic" | "llm",
): ConversationAccumulator {
  return {
    question,
    mode,
    drafter,
    probe: [],
    plan: null,
    results: [],
    skipped: [],
    evidence: null,
    answer: null,
    status: "running",
    exitCode: 0,
    events: [],
    laneMeta: {},
    reply: null,
    route: null,
    validation: null,
    conversationId: null,
    conversationTitle: null,
  };
}

/** Optional live-only side effects a caller can react to as one event folds in
 *  (status-bar highlighting, staggered reveal timers). Rehydration ignores these. */
export interface ConversationEventEffects {
  /** A `liveStatus` patch to merge (mirrors the mini-stepper node ids). */
  statusPatch?: Record<string, StageStatus>;
  /** Millisecond delay before the given status patch should apply (staggered
   *  planner-stage reveal); the caller is responsible for the actual timer. */
  delayedPatches?: { ms: number; patch: Record<string, StageStatus> }[];
}

/**
 * Fold ONE conversation SSE event into the accumulator, mutating it in place.
 * Shared by live streaming (`submit`, below) and stored-turn rehydration
 * (`buildRunFromStoredTurn` in `rehydrate.ts`) so both paths render identical
 * `WorkbenchRun`s from the same event vocabulary. `receivedMs` stamps the event
 * for the Raw JSON / logs tabs (0 for replayed stored events — they have no
 * live wall-clock).
 *
 * Returns any live-only effects (status-bar patches); rehydration callers can
 * ignore the return value entirely.
 */
export function applyConversationEvent(
  acc: ConversationAccumulator,
  event: QueryEvent,
  receivedMs = 0,
): ConversationEventEffects {
  acc.events.push({ ...event, receivedMs });
  const effects: ConversationEventEffects = {};

  switch (event.type) {
    case "status": {
      const phase = event.data.phase;
      if (phase === "probing") effects.statusPatch = { probe: "running", "stage-probe": "running" };
      else if (phase === "planning") effects.statusPatch = { plan: "running", "stage-draft": "running" };
      else if (phase === "querying") effects.statusPatch = { specialists: "running" };
      else if (phase === "answering") effects.statusPatch = { answer: "running" };
      break;
    }
    case "context":
      // Nothing to fold onto the run today; the resolved question is echoed
      // back on the `route`/`final` events and stored payload directly.
      break;
    case "probe":
      acc.probe = event.data.live_sources;
      effects.statusPatch = { probe: "pass", "stage-probe": "pass" };
      break;
    case "plan":
      acc.plan = event.data.plan;
      effects.statusPatch = { "stage-draft": "pass", "stage-gate": "running" };
      effects.delayedPatches = [
        { ms: 140, patch: { "stage-gate": "pass", "stage-emit": "running" } },
        { ms: 280, patch: { "stage-emit": "pass", plan: "pass" } },
      ];
      break;
    case "route":
      acc.route = event.data.decision;
      break;
    case "specialist-start": {
      const backend = event.data.source === "capec" ? "gremlin" : "neo4j";
      acc.laneMeta[`lane-${backend}`] = {
        subQuestion: event.data.sub_question,
        startedMs: receivedMs,
        arrivedMs: null,
        seedCount: event.data.seed_count,
        producer: event.data.producer,
        order: null,
      };
      if (!event.data.skipped) {
        effects.statusPatch = { specialists: "running", [`lane-${backend}`]: "running" };
      }
      break;
    }
    case "specialist": {
      acc.results.push(event.data.result);
      const backend = backendOf(event.data.result);
      const laneId = `lane-${backend}`;
      const arrivalOrder = acc.results.length;
      const started = acc.laneMeta[laneId];
      acc.laneMeta[laneId] = {
        subQuestion: event.data.result.task.sub_question_id,
        startedMs: started?.startedMs ?? null,
        arrivedMs: receivedMs,
        seedCount: started?.seedCount ?? 0,
        producer: started?.producer ?? null,
        order: arrivalOrder,
      };
      const laneStatus: StageStatus = event.data.result.ok
        ? "pass"
        : event.data.result.partial
          ? "partial"
          : "fail";
      effects.statusPatch = { specialists: "running", [laneId]: laneStatus };
      break;
    }
    case "skipped":
      acc.skipped.push(event.data);
      break;
    case "evidence":
      acc.evidence = event.data.evidence;
      effects.statusPatch = { specialists: "pass", evidence: "pass" };
      break;
    case "answer":
      acc.answer = event.data;
      if (event.data.status) acc.status = event.data.status;
      if (typeof event.data.exit_code === "number") acc.exitCode = event.data.exit_code;
      effects.statusPatch = { answer: "pass" };
      break;
    case "validation":
      acc.validation = event.data;
      break;
    case "final":
      acc.reply = {
        text: event.data.final_answer,
        route: event.data.route,
        composer: event.data.composer,
        grounded: event.data.grounded,
      };
      effects.statusPatch = { answer: "pass" };
      break;
    case "conversation":
      acc.conversationId = event.data.conversation_id;
      acc.conversationTitle = event.data.title ?? acc.conversationTitle;
      break;
    case "done":
      acc.status = event.data.status;
      acc.exitCode = event.data.exit_code;
      effects.statusPatch = {
        answer:
          event.data.status === "answered" ? "pass" : event.data.status === "no_sources" ? "fail" : "partial",
      };
      break;
    case "error":
      acc.status = "partial";
      break;
  }

  return effects;
}

/** Build the evidence bundle to pass to `buildRun` for an accumulator: the real
 *  federated evidence once it has arrived, else an in-progress stand-in while
 *  specialists are still streaming (so lanes render live). */
export function evidenceFor(acc: ConversationAccumulator): FederatedEvidence | null {
  return (
    acc.evidence ??
    (acc.results.length || acc.skipped.length ? inProgressEvidence(acc.question, acc.results, acc.skipped) : null)
  );
}

/** Assemble the `RunInputs` `buildRun` needs from a folded accumulator. */
export function runInputsFromAccumulator(
  id: string,
  acc: ConversationAccumulator,
  extra: { elapsedMs?: number; createdAt?: number } = {},
): RunInputs {
  return {
    id,
    question: acc.question,
    mode: acc.mode,
    drafter: acc.drafter,
    liveSources: acc.probe,
    plan: acc.plan,
    evidence: evidenceFor(acc),
    answer: acc.answer,
    status: acc.status,
    exitCode: acc.exitCode,
    elapsedMs: extra.elapsedMs ?? 0,
    createdAt: extra.createdAt,
    events: [...acc.events],
    laneMeta: { ...acc.laneMeta },
    reply: acc.reply,
    route: acc.route,
    validation: acc.validation,
  };
}

export function useRunMachine(): RunMachine {
  // Start on a clean, empty thread — no seeded demo turns. Real turns arrive
  // via submit(); the empty state is the same one newConversation() produces.
  const [runs, setRuns] = useState<WorkbenchRun[]>([]);
  const [activeRunId, setActiveRunId] = useState<string>("");
  const [streamingRunId, setStreamingRunId] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<Record<string, StageStatus>>({});
  const [replaying, setReplaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [conversations, setConversations] = useState<ConversationSummaryDTO[]>([]);
  const [conversationId, setConversationId] = useState<string>("");
  const [conversationsLoading, setConversationsLoading] = useState(false);

  const timers = useRef<number[]>([]);
  const abort = useRef<AbortController | null>(null);
  const seq = useRef(0);

  // The in-flight stream's fold state (the streaming turn).
  const acc = useRef<ConversationAccumulator>(emptyAccumulator("", "query", "deterministic"));
  const runId = useRef("");
  const startedAt = useRef(0);
  const createdAt = useRef(0);
  const conversationIdRef = useRef("");

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

  /** Insert or replace a turn in `runs` by id (preserving order). */
  const upsertRun = useCallback((built: WorkbenchRun) => {
    setRuns((prev) =>
      prev.some((r) => r.id === built.id)
        ? prev.map((r) => (r.id === built.id ? built : r))
        : [...prev, built],
    );
  }, []);

  /** Rebuild the streaming turn from the current accumulator. */
  const rebuild = useCallback(() => {
    const inputs = runInputsFromAccumulator(runId.current, acc.current, {
      elapsedMs: startedAt.current ? Math.round(performance.now() - startedAt.current) : 0,
      createdAt: createdAt.current,
    });
    upsertRun(buildRun(inputs));
  }, [upsertRun]);

  const cancel = useCallback(() => {
    clearTimers();
    abort.current?.abort();
    abort.current = null;
    setReplaying(false);
    setStreamingRunId(null);
  }, [clearTimers]);

  useEffect(() => cancel, [cancel]);

  const selectRun = useCallback((id: string) => setActiveRunId(id), []);

  const refreshConversations = useCallback(async () => {
    setConversationsLoading(true);
    try {
      const list = await conversationsApi.listConversations();
      setConversations(list);
    } catch {
      // Leave the previous list in place on a transient fetch failure.
    } finally {
      setConversationsLoading(false);
    }
  }, []);

  useEffect(() => {
    // On first mount only — do not auto-load a thread even if some exist.
    let cancelled = false;
    async function loadInitialConversations() {
      setConversationsLoading(true);
      try {
        const list = await conversationsApi.listConversations();
        if (!cancelled) setConversations(list);
      } catch {
        // Leave the (empty) list in place on a transient fetch failure.
      } finally {
        if (!cancelled) setConversationsLoading(false);
      }
    }
    void loadInitialConversations();
    return () => {
      cancelled = true;
    };
  }, []);

  const setActiveConversation = useCallback((id: string) => {
    conversationIdRef.current = id;
    setConversationId(id);
  }, []);

  const newConversation = useCallback(async () => {
    cancel();
    setError(null);
    setLiveStatus({});
    setRuns([]);
    setActiveRunId("");
    const created = await conversationsApi.createConversation();
    setActiveConversation(created.id);
    await refreshConversations();
  }, [cancel, refreshConversations, setActiveConversation]);

  const selectConversation = useCallback(
    async (id: string) => {
      cancel();
      setError(null);
      setLiveStatus({});
      const detail = await conversationsApi.getConversation(id);
      setActiveConversation(detail.id);
      const { buildRunFromStoredTurn } = await import("./rehydrate");
      const rehydrated: WorkbenchRun[] = [];
      const turns = [...detail.turns].sort((a, b) => a.seq - b.seq);
      for (let i = 0; i < turns.length; i += 1) {
        const t = turns[i];
        if (t.role !== "user") continue;
        const next = turns[i + 1];
        const assistantTurn = next && next.role === "assistant" ? next : null;
        rehydrated.push(buildRunFromStoredTurn(t, assistantTurn));
      }
      setRuns(rehydrated);
      setActiveRunId(rehydrated.length ? rehydrated[rehydrated.length - 1].id : "");
    },
    [cancel, setActiveConversation],
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      const wasActive = conversationIdRef.current === id;
      await conversationsApi.deleteConversation(id);
      if (wasActive) {
        cancel();
        setError(null);
        setLiveStatus({});
        setRuns([]);
        setActiveRunId("");
        setActiveConversation("");
      }
      await refreshConversations();
    },
    [cancel, refreshConversations, setActiveConversation],
  );

  const renameConversationThread = useCallback(
    async (id: string, title: string) => {
      await conversationsApi.renameConversation(id, title);
      await refreshConversations();
    },
    [refreshConversations],
  );

  // -- offline demo replay (animates the active turn) ------------------------
  const replay = useCallback(() => {
    cancel();
    setReplaying(true);
    setError(null);
    setLiveStatus({});
    setStreamingRunId(activeRunId);
    for (const frame of REPLAY_FRAMES) {
      pushTimer(() => setLiveStatus((prev) => ({ ...prev, ...frame.set })), frame.at);
    }
    pushTimer(() => {
      setReplaying(false);
      setStreamingRunId(null);
    }, LAST_AT + 250);
  }, [cancel, pushTimer, activeRunId]);

  // -- live query ------------------------------------------------------------
  const submit = useCallback(
    (req: QueryRequestBody) => {
      cancel();
      setError(null);
      setReplaying(true);
      setLiveStatus({});

      seq.current += 1;
      const id = `q-${seq.current}`;
      runId.current = id;
      acc.current = emptyAccumulator(req.question, req.mode, req.drafter);
      startedAt.current = performance.now();
      createdAt.current = Date.now();
      setStreamingRunId(id);
      setActiveRunId(id);
      rebuild(); // append the question + an empty in-progress turn immediately

      const finish = () => {
        pushTimer(() => {
          setReplaying(false);
          setStreamingRunId(null);
        }, 320);
        abort.current = null;
      };

      const ac = new AbortController();
      abort.current = ac;

      const runStream = async () => {
        // A conversation-query turn needs an active thread; create one lazily
        // on the first send if none is active yet.
        let cid = conversationIdRef.current;
        if (!cid) {
          const created = await conversationsApi.createConversation();
          cid = created.id;
          setActiveConversation(cid);
          await refreshConversations();
        }

        const body: ConversationQueryBody = {
          question: req.question,
          conversation_id: cid,
          mode: req.mode,
          drafter: req.drafter,
        };

        await streamConversation(
          body,
          (event) => {
            const receivedMs = Math.round(performance.now() - startedAt.current);
            const effects = applyConversationEvent(acc.current, event, receivedMs);
            if (effects.statusPatch) mergeStatus(effects.statusPatch);
            for (const { ms, patch } of effects.delayedPatches ?? []) {
              pushTimer(() => mergeStatus(patch), ms);
            }
            rebuild();

            if (event.type === "error") {
              setError(event.data.message);
              rebuild();
              finish();
              return;
            }
            if (event.type === "conversation") {
              void refreshConversations();
            }
            if (event.type === "done") {
              void refreshConversations();
              finish();
            }
          },
          ac.signal,
        );
      };

      runStream().catch((e: unknown) => {
        if (ac.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        acc.current.status = "partial";
        rebuild();
        finish();
      });
    },
    [cancel, mergeStatus, pushTimer, rebuild, refreshConversations, setActiveConversation],
  );

  const statusOf = useCallback(
    (id: string, fallback: StageStatus): StageStatus =>
      replaying ? (liveStatus[id] ?? "pending") : fallback,
    [replaying, liveStatus],
  );

  const completedStages = replaying
    ? PLANNER_STAGE_IDS.filter((id) => liveStatus[id] === "pass").length
    : PLANNER_STAGE_IDS.length;

  const run = useMemo(
    () => runs.find((r) => r.id === activeRunId) ?? runs[runs.length - 1] ?? EMPTY_RUN,
    [runs, activeRunId],
  );

  return {
    runs,
    run,
    activeRunId,
    streamingRunId,
    replaying,
    error,
    liveStatus,
    replay,
    submit,
    selectRun,
    cancel,
    statusOf,
    completedStages,
    totalStages: PLANNER_STAGE_IDS.length,
    conversations,
    conversationId,
    conversationsLoading,
    refreshConversations,
    newConversation,
    selectConversation,
    deleteConversation,
    renameConversation: renameConversationThread,
  };
}
