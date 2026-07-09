import { describe, expect, it } from "vitest";
import {
  applyConversationEvent,
  emptyAccumulator,
  evidenceFor,
  runInputsFromAccumulator,
  upsertRunInto,
} from "../runMachine";
import { buildRun } from "../adapt";
import type { QueryEvent, WorkbenchRun } from "../types";

const makeRun = (id: string): WorkbenchRun => buildRun(runInputsFromAccumulator(id, emptyAccumulator("q", "query", "llm")));

describe("applyConversationEvent: quick path", () => {
  it("folds status → context → route → final → conversation → done with no pipeline events", () => {
    const acc = emptyAccumulator("Did we cover T1047 already?", "query", "llm");
    const events: QueryEvent[] = [
      { type: "status", data: { phase: "orchestrating" } },
      { type: "context", data: { resolved_question: "Did we cover T1047 already?", rewritten: false } },
      { type: "route", data: { decision: "quick", reason: "answerable from memory" } },
      {
        type: "final",
        data: {
          final_answer: "Yes, we covered T1047 earlier.",
          route: "quick",
          composer: "llm",
          grounded: false,
        },
      },
      { type: "conversation", data: { conversation_id: "c-1", title: "T1047 recap" } },
      { type: "done", data: { status: "answered", exit_code: 0 } },
    ];

    for (const e of events) applyConversationEvent(acc, e);

    expect(acc.route).toBe("quick");
    expect(acc.reply).toEqual({
      text: "Yes, we covered T1047 earlier.",
      route: "quick",
      composer: "llm",
      grounded: false,
    });
    expect(acc.conversationId).toBe("c-1");
    expect(acc.conversationTitle).toBe("T1047 recap");
    expect(acc.status).toBe("answered");
    expect(acc.exitCode).toBe(0);
    expect(evidenceFor(acc)).toBeNull(); // no pipeline ran

    const run = buildRun(runInputsFromAccumulator("turn-1", acc));
    expect(run.reply?.route).toBe("quick");
    expect(run.federated.results).toHaveLength(0);
  });
});

describe("applyConversationEvent: graph path", () => {
  const PROBE = [
    {
      dataset: "attack",
      backend: "neo4j",
      endpoint: "bolt://localhost:5456",
      live: true,
      node_count: 100,
      observed_labels: ["Technique"],
      reason: "live",
    },
  ];

  const RESULT = {
    task: {
      sub_question_id: "sq-1",
      source: "attack",
      text: "mitigations for T1047",
      entities: ["T1047"],
      limits: { max_traversal_depth: 3, max_result_rows: 1000, query_timeout_ms: 5000 },
      join_key: null,
      seed_ids: [],
      rationale: "resolve WMI",
    },
    query: "MATCH (t) RETURN t",
    records: [
      {
        primary_id: "M1038",
        id_scheme: "attack-id",
        label: "Mitigation",
        name: "Execution Prevention",
        properties: {},
        related: [],
        join_values: ["M1038"],
        provenance: null,
      },
    ],
    record_count: 1,
    summary: "1 mitigation",
    traces: [],
    ok: true,
    partial: false,
    error: null,
    join_values: ["M1038"],
  };

  it("folds the full pipeline event set plus validation + final onto the accumulator", () => {
    const acc = emptyAccumulator("What mitigates T1047?", "query", "llm");
    const events: QueryEvent[] = [
      { type: "status", data: { phase: "orchestrating" } },
      { type: "context", data: { resolved_question: "What mitigates T1047?", rewritten: false } },
      { type: "route", data: { decision: "graph", reason: "requires federated evidence" } },
      { type: "status", data: { phase: "probing" } },
      { type: "probe", data: { live_sources: PROBE } },
      {
        type: "specialist-start",
        data: {
          sub_question: "sq-1",
          source: "attack",
          index: 1,
          total: 1,
          seed_count: 0,
          producer: null,
          skipped: null,
        },
      },
      { type: "specialist", data: { result: RESULT, index: 1, total: 1 } },
      {
        type: "evidence",
        data: {
          evidence: {
            request: "What mitigates T1047?",
            results: [RESULT],
            unsupported: [],
            skipped: [],
            partial: false,
            join_index: {},
            cross_source_join_values: [],
          },
        },
      },
      {
        type: "answer",
        data: {
          headline: "1 record found",
          sections: [
            {
              source: "attack",
              backend: "neo4j",
              ok: true,
              partial: false,
              summary: "1 mitigation",
              record_ids: ["M1038"],
              record_count: 1,
            },
          ],
          cross_source: [],
          unsupported: [],
          status: "answered",
          exit_code: 0,
        },
      },
      {
        type: "validation",
        data: { verdict: "insufficient", reason: "missing citation", missing: ["citation"], iteration: 1 },
      },
      {
        type: "validation",
        data: { verdict: "pass", reason: "resolved on retry", missing: [], iteration: 2 },
      },
      {
        type: "final",
        data: {
          final_answer: "T1047 is mitigated by M1038 (Execution Prevention).",
          route: "graph",
          composer: "llm",
          grounded: true,
        },
      },
      { type: "conversation", data: { conversation_id: "c-2" } },
      { type: "done", data: { status: "answered", exit_code: 0 } },
    ];

    for (const e of events) applyConversationEvent(acc, e);

    expect(acc.route).toBe("graph");
    // The LAST validation event wins (retry semantics).
    expect(acc.validation).toEqual({ verdict: "pass", reason: "resolved on retry", missing: [], iteration: 2 });
    expect(acc.reply?.text).toBe("T1047 is mitigated by M1038 (Execution Prevention).");
    expect(acc.plan).toBeNull(); // no `plan` event on this synthetic quick-ish graph run
    expect(acc.evidence?.results).toHaveLength(1);
    expect(acc.events.map((e) => e.type)).toEqual(events.map((e) => e.type));

    const run = buildRun(runInputsFromAccumulator("turn-2", acc));
    expect(run.reply?.route).toBe("graph");
    expect(run.federated.results).toHaveLength(1);
    expect(run.lanes.map((l) => l.id)).toEqual(["lane-neo4j"]);
  });

  it("stamps receivedMs onto every folded event for the Raw JSON / logs tabs", () => {
    const acc = emptyAccumulator("q", "query", "deterministic");
    applyConversationEvent(acc, { type: "status", data: { phase: "probing" } }, 42);
    applyConversationEvent(acc, { type: "probe", data: { live_sources: PROBE } }, 88);
    expect(acc.events.map((e) => e.receivedMs)).toEqual([42, 88]);
  });

  it("returns a statusPatch effect for status-bearing events and none for silent ones", () => {
    const acc = emptyAccumulator("q", "query", "deterministic");
    const probeEffects = applyConversationEvent(acc, { type: "probe", data: { live_sources: PROBE } });
    expect(probeEffects.statusPatch).toEqual({ probe: "pass", "stage-probe": "pass" });

    const contextEffects = applyConversationEvent(acc, {
      type: "context",
      data: { resolved_question: "q", rewritten: false },
    });
    expect(contextEffects.statusPatch).toBeUndefined();
  });
});

describe("upsertRunInto: per-conversation turn folding (background streams)", () => {
  it("appends a new turn only to its own conversation's list", () => {
    const byConv = { "conv-A": [makeRun("a1")], "conv-B": [makeRun("b1")] };
    const next = upsertRunInto(byConv, "conv-A", makeRun("a2"));

    expect(next["conv-A"].map((r) => r.id)).toEqual(["a1", "a2"]);
    // The other conversation is untouched — the background stream for A never
    // disturbs B even though B is the one on screen.
    expect(next["conv-B"]).toBe(byConv["conv-B"]);
  });

  it("replaces a turn in place by id (progressive rebuild during streaming)", () => {
    const first = makeRun("a1");
    const byConv = { "conv-A": [first] };
    const updated = makeRun("a1");
    const next = upsertRunInto(byConv, "conv-A", updated);

    expect(next["conv-A"]).toHaveLength(1);
    expect(next["conv-A"][0]).toBe(updated);
  });

  it("creates a conversation entry when folding the first turn into an unseen id", () => {
    const next = upsertRunInto({}, "conv-new", makeRun("n1"));
    expect(Object.keys(next)).toEqual(["conv-new"]);
    expect(next["conv-new"].map((r) => r.id)).toEqual(["n1"]);
  });
});
