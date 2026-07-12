import { describe, expect, it } from "vitest";
import {
  buildMitigationMatrix,
  cellKey,
  isRenderableMatrix,
} from "../synthesisMatrix";
import { buildEntityDetails } from "../synthesisGraph";
import type {
  EvidenceRecord,
  FederatedEvidence,
  SpecialistResult,
  SynthesisView,
} from "../types";

/* -------------------------------------------------------------------------- */
/* Helpers (mirroring synthesisGraph.test.ts)                                  */
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

const EXPLICIT = [
  { source: "T1047", target: "M1038", rel: "mitigatedBy" },
  { source: "T1047", target: "M1026", rel: "mitigatedBy" },
  { source: "T1546.003", target: "M1038", rel: "mitigatedBy" },
  { source: "CAPEC-549", target: "T1047", rel: "mapsTo" },
];

/* -------------------------------------------------------------------------- */
/* buildMitigationMatrix                                                       */
/* -------------------------------------------------------------------------- */

describe("buildMitigationMatrix (explicit edges)", () => {
  it("grids techniques×mitigations from mitigatedBy edges, ignoring mapsTo", () => {
    const matrix = buildMitigationMatrix(view([], EXPLICIT), []);
    expect(matrix.techniques.map((t) => t.id)).toEqual(["T1047", "T1546.003"]);
    expect(matrix.mitigations.map((m) => m.id)).toEqual(["M1026", "M1038"]);
    expect(matrix.cells).toEqual(
      new Set([
        cellKey("T1047", "M1038"),
        cellKey("T1047", "M1026"),
        cellKey("T1546.003", "M1038"),
      ]),
    );
    // The uncovered cell stays empty.
    expect(matrix.cells.has(cellKey("T1546.003", "M1026"))).toBe(false);
  });

  it("is provenance-exact when the payload carries explicit edges", () => {
    expect(buildMitigationMatrix(view([], EXPLICIT), []).provenanceExact).toBe(true);
  });

  it("orients a reversed mitigation→technique edge defensively", () => {
    const matrix = buildMitigationMatrix(
      view([], [{ source: "M1038", target: "T1047", rel: "mitigatedBy" }]),
      [],
    );
    expect(matrix.techniques.map((t) => t.id)).toEqual(["T1047"]);
    expect(matrix.mitigations.map((m) => m.id)).toEqual(["M1038"]);
    expect(matrix.cells.has(cellKey("T1047", "M1038"))).toBe(true);
  });

  it("ignores mitigatedBy edges whose endpoints are not a technique/mitigation pair", () => {
    const matrix = buildMitigationMatrix(
      view([], [{ source: "CAPEC-549", target: "M1038", rel: "mitigatedBy" }]),
      [],
    );
    expect(isRenderableMatrix(matrix)).toBe(false);
  });

  it("sorts rows and columns by id for a deterministic render", () => {
    const shuffled = [
      { source: "T1546.003", target: "M1038", rel: "mitigatedBy" },
      { source: "T1047", target: "M1026", rel: "mitigatedBy" },
    ];
    const matrix = buildMitigationMatrix(view([], shuffled), []);
    expect(matrix.techniques.map((t) => t.id)).toEqual(["T1047", "T1546.003"]);
    expect(matrix.mitigations.map((m) => m.id)).toEqual(["M1026", "M1038"]);
  });

  it("de-duplicates repeated pairs", () => {
    const doubled = [
      { source: "T1047", target: "M1038", rel: "mitigatedBy" },
      { source: "T1047", target: "M1038", rel: "mitigatedBy" },
    ];
    const matrix = buildMitigationMatrix(view([], doubled), []);
    expect(matrix.cells.size).toBe(1);
  });
});

describe("buildMitigationMatrix (inference fallback)", () => {
  it("grids co-citation-inferred pairs and reports them as not provenance-exact", () => {
    const matrix = buildMitigationMatrix(
      view([claim({ entityIds: ["T1047", "M1038"] })]),
      [],
    );
    expect(matrix.cells.has(cellKey("T1047", "M1038"))).toBe(true);
    expect(matrix.provenanceExact).toBe(false);
  });

  it("is not renderable when no claim links a technique to a mitigation", () => {
    const matrix = buildMitigationMatrix(
      view([claim({ entityIds: ["CAPEC-549", "T1047"] })]),
      [],
    );
    expect(isRenderableMatrix(matrix)).toBe(false);
  });
});

describe("buildMitigationMatrix names", () => {
  it("resolves display names from entity details, falling back to the id", () => {
    const details = buildEntityDetails(
      fed({
        results: [
          resultWith([
            record({
              primary_id: "T1047",
              name: "Windows Management Instrumentation",
              related: [{ id: "M1038", name: "Execution Prevention" }],
            }),
          ]),
        ],
      }),
    );
    const matrix = buildMitigationMatrix(view([], EXPLICIT), [], details);
    expect(matrix.techniques.find((t) => t.id === "T1047")?.name).toBe(
      "Windows Management Instrumentation",
    );
    // Named via the record's related entry (the buildEntityDetails extension).
    expect(matrix.mitigations.find((m) => m.id === "M1038")?.name).toBe(
      "Execution Prevention",
    );
    // No detail anywhere → id fallback.
    expect(matrix.mitigations.find((m) => m.id === "M1026")?.name).toBe("M1026");
  });
});

/* -------------------------------------------------------------------------- */
/* isRenderableMatrix                                                          */
/* -------------------------------------------------------------------------- */

describe("isRenderableMatrix", () => {
  it("is false for an empty view", () => {
    expect(isRenderableMatrix(buildMitigationMatrix(view([]), []))).toBe(false);
  });

  it("is true once one technique↔mitigation cell exists", () => {
    const matrix = buildMitigationMatrix(
      view([], [{ source: "T1047", target: "M1038", rel: "mitigatedBy" }]),
      [],
    );
    expect(isRenderableMatrix(matrix)).toBe(true);
  });
});
