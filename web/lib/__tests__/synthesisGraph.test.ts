import { describe, expect, it } from "vitest";
import {
  buildEntityDetails,
  classifyEntity,
  deriveEdges,
  isRenderableSubgraph,
  synthesisToGraphPayload,
  REL_MAPS_TO,
  REL_MITIGATED_BY,
} from "../synthesisGraph";
import { toForceGraphData } from "../graph";
import type {
  EvidenceRecord,
  FederatedEvidence,
  JoinIndexEntry,
  JoinPair,
  SpecialistResult,
  SynthesisView,
} from "../types";

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function claim(over: Partial<SynthesisView["claims"][number]>): SynthesisView["claims"][number] {
  return { text: "", kind: "fact", chips: [], entityIds: [], contested: [], ...over };
}

function view(
  claims: SynthesisView["claims"],
  edges: SynthesisView["edges"] = [],
): SynthesisView {
  return {
    headline: "",
    narrative: "",
    claims,
    abstentions: [],
    flagged: [],
    conflicts: [],
    notes: [],
    composer: "deterministic",
    fallbackReason: null,
    verification: null,
    edges,
  };
}

const JOINS: JoinPair[] = [
  { left: "CAPEC-549", leftAccent: "amber", right: "T1047", rightAccent: "teal" },
  { left: "CAPEC-563", leftAccent: "amber", right: "T1546.003", rightAccent: "teal" },
];

function record(over: Partial<EvidenceRecord>): EvidenceRecord {
  return {
    primary_id: "",
    id_scheme: "",
    label: "",
    name: "",
    properties: {},
    related: [],
    join_values: [],
    provenance: null,
    ...over,
  };
}

function fed(over: Partial<FederatedEvidence>): FederatedEvidence {
  return {
    request: "",
    results: [],
    unsupported: [],
    skipped: [],
    partial: false,
    join_index: {},
    cross_source_join_values: [],
    ...over,
  };
}

function resultWith(records: EvidenceRecord[]): SpecialistResult {
  return {
    task: {
      sub_question_id: "",
      source: "",
      text: "",
      entities: [],
      limits: { max_traversal_depth: 0, max_result_rows: 0, query_timeout_ms: 0 },
      join_key: null,
      seed_ids: [],
      rationale: "",
    },
    query: "",
    records,
    record_count: records.length,
    summary: "",
    traces: [],
    ok: true,
    partial: false,
    error: null,
    join_values: [],
  };
}

/* -------------------------------------------------------------------------- */
/* classifyEntity                                                              */
/* -------------------------------------------------------------------------- */

describe("classifyEntity", () => {
  it("types CAPEC patterns, techniques, sub-techniques, and mitigations by prefix", () => {
    expect(classifyEntity("CAPEC-549").kind).toBe("capec");
    expect(classifyEntity("T1047").kind).toBe("technique");
    expect(classifyEntity("T1546.003").kind).toBe("technique");
    expect(classifyEntity("M1038").kind).toBe("mitigation");
    expect(classifyEntity("something-else").kind).toBe("other");
  });

  it("gives each kind a distinct label so the palette separates them", () => {
    const labels = new Set(
      ["CAPEC-1", "T1000", "M1000"].map((id) => classifyEntity(id).label),
    );
    expect(labels.size).toBe(3);
  });
});

/* -------------------------------------------------------------------------- */
/* deriveEdges — inference mode (Option A)                                     */
/* -------------------------------------------------------------------------- */

describe("deriveEdges (inference mode)", () => {
  it("orients CAPEC→ATT&CK edges from the join index regardless of pair order", () => {
    const reversed: JoinPair[] = [
      { left: "T1047", leftAccent: "teal", right: "CAPEC-549", rightAccent: "amber" },
    ];
    const edges = deriveEdges([], reversed);
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({ source: "CAPEC-549", target: "T1047", type: REL_MAPS_TO });
  });

  it("infers technique→mitigation from within-claim co-citation", () => {
    const edges = deriveEdges(
      [claim({ kind: "fact", entityIds: ["T1047", "M1038"] })],
      [],
    );
    expect(edges).toContainEqual(
      expect.objectContaining({ source: "T1047", target: "M1038", type: REL_MITIGATED_BY }),
    );
  });

  it("de-duplicates an edge derived from both the join index and a claim", () => {
    const edges = deriveEdges(
      [claim({ kind: "correlation", entityIds: ["CAPEC-549", "T1047"] })],
      JOINS,
    );
    const mapsTo = edges.filter(
      (e) => e.source === "CAPEC-549" && e.target === "T1047" && e.type === REL_MAPS_TO,
    );
    expect(mapsTo).toHaveLength(1);
  });

  it("drops self-loops and never emits an edge for a lone id", () => {
    const edges = deriveEdges([claim({ entityIds: ["T1047"] })], []);
    expect(edges).toHaveLength(0);
  });
});

/* -------------------------------------------------------------------------- */
/* deriveEdges — explicit mode (Option B)                                      */
/* -------------------------------------------------------------------------- */

describe("deriveEdges (explicit mode)", () => {
  it("uses the payload's exact edges verbatim and skips inference", () => {
    // Inference would produce CAPEC-549→T1047 from JOINS; explicit overrides it
    // with a different exact set, proving inference is bypassed.
    const explicit = [{ source: "CAPEC-999", target: "T9999", rel: "mapsTo" }];
    const edges = deriveEdges([], JOINS, explicit);
    expect(edges).toEqual([
      { id: "CAPEC-999__mapsTo__T9999", source: "CAPEC-999", target: "T9999", type: "mapsTo" },
    ]);
  });

  it("falls back to inference when the explicit set is empty", () => {
    const edges = deriveEdges([], JOINS, []);
    expect(edges.length).toBe(2); // both join pairs
    expect(edges.every((e) => e.type === REL_MAPS_TO)).toBe(true);
  });

  it("carries the backend rel type onto the graph edge", () => {
    const explicit = [{ source: "T1047", target: "M1038", rel: REL_MITIGATED_BY }];
    const edges = deriveEdges([], [], explicit);
    expect(edges[0].type).toBe(REL_MITIGATED_BY);
  });
});

describe("synthesisToGraphPayload with explicit edges", () => {
  it("prefers the payload edges over inference and includes their endpoints as nodes", () => {
    const v = view(
      [claim({ kind: "correlation", entityIds: ["CAPEC-1", "T1000"] })],
      [{ source: "CAPEC-1", target: "T1000", rel: "mapsTo" }],
    );
    const payload = synthesisToGraphPayload(v, []);
    expect(payload.edges).toEqual([
      { id: "CAPEC-1__mapsTo__T1000", source: "CAPEC-1", target: "T1000", type: "mapsTo" },
    ]);
    const ids = payload.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(["CAPEC-1", "T1000"]);
  });
});

/* -------------------------------------------------------------------------- */
/* synthesisToGraphPayload                                                     */
/* -------------------------------------------------------------------------- */

describe("synthesisToGraphPayload", () => {
  const v = view([
    claim({ kind: "fact", chips: [{ id: "T1047", source: "attack/neo4j", accent: "teal" }], entityIds: ["T1047"] }),
    claim({
      kind: "correlation",
      chips: [
        { id: "T1047", source: "attack/neo4j", accent: "teal" },
        { id: "M1038", source: "attack/neo4j", accent: "teal" },
      ],
      entityIds: ["T1047", "M1038"],
    }),
  ]);

  it("builds nodes for every cited/asserted id plus join endpoints", () => {
    const payload = synthesisToGraphPayload(v, JOINS);
    const ids = payload.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(["CAPEC-549", "CAPEC-563", "M1038", "T1047", "T1546.003"]);
  });

  it("labels nodes by kind so the force-graph palette separates them", () => {
    const payload = synthesisToGraphPayload(v, JOINS);
    const t1047 = payload.nodes.find((n) => n.id === "T1047");
    const capec = payload.nodes.find((n) => n.id === "CAPEC-549");
    expect(t1047?.label).toBe("ATT&CK Technique");
    expect(capec?.label).toBe("CAPEC Pattern");
  });

  it("produces a payload the existing toForceGraphData renders without dangling links", () => {
    const payload = synthesisToGraphPayload(v, JOINS);
    const fg = toForceGraphData(payload);
    const nodeIds = new Set(fg.nodes.map((n) => n.id));
    // Every link endpoint resolves to a rendered node.
    for (const link of fg.links) {
      expect(nodeIds.has(link.sourceId)).toBe(true);
      expect(nodeIds.has(link.targetId)).toBe(true);
    }
    expect(fg.links.length).toBeGreaterThan(0);
  });

  it("counts reflect the derived graph", () => {
    const payload = synthesisToGraphPayload(v, JOINS);
    expect(payload.counts.nodes).toBe(payload.nodes.length);
    expect(payload.counts.relationships).toBe(payload.edges.length);
  });
});

/* -------------------------------------------------------------------------- */
/* isRenderableSubgraph                                                        */
/* -------------------------------------------------------------------------- */

describe("isRenderableSubgraph", () => {
  it("is false with no edges (nothing to plot)", () => {
    const payload = synthesisToGraphPayload(view([claim({ entityIds: ["T1047"] })]), []);
    expect(isRenderableSubgraph(payload)).toBe(false);
  });

  it("is true once there is at least one edge between two nodes", () => {
    const payload = synthesisToGraphPayload(view([]), JOINS);
    expect(isRenderableSubgraph(payload)).toBe(true);
  });
});

/* -------------------------------------------------------------------------- */
/* buildEntityDetails                                                          */
/* -------------------------------------------------------------------------- */

describe("buildEntityDetails", () => {
  it("returns an empty map for missing evidence", () => {
    expect(buildEntityDetails(null).size).toBe(0);
    expect(buildEntityDetails(undefined).size).toBe(0);
  });

  it("projects name/label/properties from specialist records", () => {
    const details = buildEntityDetails(
      fed({
        results: [
          resultWith([
            record({
              primary_id: "T1047",
              name: "Windows Management Instrumentation",
              label: "ATT&CK Technique",
              properties: { description: "Adversaries may abuse WMI…" },
            }),
          ]),
        ],
      }),
    );
    expect(details.get("T1047")).toEqual({
      name: "Windows Management Instrumentation",
      label: "ATT&CK Technique",
      properties: { description: "Adversaries may abuse WMI…" },
    });
  });

  it("falls back to a join-index name (no properties) when there is no record", () => {
    const entries: JoinIndexEntry[] = [
      { source: "capec", primary_id: "CAPEC-549", name: "Local Execution of Code" },
    ];
    const details = buildEntityDetails(fed({ join_index: { T1047: entries } }));
    expect(details.get("CAPEC-549")).toEqual({
      name: "Local Execution of Code",
      label: "",
      properties: {},
    });
  });

  it("prefers the record over a join-index entry for the same id", () => {
    const entries: JoinIndexEntry[] = [
      { source: "attack", primary_id: "T1047", name: "join-name" },
    ];
    const details = buildEntityDetails(
      fed({
        join_index: { key: entries },
        results: [
          resultWith([
            record({ primary_id: "T1047", name: "record-name", properties: { a: 1 } }),
          ]),
        ],
      }),
    );
    expect(details.get("T1047")?.name).toBe("record-name");
    expect(details.get("T1047")?.properties).toEqual({ a: 1 });
  });
});

/* -------------------------------------------------------------------------- */
/* synthesisToGraphPayload — node enrichment                                   */
/* -------------------------------------------------------------------------- */

describe("synthesisToGraphPayload node enrichment", () => {
  const details = buildEntityDetails(
    fed({
      results: [
        resultWith([
          record({
            primary_id: "T1047",
            name: "Windows Management Instrumentation",
            label: "ATT&CK Technique",
            properties: { description: "desc" },
          }),
        ]),
      ],
    }),
  );

  it("stamps the real name and properties onto a matched node", () => {
    const payload = synthesisToGraphPayload(view([]), JOINS, details);
    const t1047 = payload.nodes.find((n) => n.id === "T1047");
    expect(t1047?.name).toBe("Windows Management Instrumentation");
    expect(t1047?.properties).toEqual({ description: "desc" });
  });

  it("keeps the palette label from the id prefix, not the evidence label", () => {
    const payload = synthesisToGraphPayload(view([]), JOINS, details);
    const t1047 = payload.nodes.find((n) => n.id === "T1047");
    expect(t1047?.label).toBe("ATT&CK Technique");
    expect(t1047?.labels).toEqual(["ATT&CK Technique"]);
  });

  it("falls back to the id as name when no detail matches", () => {
    const payload = synthesisToGraphPayload(view([]), JOINS, details);
    const capec = payload.nodes.find((n) => n.id === "CAPEC-563");
    expect(capec?.name).toBe("CAPEC-563");
    expect(capec?.properties).toEqual({});
  });

  it("behaves identically to the pre-enrichment call when details are omitted", () => {
    const payload = synthesisToGraphPayload(view([]), JOINS);
    const t1047 = payload.nodes.find((n) => n.id === "T1047");
    expect(t1047?.name).toBe("T1047");
    expect(t1047?.properties).toEqual({});
  });
});
