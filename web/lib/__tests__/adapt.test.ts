import { describe, expect, it } from "vitest";
import { buildLiveSources, buildRun, type RunInputs } from "../adapt";
import { wmiCapecRun } from "../fixtures";
import type {
  FederatedEvidence,
  Plan,
  ProbeSource,
  ServerAnswer,
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
