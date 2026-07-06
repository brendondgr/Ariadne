import { describe, expect, it } from "vitest";
import { buildLiveSources, buildRun, buildSynthesis, type RunInputs } from "../adapt";
import { wmiCapecRun } from "../fixtures";
import type {
  FederatedEvidence,
  Plan,
  ProbeSource,
  ServerAnswer,
  ServerSynthesis,
  SpecialistStep,
} from "../types";

const EXPECTED_STEPS: SpecialistStep[] = [
  "intake",
  "resolve",
  "gate",
  "execute",
  "assess",
  "normalize",
];

const FED: FederatedEvidence = wmiCapecRun.federated;

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
  {
    dataset: "capec",
    backend: "gremlin",
    endpoint: "ws://localhost:6455/gremlin",
    live: true,
    node_count: 4888,
    observed_labels: ["AttackPattern"],
    reason: "live",
  },
];

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
  joins: [{ key: "external_id", sources: ["attack", "capec"], on: "external_id" }],
  unsupported: [],
  assumptions: ["WMI == T1047 alias"],
  rationale: "Route ATT&CK to neo4j and CAPEC to gremlin; join on external_id.",
  partial: false,
  trace: [
    { iteration: 1, drafter: "DeterministicDrafter", gate_ok: true, reasons: [], sub_questions: 2, unsupported: 0 },
  ],
};

/** Reconstruct the server `answer` payload the backend would emit for FED. */
function serverAnswer(): ServerAnswer {
  const jindex = FED.join_index;
  return {
    headline: "Gathered 4 record(s) from 2 source(s); 2 cross-source correlation(s).",
    sections: FED.results.map((r) => ({
      source: r.task.source,
      backend: r.records[0]?.provenance?.backend ?? r.task.source,
      ok: r.ok,
      partial: r.partial,
      summary: r.summary,
      record_ids: r.records.map((rec) => rec.primary_id),
      record_count: r.record_count,
    })),
    cross_source: FED.cross_source_join_values.map((value) => ({ value, entries: jindex[value] ?? [] })),
    unsupported: [],
    status: "answered",
    exit_code: 0,
  };
}

function wmiInputs(): RunInputs {
  return {
    id: "turn-live-1",
    question: FED.request,
    mode: "query",
    drafter: "deterministic",
    liveSources: PROBE,
    plan: PLAN,
    evidence: FED,
    answer: serverAnswer(),
    status: "answered",
    exitCode: 0,
    elapsedMs: 412,
  };
}

describe("buildRun adapter", () => {
  const run = buildRun(wmiInputs());

  it("produces an answered run (exit 0) carrying the raw federated bundle", () => {
    expect(run.status).toBe("answered");
    expect(run.exitCode).toBe(0);
    expect(run.federated).toEqual(FED); // Raw JSON tab gets the untouched to_dict.
  });

  it("maps both probed backends to live sources with node counts", () => {
    expect(run.liveSources).toHaveLength(2);
    expect(run.liveSources.every((s) => s.status === "live")).toBe(true);
    expect(run.liveSources.map((s) => s.nodes)).toEqual([2611, 4888]);
  });

  it("emits the four planner stages with the gate shielded", () => {
    expect(run.plannerStages.map((s) => s.id)).toEqual([
      "stage-probe",
      "stage-draft",
      "stage-gate",
      "stage-emit",
    ]);
    expect(run.plannerStages.find((s) => s.id === "stage-gate")?.shield).toBe(true);
    expect(run.plannerStages.find((s) => s.id === "stage-probe")?.status).toBe("pass");
  });

  it("builds one lane per source with all six canonical micro-steps and the right accent", () => {
    expect(run.lanes.map((l) => l.id)).toEqual(["lane-neo4j", "lane-gremlin"]);
    const [neo, grem] = run.lanes;
    expect(neo.accent).toBe("teal");
    expect(grem.accent).toBe("amber");
    for (const lane of run.lanes) {
      expect(lane.steps.map((s) => s.key)).toEqual(EXPECTED_STEPS);
      expect(lane.steps.filter((s) => s.emphasis).map((s) => s.key)).toEqual(["gate", "normalize"]);
      expect(lane.steps.every((s) => s.status === "pass")).toBe(true);
    }
    expect(neo.records.map((r) => r.id)).toEqual(["T1047", "T1546.003"]);
    expect(grem.records.map((r) => r.id)).toEqual(["CAPEC-549", "CAPEC-563"]);
    expect(neo.rows).toBe(2);
  });

  it("flattens four evidence rows with source-coded accents", () => {
    expect(run.evidence).toHaveLength(4);
    expect(new Set(run.evidence.map((e) => e.id))).toEqual(
      new Set(["T1047", "T1546.003", "CAPEC-549", "CAPEC-563"]),
    );
    const t1047 = run.evidence.find((e) => e.id === "T1047")!;
    expect(t1047.accent).toBe("teal");
    expect(t1047.meta).toContain("join_values");
  });

  it("derives two join candidates (CAPEC↔ATT&CK) keyed on external_id", () => {
    expect(run.joinKey).toBe("external_id");
    expect(run.joinIndex).toHaveLength(2);
    for (const cand of run.joinIndex) {
      expect(cand.matchedOn).toBe("external_id");
      expect(cand.left.startsWith("CAPEC-")).toBe(true);
      expect(cand.leftAccent).toBe("amber");
      expect(cand.right.startsWith("T")).toBe(true);
      expect(cand.rightAccent).toBe("teal");
    }
  });

  it("composes an answer with cross-source join pairs and provenance chips", () => {
    expect(run.answer.paragraphs.length).toBeGreaterThan(0);
    expect(run.answer.joinPairs).toHaveLength(2);
    const hasChip = run.answer.paragraphs.some((p) => p.segments.some((s) => s.kind === "chip"));
    expect(hasChip).toBe(true);
  });

  it("each lane has traceEntries, task.entities populated, and includes a normalize entry", () => {
    for (const lane of run.lanes) {
      expect(lane.traceEntries.length).toBeGreaterThanOrEqual(1);
      expect(lane.traceEntries.some((e) => e.step === "normalize")).toBe(true);
      expect(lane.task.entities.length).toBeGreaterThan(0);
    }
  });

  it("buildPlannerStages gate stage code includes the full iteration trace", () => {
    const gateStage = run.plannerStages.find((s) => s.id === "stage-gate");
    expect(gateStage).toBeDefined();
    expect(gateStage!.code).toContain("iteration");
  });
});

describe("buildRun incremental / partial states", () => {
  it("handles a plan-only (in-progress) run with no evidence yet", () => {
    const run = buildRun({
      id: "turn-progress",
      question: FED.request,
      mode: "query",
      drafter: "deterministic",
      liveSources: PROBE,
      plan: PLAN,
      evidence: null,
      answer: null,
      status: "running",
      exitCode: 0,
      elapsedMs: 0,
    });
    expect(run.plannerStages).toHaveLength(4);
    expect(run.lanes).toHaveLength(0);
    expect(run.evidence).toHaveLength(0);
    expect(run.answer.paragraphs).toHaveLength(0);
    // An empty-but-valid bundle keeps the Raw JSON tab happy.
    expect(run.federated.results).toHaveLength(0);
  });

  it("retains the raw payloads + ordered event log for the Raw JSON tab", () => {
    const events: import("../types").QueryEvent[] = [
      { type: "probe", data: { live_sources: PROBE } },
      { type: "plan", data: { plan: PLAN, target_sources: ["attack", "capec"] } },
      { type: "evidence", data: { evidence: FED } },
      { type: "done", data: { status: "answered", exit_code: 0 } },
    ];
    const run = buildRun({ ...wmiInputs(), createdAt: 1234, events });
    expect(run.createdAt).toBe(1234);
    expect(run.rawPlan).toEqual(PLAN);
    expect(run.rawProbe).toEqual(PROBE);
    expect(run.rawAnswer?.status).toBe("answered");
    expect(run.events.map((e) => e.type)).toEqual(["probe", "plan", "evidence", "done"]);
  });

  it("defaults raw fields when no events/createdAt are supplied", () => {
    const run = buildRun(wmiInputs());
    expect(run.createdAt).toBe(0);
    expect(run.events).toEqual([]);
    expect(run.rawProbe).toEqual(PROBE); // probe always mirrors the liveSources input
  });

  it("marks a down backend as down with a reason", () => {
    const sources = buildLiveSources([
      { ...PROBE[0], live: false, node_count: 0, reason: "no TCP connection to 127.0.0.1:5456" },
      PROBE[1],
    ]);
    expect(sources[0].status).toBe("down");
    expect(sources[0].reason).toContain("no TCP connection");
    expect(sources[1].status).toBe("live");
  });
});

describe("Phase 3: no-cap evidence rows and full provenance fields", () => {
  it("builds 250 evidence rows with no cap from a 250-record result", () => {
    const syntheticRecords = Array.from({ length: 250 }, (_, i) => ({
      primary_id: `T${1000 + i}`,
      id_scheme: "attack-id",
      label: "Technique",
      name: `Synthetic Technique ${i}`,
      properties: { index: i },
      related: [] as Record<string, unknown>[],
      join_values: [`T${1000 + i}`],
      provenance: {
        source: "MITRE ATT&CK Enterprise",
        dataset: "attack",
        backend: "neo4j",
        query: "MATCH (t:Technique) RETURN t LIMIT 1000",
        record_id: `technique--${i}`,
        timestamp: "2026-06-29T19:00:00+00:00",
      },
    }));

    const bigFed: FederatedEvidence = {
      request: "synthetic 250-record query",
      results: [
        {
          task: {
            sub_question_id: "sq-big",
            source: "attack",
            text: "all techniques",
            entities: ["ATT&CK"],
            limits: { max_traversal_depth: 3, max_result_rows: 1000, query_timeout_ms: 5000 },
            join_key: null,
            seed_ids: [],
            rationale: "Test no-cap behavior.",
          },
          query: "MATCH (t:Technique) RETURN t LIMIT 1000",
          records: syntheticRecords,
          record_count: 250,
          summary: "250 records",
          traces: [],
          ok: true,
          partial: false,
          error: null,
          join_values: [],
        },
      ],
      unsupported: [],
      skipped: [],
      partial: false,
      join_index: {},
      cross_source_join_values: [],
    };

    const run = buildRun({
      id: "turn-big",
      question: "synthetic 250-record query",
      mode: "query",
      drafter: "deterministic",
      liveSources: PROBE,
      plan: null,
      evidence: bigFed,
      answer: null,
      status: "answered",
      exitCode: 0,
      elapsedMs: 0,
    });

    expect(run.evidence).toHaveLength(250);
    for (const row of run.evidence) {
      expect(row.fullJson).toBeTruthy();
      expect(row.fullJson.length).toBeGreaterThan(10);
      expect(row.provenanceQuery).toBe("MATCH (t:Technique) RETURN t LIMIT 1000");
    }
  });

  it("evidence rows carry idScheme, backend, joinValues, and provenanceMeta from the fixture", () => {
    const run = buildRun(wmiInputs());
    const t1047 = run.evidence.find((e) => e.id === "T1047")!;
    expect(t1047.idScheme).toBe("attack-id");
    expect(t1047.backend).toBe("neo4j");
    expect(t1047.joinValues).toEqual(["T1047"]);
    expect(t1047.provenanceMeta).toContain("attack");
    expect(t1047.provenanceMeta).toContain("neo4j");
    expect(t1047.fullJson).toContain("T1047");
  });

  it("lane records carry fullJson and query — no 6-record cap", () => {
    const manyRecords = Array.from({ length: 20 }, (_, i) => ({
      primary_id: `CAPEC-${600 + i}`,
      id_scheme: "capec-id",
      label: "AttackPattern",
      name: `Pattern ${i}`,
      properties: {},
      related: [] as Record<string, unknown>[],
      join_values: [] as string[],
      provenance: {
        source: "MITRE CAPEC",
        dataset: "capec",
        backend: "gremlin",
        query: "g.V().hasLabel('AttackPattern').limit(1000)",
        record_id: `capec--${600 + i}`,
        timestamp: "2026-06-29T19:00:00+00:00",
      },
    }));

    const fed: FederatedEvidence = {
      request: "capec with 20 records",
      results: [
        {
          task: {
            sub_question_id: "sq-capec-20",
            source: "capec",
            text: "all patterns",
            entities: ["CAPEC"],
            limits: { max_traversal_depth: 3, max_result_rows: 1000, query_timeout_ms: 5000 },
            join_key: null,
            seed_ids: [],
            rationale: "Test no-6-cap behavior for lanes.",
          },
          query: "g.V().hasLabel('AttackPattern').limit(1000)",
          records: manyRecords,
          record_count: 20,
          summary: "20 capec records",
          traces: [],
          ok: true,
          partial: false,
          error: null,
          join_values: [],
        },
      ],
      unsupported: [],
      skipped: [],
      partial: false,
      join_index: {},
      cross_source_join_values: [],
    };

    const run = buildRun({
      id: "turn-capec-20",
      question: "capec 20",
      mode: "query",
      drafter: "deterministic",
      liveSources: PROBE,
      plan: null,
      evidence: fed,
      answer: null,
      status: "answered",
      exitCode: 0,
      elapsedMs: 0,
    });

    expect(run.lanes).toHaveLength(1);
    const lane = run.lanes[0];
    expect(lane.records).toHaveLength(20); // no 6-record cap
    for (const rec of lane.records) {
      expect(rec.fullJson).toBeTruthy();
      expect(rec.fullJson).toContain("AttackPattern");
      expect(rec.query).toBe("g.V().hasLabel('AttackPattern').limit(1000)");
    }
  });
});

describe("buildSynthesis: the verified answer view", () => {
  const SYNTHESIS: ServerSynthesis = {
    request: "Which mitigations does ATT&CK list for T1047?",
    headline: "Verified answer with 1 supported claim.",
    claims: [
      {
        text: "T1047 is mitigated by M1038.",
        citations: [{ source: "attack", primary_id: "T1047", record_id: "attack:T1047" }],
        entity_ids: ["T1047", "M1038"],
        kind: "fact",
        sub_question_id: "sq-1",
        verdict: { verdict: "supported", reasons: [] },
      },
      {
        text: "T1047 is mitigated by the invented M9999.",
        citations: [{ source: "attack", primary_id: "T1047", record_id: "attack:T1047" }],
        entity_ids: ["M9999"],
        kind: "fact",
        sub_question_id: "sq-1",
        verdict: {
          verdict: "unsupported",
          reasons: ["claim asserts M9999 but no cited record grounds it"],
        },
      },
    ],
    rendered_claims: [
      {
        text: "T1047 is mitigated by M1038.",
        citations: [{ source: "attack", primary_id: "T1047", record_id: "attack:T1047" }],
        entity_ids: ["T1047", "M1038"],
        kind: "fact",
        sub_question_id: "sq-1",
      },
    ],
    abstentions: [
      {
        sub_question_id: "sq-2",
        source: "capec",
        statement:
          "The capec source doesn't establish this — the executed query ran cleanly and returned no matching records for: CAPEC-99999",
        query: "g.V().has('capec_id','CAPEC-99999').elementMap().limit(1000)",
      },
      {
        sub_question_id: "sq-3",
        source: "attack",
        statement:
          "The attack source doesn't establish this — it doesn't model the entities this question asks about, so no query was executed for: assets of T1047",
        query: "",
      },
    ],
    notes: ["one specialist was skipped"],
    composer: "llm",
    fallback_reason: "LLM composer unavailable (connection refused)",
    verification: {
      verdicts: [
        { verdict: "supported", reasons: [] },
        { verdict: "unsupported", reasons: ["ungrounded M9999"] },
      ],
      claim_count: 2,
      supported_count: 1,
      unsupported_count: 1,
      unsupported_claim_rate: 0.5,
      repaired_abstentions: 1,
      ok: false,
    },
  };

  it("maps rendered claims to cited chips with source accents", () => {
    const view = buildSynthesis(SYNTHESIS);
    expect(view).not.toBeNull();
    expect(view!.claims).toHaveLength(1);
    const claim = view!.claims[0];
    expect(claim.text).toContain("M1038");
    expect(claim.chips).toEqual([
      { id: "T1047", source: "attack/neo4j", accent: "teal", target: "lane-neo4j" },
    ]);
  });

  it("keeps cut claims visible in flagged with the verdict reasons", () => {
    const view = buildSynthesis(SYNTHESIS)!;
    expect(view.flagged).toHaveLength(1);
    expect(view.flagged[0].text).toContain("M9999");
    expect(view.flagged[0].reasons[0]).toContain("no cited record");
  });

  it("preserves the two abstention proof shapes: executed query vs boundary", () => {
    const view = buildSynthesis(SYNTHESIS)!;
    expect(view.abstentions).toHaveLength(2);
    expect(view.abstentions[0].query).toContain("CAPEC-99999");
    expect(view.abstentions[0].accent).toBe("amber");
    // Boundary refusal: no invented query proof.
    expect(view.abstentions[1].query).toBeNull();
    expect(view.abstentions[1].statement).toContain("no query was executed");
  });

  it("summarizes verification and composer fallback", () => {
    const view = buildSynthesis(SYNTHESIS)!;
    expect(view.verification).toEqual({
      supported: 1,
      total: 2,
      unsupportedRate: 0.5,
      repairedAbstentions: 1,
      ok: false,
    });
    expect(view.composer).toBe("llm");
    expect(view.fallbackReason).toContain("unavailable");
  });

  it("returns null when the payload predates Step 6", () => {
    expect(buildSynthesis(null)).toBeNull();
    expect(buildSynthesis(undefined)).toBeNull();
  });
});

describe("buildTimings / buildSequencingNotes (Wk 10-11 integration)", () => {
  it("projects pipeline timings into ordered latency chips", async () => {
    const { buildTimings } = await import("../adapt");
    expect(
      buildTimings({
        plan_ms: 3.2,
        specialists: [
          { sub_question: "q1", source: "capec", ms: 41 },
          { sub_question: "q2", source: "attack", ms: 12 },
        ],
        synthesis_ms: 0.4,
        total_ms: 90.1,
      }),
    ).toEqual([
      { label: "plan", ms: 3.2 },
      { label: "capec", ms: 41 },
      { label: "attack", ms: 12 },
      { label: "synthesis", ms: 0.4 },
      { label: "total", ms: 90.1 },
    ]);
    expect(buildTimings(null)).toBeNull();
    expect(buildTimings(undefined)).toBeNull();
    expect(buildTimings({})).toBeNull();
  });

  it("renders sequencing audit entries as readable notes", async () => {
    const { buildSequencingNotes } = await import("../adapt");
    const evidence = {
      request: "q",
      results: [],
      unsupported: [],
      skipped: [],
      partial: false,
      sequencing: [
        { consumer: "q2", producer: "q1", seed_count: 18, truncated: false, skipped: null },
        { consumer: "q3", producer: "q1", seed_count: 0, truncated: false, skipped: "it returned no join values" },
      ],
      join_index: {},
      cross_source_join_values: [],
    };
    expect(buildSequencingNotes(evidence)).toEqual([
      "q2 seeded with 18 join value(s) from q1",
      "q3 skipped — producer q1: it returned no join values",
    ]);
    // Pre-integration payloads (no sequencing field) yield no notes.
    expect(buildSequencingNotes({ ...evidence, sequencing: undefined })).toEqual([]);
    expect(buildSequencingNotes(null)).toEqual([]);
  });
});

describe("lane arrival metadata (Wk live-animation)", () => {
  it("threads laneMeta into lanes and stamps record order", () => {
    const base = wmiCapecRun;
    const evidence = base.federated;
    const inputs: RunInputs = {
      id: "t1",
      question: evidence.request,
      mode: "query",
      drafter: "deterministic",
      liveSources: [],
      plan: null,
      evidence,
      answer: null,
      status: "answered",
      exitCode: 0,
      elapsedMs: 1200,
      laneMeta: {
        "lane-neo4j": {
          subQuestion: "q2",
          startedMs: 300,
          arrivedMs: 950,
          seedCount: 18,
          producer: "q1",
          order: 2,
        },
      },
    };
    const run = buildRun(inputs);
    const neo = run.lanes.find((l) => l.id === "lane-neo4j");
    expect(neo?.arrival).toEqual({
      subQuestion: "q2",
      startedMs: 300,
      arrivedMs: 950,
      seedCount: 18,
      producer: "q1",
      order: 2,
    });
    // Lanes without metadata stay null (demo turns, older payloads).
    const grem = run.lanes.find((l) => l.id === "lane-gremlin");
    expect(grem?.arrival ?? null).toBeNull();
    // Every record carries its 1-based emission order.
    for (const lane of run.lanes) {
      expect(lane.records.map((r) => r.order)).toEqual(
        lane.records.map((_, i) => i + 1),
      );
    }
  });
});
