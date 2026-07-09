import { describe, expect, it } from "vitest";
import { buildChatExport, buildFullHistoryExport } from "../export";
import type { PlannerStage, SpecialistLane, WorkbenchRun } from "../types";

function stage(partial: Partial<PlannerStage>): PlannerStage {
  return {
    id: "plan",
    index: "1",
    title: "Plan",
    status: "pass",
    summary: "",
    code: "",
    codeLang: "text",
    ...partial,
  } as PlannerStage;
}

function lane(partial: Partial<SpecialistLane>): SpecialistLane {
  return {
    id: "lane",
    badge: "",
    backend: "neo4j",
    accent: "teal",
    title: "ATT&CK",
    rows: 0,
    ms: 0,
    language: "cypher",
    query: "",
    steps: [],
    records: [],
    arrival: null,
    task: { source: "", entities: [], seedIds: [], joinKey: null, rationale: "", limitsJson: "" },
    traceEntries: [],
    error: null,
    ...partial,
  } as SpecialistLane;
}

function run(partial: Partial<WorkbenchRun>): WorkbenchRun {
  return {
    id: "q-1",
    question: "",
    mode: "query",
    drafter: "llm",
    status: "answered",
    exitCode: 0,
    elapsedMs: 0,
    createdAt: 0,
    liveSources: [],
    stepper: [],
    plannerStages: [],
    lanes: [],
    answer: { paragraphs: [], joinPairs: [], synthesis: null, timings: null, sequencingNotes: [] },
    evidence: [],
    joinIndex: [],
    joinKey: "external_id",
    federated: {
      request: "",
      results: [],
      unsupported: [],
      skipped: [],
      partial: false,
      join_index: {},
      cross_source_join_values: [],
    },
    rawProbe: [],
    rawPlan: null,
    rawAnswer: null,
    events: [],
    ...partial,
  } as WorkbenchRun;
}

describe("buildChatExport", () => {
  it("renders a title and empty-state when there are no turns", () => {
    const md = buildChatExport("My thread", []);
    expect(md).toContain("# My thread");
    expect(md).toContain("no messages yet");
  });

  it("serializes each turn's question and reply with the route label", () => {
    const runs = [
      run({
        id: "q-1",
        question: "What does CAPEC-98 map to?",
        reply: { text: "CAPEC-98 maps to T1566 and T1598.", route: "graph", composer: "llm", grounded: true },
      }),
      run({
        id: "q-2",
        question: "What did it map to again?",
        reply: { text: "T1566 and T1598.", route: "quick", composer: "llm", grounded: true },
      }),
    ];
    const md = buildChatExport("Phishing", runs);
    expect(md).toContain("# Phishing");
    expect(md).toContain("## 1. You");
    expect(md).toContain("What does CAPEC-98 map to?");
    expect(md).toContain("queried the graphs");
    expect(md).toContain("CAPEC-98 maps to T1566 and T1598.");
    expect(md).toContain("## 2. You");
    expect(md).toContain("answered from memory");
    // Turns are separated.
    expect(md).toContain("---");
  });

  it("falls back to a placeholder when a turn has no reply", () => {
    const md = buildChatExport("t", [run({ question: "hi", reply: null })]);
    expect(md).toContain("no reply captured");
  });

  it("uses a default title when none is given", () => {
    expect(buildChatExport("", [])).toContain("# Conversation");
  });
});

describe("buildFullHistoryExport", () => {
  it("renders the empty-state and default title like the chat export", () => {
    expect(buildFullHistoryExport("My thread", [])).toContain("no messages yet");
    expect(buildFullHistoryExport("", [])).toContain("# Conversation");
  });

  it("traces a graph turn's planner stages and specialist queries in order", () => {
    const md = buildFullHistoryExport("Phishing", [
      run({
        question: "What does CAPEC-98 map to?",
        route: "graph",
        plannerStages: [
          stage({ title: "Draft plan", status: "pass", summary: "Two sub-questions" }),
        ],
        lanes: [
          lane({
            backend: "gremlin",
            title: "CAPEC",
            rows: 3,
            ms: 42,
            language: "gremlin",
            query: "g.V('CAPEC-98')",
            arrival: { subQuestion: "q1", startedMs: 0, arrivedMs: 42, seedCount: 0, producer: null, order: 2 },
          }),
          lane({
            backend: "neo4j",
            title: "ATT&CK",
            rows: 5,
            ms: 17,
            language: "cypher",
            query: "MATCH (t:Technique) RETURN t",
            arrival: { subQuestion: "q0", startedMs: 0, arrivedMs: 17, seedCount: 0, producer: null, order: 1 },
          }),
        ],
        answer: {
          paragraphs: [],
          joinPairs: [],
          synthesis: null,
          timings: [{ label: "plan", ms: 12 }],
          sequencingNotes: ["neo4j → gremlin seeding"],
        },
        validation: { verdict: "pass", reason: "complete", missing: [], iteration: 1 },
        reply: { text: "CAPEC-98 maps to T1566 and T1598.", route: "graph", composer: "llm", grounded: true },
      }),
    ]);

    expect(md).toContain("**Pipeline:**");
    expect(md).toContain("**Draft plan**");
    // Lanes are ordered by arrival.order: ATT&CK (order 1, 5 rows) before CAPEC (order 2, 3 rows).
    expect(md.indexOf("5 record(s) in 17 ms")).toBeLessThan(md.indexOf("3 record(s) in 42 ms"));
    expect(md).toContain("5 record(s) in 17 ms");
    expect(md).toContain("MATCH (t:Technique) RETURN t");
    expect(md).toContain("_Sequencing:_ neo4j → gremlin seeding");
    expect(md).toContain("_Validation:_ pass");
    expect(md).toContain("_Timings:_ plan 12ms");
    expect(md).toContain("CAPEC-98 maps to T1566 and T1598.");
  });

  it("marks a memory-answered (quick) turn as no graph queried", () => {
    const md = buildFullHistoryExport("t", [
      run({
        question: "What did it map to again?",
        route: "quick",
        reply: { text: "T1566 and T1598.", route: "quick", composer: "llm", grounded: true },
      }),
    ]);
    expect(md).toContain("answered from memory (no graph queried)");
    expect(md).not.toContain("record(s) in");
  });
});
