import { describe, expect, it } from "vitest";
import { buildRunFromStoredTurn } from "../rehydrate";
import type {
  AssistantPayload,
  FederatedEvidence,
  Plan,
  ProbeSource,
  ServerAnswer,
  StoredTurn,
} from "../types";

const PROBE: ProbeSource[] = [
  {
    dataset: "attack",
    backend: "neo4j",
    endpoint: "bolt://localhost:5456",
    live: true,
    node_count: 2611,
    observed_labels: ["Technique"],
    reason: "live",
  },
];

const FED: FederatedEvidence = {
  request: "What mitigates T1047?",
  results: [
    {
      task: {
        sub_question_id: "sq-1",
        source: "attack",
        text: "mitigations for T1047",
        entities: ["T1047"],
        limits: { max_traversal_depth: 3, max_result_rows: 1000, query_timeout_ms: 5000 },
        join_key: null,
        seed_ids: [],
        rationale: "resolve WMI to T1047",
      },
      query: "MATCH (t:Technique {external_id:'T1047'})-[:MITIGATED_BY]->(m) RETURN m",
      records: [
        {
          primary_id: "M1038",
          id_scheme: "attack-id",
          label: "Mitigation",
          name: "Execution Prevention",
          properties: {},
          related: [],
          join_values: ["M1038"],
          provenance: {
            source: "MITRE ATT&CK Enterprise",
            dataset: "attack",
            backend: "neo4j",
            query: "MATCH (t:Technique {external_id:'T1047'})-[:MITIGATED_BY]->(m) RETURN m",
            record_id: "mitigation--M1038",
            timestamp: "2026-07-08T10:00:00+00:00",
          },
        },
      ],
      record_count: 1,
      summary: "1 mitigation found",
      traces: [],
      ok: true,
      partial: false,
      error: null,
      join_values: ["M1038"],
    },
  ],
  unsupported: [],
  skipped: [],
  partial: false,
  join_index: {},
  cross_source_join_values: [],
};

const PLAN: Plan = {
  request: FED.request,
  sub_questions: FED.results.map((r) => ({
    id: r.task.sub_question_id,
    source: r.task.source,
    text: r.task.text,
    entities: r.task.entities,
    limits: r.task.limits,
    join_key: r.task.join_key,
    rationale: r.task.rationale,
  })),
  joins: [],
  unsupported: [],
  assumptions: [],
  rationale: "route to attack",
  partial: false,
  trace: [{ iteration: 1, drafter: "DeterministicDrafter", gate_ok: true, reasons: [], sub_questions: 1, unsupported: 0 }],
};

function serverAnswer(): ServerAnswer {
  return {
    headline: "Gathered 1 record(s) from 1 source(s).",
    sections: [
      {
        source: "attack",
        backend: "neo4j",
        ok: true,
        partial: false,
        summary: "1 mitigation found",
        record_ids: ["M1038"],
        record_count: 1,
      },
    ],
    cross_source: [],
    unsupported: [],
    status: "answered",
    exit_code: 0,
  };
}

function graphTurnPayload(): AssistantPayload {
  return {
    final_answer: "ATT&CK lists mitigation M1038 (Execution Prevention) for T1047 (WMI).",
    route: "graph",
    route_reason: "requires federated evidence",
    resolved_question: "What mitigates T1047 (WMI)?",
    validation: { verdict: "pass", reason: "sufficient evidence", missing: [], iteration: 1 },
    facts: ["T1047 is mitigated by M1038"],
    status: "answered",
    exit_code: 0,
    events: [
      { type: "probe", data: { live_sources: PROBE } },
      { type: "plan", data: { plan: PLAN, target_sources: ["attack"] } },
      {
        type: "specialist",
        data: { result: FED.results[0], index: 1, total: 1 },
      },
      { type: "evidence", data: { evidence: FED } },
      { type: "answer", data: serverAnswer() },
      {
        type: "validation",
        data: { verdict: "pass", reason: "sufficient evidence", missing: [], iteration: 1 },
      },
      {
        type: "final",
        data: {
          final_answer: "ATT&CK lists mitigation M1038 (Execution Prevention) for T1047 (WMI).",
          route: "graph",
          composer: "llm",
          grounded: true,
        },
      },
      { type: "done", data: { status: "answered", exit_code: 0 } },
    ],
  };
}

function quickTurnPayload(): AssistantPayload {
  return {
    final_answer: "Yes — we discussed T1047 (WMI execution) earlier in this thread.",
    route: "quick",
    route_reason: "answerable from conversation memory",
    resolved_question: "Did we already cover WMI execution?",
    validation: null,
    facts: [],
    status: "answered",
    exit_code: 0,
    events: [
      {
        type: "final",
        data: {
          final_answer: "Yes — we discussed T1047 (WMI execution) earlier in this thread.",
          route: "quick",
          composer: "llm",
          grounded: false,
        },
      },
      { type: "done", data: { status: "answered", exit_code: 0 } },
    ],
  };
}

function userTurn(question: string, id = "turn-user-1"): StoredTurn {
  return {
    id,
    conversation_id: "c-1",
    seq: 0,
    role: "user",
    created_at: "2026-07-08T10:00:00+00:00",
    question,
    payload: null,
    mode: "query",
    drafter: "llm",
    route: null,
  };
}

function assistantTurn(payload: AssistantPayload, id = "turn-assistant-1"): StoredTurn {
  return {
    id,
    conversation_id: "c-1",
    seq: 1,
    role: "assistant",
    created_at: "2026-07-08T10:00:05+00:00",
    question: payload.resolved_question,
    payload,
    mode: "query",
    drafter: "llm",
    route: payload.route,
  };
}

describe("buildRunFromStoredTurn: graph-path turn", () => {
  const run = buildRunFromStoredTurn(userTurn("What mitigates T1047 (WMI)?"), assistantTurn(graphTurnPayload()));

  it("carries the conversational reply text from payload.final_answer", () => {
    expect(run.reply).not.toBeNull();
    expect(run.reply!.text).toBe(graphTurnPayload().final_answer);
    expect(run.reply!.route).toBe("graph");
    expect(run.reply!.grounded).toBe(true);
  });

  it("replays the answer event into the grounded card fields (evidence + answer paragraphs)", () => {
    expect(run.federated.results).toHaveLength(1);
    expect(run.federated.results[0].records[0].primary_id).toBe("M1038");
    expect(run.answer.paragraphs.length).toBeGreaterThan(0);
    expect(run.lanes.map((l) => l.id)).toEqual(["lane-neo4j"]);
  });

  it("carries route + validation onto the run for the UI indicators", () => {
    expect(run.route).toBe("graph");
    expect(run.validation).toEqual({ verdict: "pass", reason: "sufficient evidence", missing: [], iteration: 1 });
  });

  it("uses the user turn's question as the run's question and a valid createdAt", () => {
    expect(run.question).toBe("What mitigates T1047 (WMI)?");
    expect(run.createdAt).toBeGreaterThan(0);
    expect(run.status).toBe("answered");
    expect(run.exitCode).toBe(0);
  });
});

describe("buildRunFromStoredTurn: quick-path turn", () => {
  const run = buildRunFromStoredTurn(
    userTurn("Did we already cover WMI execution?", "turn-user-2"),
    assistantTurn(quickTurnPayload(), "turn-assistant-2"),
  );

  it("has a reply but no grounded evidence (quick path never ran the pipeline)", () => {
    expect(run.reply).not.toBeNull();
    expect(run.reply!.route).toBe("quick");
    expect(run.reply!.grounded).toBe(false);
    expect(run.federated.results).toHaveLength(0);
    expect(run.lanes).toHaveLength(0);
  });
});

describe("buildRunFromStoredTurn: defensive fallback with no assistant turn", () => {
  it("still returns a run (idle status, no reply) instead of throwing", () => {
    const run = buildRunFromStoredTurn(userTurn("orphaned question", "turn-user-3"), null);
    expect(run.question).toBe("orphaned question");
    expect(run.reply).toBeNull();
    expect(run.status).toBe("idle");
  });
});
