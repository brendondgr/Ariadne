import { describe, expect, it } from "vitest";
import { buildChatExport } from "../export";
import type { WorkbenchRun } from "../types";

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
