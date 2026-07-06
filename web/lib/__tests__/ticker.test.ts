import { describe, expect, it } from "vitest";
import { describeEvent, tickerLines } from "../ticker";
import type { StampedQueryEvent } from "../types";

const EVENTS: StampedQueryEvent[] = [
  { type: "status", data: { phase: "probing" }, receivedMs: 120 },
  {
    type: "probe",
    data: {
      live_sources: [
        { dataset: "attack", backend: "neo4j", endpoint: "bolt://x", live: true, node_count: 4369, observed_labels: [], reason: "" },
        { dataset: "capec", backend: "gremlin", endpoint: "ws://y", live: false, node_count: 0, observed_labels: [], reason: "down" },
      ],
    },
    receivedMs: 340,
  },
  {
    type: "specialist-start",
    data: { sub_question: "q2", source: "attack", index: 1, total: 2, seed_count: 18, producer: "q1", skipped: null },
    receivedMs: 900,
  },
  {
    type: "done",
    data: { status: "answered", exit_code: 0 },
    receivedMs: 1500,
  },
];

describe("describeEvent / tickerLines", () => {
  it("narrates each event with its elapsed arrival time", () => {
    const lines = tickerLines(EVENTS);
    expect(lines.map((l) => l.text)).toEqual([
      "probing graph backends…",
      "probe: attack live (4369 nodes) · capec DOWN",
      "q2 [attack] querying… seeded with 18 id(s) from q1",
      "done · answered (exit 0)",
    ]);
    expect(lines.map((l) => l.time)).toEqual(["0.1s", "0.3s", "0.9s", "1.5s"]);
    expect(lines[3].terminal).toBe(true);
  });

  it("narrates specialist results, honest empties, and announced skips", () => {
    const result = (over: object) => ({
      type: "specialist" as const,
      data: {
        result: {
          task: { sub_question_id: "q1", source: "capec", text: "", entities: [], limits: {}, join_key: null, seed_ids: [], rationale: "" },
          query: "g.V()", records: [{}, {}], record_count: 2, summary: "", traces: [], ok: true, partial: false, error: null,
          join_values: [],
          ...over,
        },
      },
      receivedMs: 700,
    });
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(describeEvent(result({}) as any, 0)?.text).toBe("capec: 2 record(s) returned");
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(describeEvent(result({ records: [], query: "" }) as any, 0)?.text).toBe(
      "capec: no query executed (honest empty)",
    );
    const skipStart: StampedQueryEvent = {
      type: "specialist-start",
      data: { sub_question: "q2", source: "attack", index: 1, total: 2, seed_count: 0, producer: "q1", skipped: "it returned no join values" },
      receivedMs: 800,
    };
    expect(describeEvent(skipStart, 0)?.text).toBe(
      "q2 [attack] skipped — it returned no join values",
    );
    expect(describeEvent(skipStart, 0)?.accent).toBe("amber");
  });

  it("drops events with no narration and tolerates missing stamps", () => {
    const unknown = { type: "status", data: { phase: "mystery" } } as StampedQueryEvent;
    expect(describeEvent(unknown, 0)).toBeNull();
    const unstamped: StampedQueryEvent = { type: "done", data: { status: "partial", exit_code: 1 } };
    const line = describeEvent(unstamped, 3);
    expect(line?.time).toBe("");
    expect(line?.accent).toBe("amber");
  });
});
