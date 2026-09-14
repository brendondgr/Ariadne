"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  Assessment,
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
  { at: 350, set: { "stage-probe": "pass", probe: "pass", classify: "running" } },
  { at: 600, set: { classify: "pass", plan: "running", "stage-draft": "running" } },
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
  /** The turn currently streaming (live animation) in the ACTIVE conversation,
   *  or null when the active conversation is idle. Background conversations may
   *  still be streaming — see `busyConversationIds`. */
  streamingRunId: string | null;
  /** Every conversation id with an in-flight background query. Drives the
   *  sidebar "swirl" indicator; a query stays here across chat switches. */
  busyConversationIds: Set<string>;
  /** True while a demo replay OR a live query is animating in the ACTIVE
   *  conversation (a background query in another chat does not make this true). */
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
  /** Latest iterative-retrieval verdict and how many hops the run took (1 = single pass). */
  assessment: Assessment | null;
  hop: number;
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
    assessment: null,
    hop: 1,
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
      else if (phase === "classifying") effects.statusPatch = { classify: "running" };
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
      // The plan carries the classified intent, so classify is done here.
      effects.statusPatch = { classify: "pass", "stage-draft": "pass", "stage-gate": "running" };
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
    case "assess":
      // Iterative-retrieval verdict: record the latest assessment and hop so
      // the UI can show how many retrieval passes the run took.
      acc.assessment = event.data.assessment;
      acc.hop = event.data.hop;
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

/** Upsert a built run into a per-conversation runs map (pure). Inserting or
 *  replacing a turn for `cid` never touches any OTHER conversation's list — this
 *  is what lets a background stream keep folding into its own conversation while
 *  a different one is on screen. */
export function upsertRunInto(
  byConversation: Record<string, WorkbenchRun[]>,
  cid: string,
  built: WorkbenchRun,
): Record<string, WorkbenchRun[]> {
  const list = byConversation[cid] ?? [];
  const next = list.some((r) => r.id === built.id)
    ? list.map((r) => (r.id === built.id ? built : r))
    : [...list, built];
  return { ...byConversation, [cid]: next };
}

/** One conversation's in-flight stream. Held in a ref-map keyed by conversation
 *  id so switching the active chat never cancels or loses another chat's query. */
interface StreamState {
  acc: ConversationAccumulator;
  runId: string;
  startedAt: number;
  createdAt: number;
  abort: AbortController;
  timers: number[];
}

/** Stable empty status map so an idle conversation's `liveStatus` keeps a
 *  constant identity across renders. */
const EMPTY_STATUS: Record<string, StageStatus> = {};

export function useRunMachine(): RunMachine {
  // Per-conversation state. `runsByConversation` is the source of truth for
  // EVERY conversation's turns (active or streaming in the background); the
  // active conversation's list is derived below. Keying streams + live status by
  // conversation id is what lets a query keep running after the analyst switches
  // chats — nothing is cancelled or replaced on switch.
  const [runsByConversation, setRunsByConversation] = useState<Record<string, WorkbenchRun[]>>({});
  const [liveStatusByConversation, setLiveStatusByConversation] = useState<
    Record<string, Record<string, StageStatus>>
  >({});
  const [streamingByConversation, setStreamingByConversation] = useState<Record<string, string>>({});
  const [busyIds, setBusyIds] = useState<string[]>([]);
  const [activeRunId, setActiveRunId] = useState<string>("");
  const [demoReplaying, setDemoReplaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [conversations, setConversations] = useState<ConversationSummaryDTO[]>([]);
  const [conversationId, setConversationId] = useState<string>("");
  const [conversationsLoading, setConversationsLoading] = useState(false);

  const seq = useRef(0);
  const conversationIdRef = useRef("");
  const demoTimers = useRef<number[]>([]);
  // Every in-flight stream, keyed by conversation id. Survives chat switches.
  const streams = useRef<Map<string, StreamState>>(new Map());

  // Tear down every stream on unmount (not on conversation switch).
  useEffect(
    () => () => {
      streams.current.forEach((st) => {
        st.abort.abort();
        st.timers.forEach((t) => clearTimeout(t));
      });
      streams.current.clear();
      demoTimers.current.forEach((t) => clearTimeout(t));
    },
    [],
  );

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

  /** Detach + clean up a conversation's stream registry entry (does NOT abort;
   *  the caller decides whether to abort the underlying request first). */
  const forgetStream = useCallback((cid: string) => {
    streams.current.delete(cid);
    setBusyIds((b) => b.filter((x) => x !== cid));
    setStreamingByConversation((m) => {
      if (!(cid in m)) return m;
      const next = { ...m };
      delete next[cid];
      return next;
    });
  }, []);

  /** Abort a conversation's in-flight stream (if any) and forget it. */
  const abortStream = useCallback(
    (cid: string) => {
      const st = streams.current.get(cid);
      if (!st) return;
      st.abort.abort();
      st.timers.forEach((t) => clearTimeout(t));
      forgetStream(cid);
    },
    [forgetStream],
  );

  /** Open a background stream for `cid`. Its events fold into that conversation's
   *  own runs/liveStatus regardless of which chat is on screen. */
  const startStream = useCallback(
    (cid: string, req: QueryRequestBody) => {
      // One active turn per conversation — supersede any prior in-flight turn.
      const prev = streams.current.get(cid);
      if (prev) {
        prev.abort.abort();
        prev.timers.forEach((t) => clearTimeout(t));
      }

      seq.current += 1;
      const id = `q-${seq.current}`;
      const st: StreamState = {
        acc: emptyAccumulator(req.question, req.mode, req.drafter),
        runId: id,
        startedAt: performance.now(),
        createdAt: Date.now(),
        abort: new AbortController(),
        timers: [],
      };
      streams.current.set(cid, st);
      setBusyIds((b) => (b.includes(cid) ? b : [...b, cid]));
      setStreamingByConversation((m) => ({ ...m, [cid]: id }));
      setLiveStatusByConversation((m) => ({ ...m, [cid]: {} }));

      const rebuild = () => {
        const inputs = runInputsFromAccumulator(id, st.acc, {
          elapsedMs: Math.round(performance.now() - st.startedAt),
          createdAt: st.createdAt,
        });
        setRunsByConversation((m) => upsertRunInto(m, cid, buildRun(inputs)));
      };
      const mergeStatus = (patch: Record<string, StageStatus>) => {
        setLiveStatusByConversation((m) => ({ ...m, [cid]: { ...(m[cid] ?? {}), ...patch } }));
      };
      const pushTimer = (fn: () => void, at: number) => {
        st.timers.push(window.setTimeout(fn, at));
      };

      // Select the new turn if this conversation is the one on screen.
      if (conversationIdRef.current === cid) setActiveRunId(id);
      rebuild(); // append the question + an empty in-progress turn immediately

      const runStream = async () => {
        const body: ConversationQueryBody = {
          question: req.question,
          conversation_id: cid,
          mode: req.mode,
          drafter: req.drafter,
          // Assembled field by field rather than spread, so anything added to
          // QueryRequestBody and NOT added here is silently dropped and the
          // control becomes a no-op on screen.
          verify: req.verify,
          narrate: req.narrate,
          thinking_budget: req.thinking_budget,
        };
        await streamConversation(
          body,
          (event) => {
            const receivedMs = Math.round(performance.now() - st.startedAt);
            const effects = applyConversationEvent(st.acc, event, receivedMs);
            if (effects.statusPatch) mergeStatus(effects.statusPatch);
            for (const { ms, patch } of effects.delayedPatches ?? []) {
              pushTimer(() => mergeStatus(patch), ms);
            }
            rebuild();

            if (event.type === "error") {
              setError(event.data.message);
              rebuild();
              forgetStream(cid);
              return;
            }
            if (event.type === "conversation") {
              void refreshConversations();
            }
            if (event.type === "done") {
              void refreshConversations();
              forgetStream(cid);
            }
          },
          st.abort.signal,
        );
      };

      runStream().catch((e: unknown) => {
        // A user cancel / chat delete aborts st.abort — swallow those. Anything
        // else is a real failure: a network drop, a backend exception, or an
        // `SseStallError` from the inactivity watchdog (which deliberately does
        // NOT abort the signal, so a silent hang surfaces here as a visible
        // error instead of an endless "Composing the answer" spinner).
        if (st.abort.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        st.acc.status = "partial";
        rebuild();
        forgetStream(cid);
      });
    },
    [forgetStream, refreshConversations],
  );

  const newConversation = useCallback(async () => {
    // Do NOT cancel other conversations' streams — they keep running in the bg.
    setError(null);
    const created = await conversationsApi.createConversation();
    setActiveConversation(created.id);
    setRunsByConversation((m) => (m[created.id] ? m : { ...m, [created.id]: [] }));
    setActiveRunId("");
    await refreshConversations();
  }, [refreshConversations, setActiveConversation]);

  const selectConversation = useCallback(
    async (id: string) => {
      // Switching chats never cancels a stream. If the target is streaming in the
      // background, keep its live in-memory turns (a re-fetch would clobber the
      // in-flight turn); just bring it on screen and follow its streaming turn.
      setError(null);
      setActiveConversation(id);
      const streaming = streams.current.get(id);
      if (streaming) {
        setActiveRunId(streaming.runId);
        return;
      }
      // Otherwise rehydrate from the backend (canonical for completed threads).
      const detail = await conversationsApi.getConversation(id);
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
      setRunsByConversation((m) => ({ ...m, [id]: rehydrated }));
      setActiveRunId(rehydrated.length ? rehydrated[rehydrated.length - 1].id : "");
    },
    [setActiveConversation],
  );

  const deleteConversation = useCallback(
    async (id: string) => {
      const wasActive = conversationIdRef.current === id;
      abortStream(id); // a deleted thread's stream is moot
      await conversationsApi.deleteConversation(id);
      setRunsByConversation((m) => {
        if (!(id in m)) return m;
        const next = { ...m };
        delete next[id];
        return next;
      });
      setLiveStatusByConversation((m) => {
        if (!(id in m)) return m;
        const next = { ...m };
        delete next[id];
        return next;
      });
      if (wasActive) {
        setError(null);
        setActiveConversation("");
        setActiveRunId("");
      }
      await refreshConversations();
    },
    [abortStream, refreshConversations, setActiveConversation],
  );

  const renameConversationThread = useCallback(
    async (id: string, title: string) => {
      await conversationsApi.renameConversation(id, title);
      await refreshConversations();
    },
    [refreshConversations],
  );

  const cancel = useCallback(() => {
    // Cancel the ACTIVE conversation's stream + any demo replay.
    demoTimers.current.forEach((t) => clearTimeout(t));
    demoTimers.current = [];
    setDemoReplaying(false);
    abortStream(conversationIdRef.current);
  }, [abortStream]);

  // -- derived active-conversation view --------------------------------------
  const runs = useMemo(
    () => runsByConversation[conversationId] ?? [],
    [runsByConversation, conversationId],
  );
  const liveStatus = liveStatusByConversation[conversationId] ?? EMPTY_STATUS;
  const streamingRunId = streamingByConversation[conversationId] ?? null;
  const activeBusy = busyIds.includes(conversationId);
  const replaying = demoReplaying || activeBusy;
  const busyConversationIds = useMemo(() => new Set(busyIds), [busyIds]);

  // -- offline demo replay (animates the active turn) ------------------------
  const replay = useCallback(() => {
    const cid = conversationIdRef.current;
    demoTimers.current.forEach((t) => clearTimeout(t));
    demoTimers.current = [];
    abortStream(cid);
    setDemoReplaying(true);
    setError(null);
    setLiveStatusByConversation((m) => ({ ...m, [cid]: {} }));
    setStreamingByConversation((m) => ({ ...m, [cid]: activeRunId }));
    for (const frame of REPLAY_FRAMES) {
      demoTimers.current.push(
        window.setTimeout(
          () =>
            setLiveStatusByConversation((m) => ({ ...m, [cid]: { ...(m[cid] ?? {}), ...frame.set } })),
          frame.at,
        ),
      );
    }
    demoTimers.current.push(
      window.setTimeout(() => {
        setDemoReplaying(false);
        setStreamingByConversation((m) => {
          if (!(cid in m)) return m;
          const next = { ...m };
          delete next[cid];
          return next;
        });
      }, LAST_AT + 250),
    );
  }, [abortStream, activeRunId]);

  // -- live query ------------------------------------------------------------
  const submit = useCallback(
    (req: QueryRequestBody) => {
      setError(null);
      const go = async () => {
        // A conversation-query turn needs an active thread; create one lazily on
        // the first send if none is active yet.
        let cid = conversationIdRef.current;
        let createdNew = false;
        if (!cid) {
          const created = await conversationsApi.createConversation();
          cid = created.id;
          createdNew = true;
          setActiveConversation(cid);
        }
        startStream(cid, req);
        if (createdNew) await refreshConversations();
      };
      go().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    },
    [refreshConversations, setActiveConversation, startStream],
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
    busyConversationIds,
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
