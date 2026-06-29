import { describe, expect, it } from "vitest";
import { wmiCapecRun } from "../fixtures";
import type { SpecialistStep } from "../types";

const EXPECTED_STEPS: SpecialistStep[] = [
  "intake",
  "resolve",
  "draft",
  "gate",
  "execute",
  "assess",
  "normalize",
  "handoff",
];

describe("wmiCapecRun fixture", () => {
  it("is a fully-grounded answered run (exit 0)", () => {
    expect(wmiCapecRun.status).toBe("answered");
    expect(wmiCapecRun.exitCode).toBe(0);
    expect(wmiCapecRun.federated.partial).toBe(false);
  });

  it("probes both backends as live", () => {
    expect(wmiCapecRun.liveSources).toHaveLength(2);
    expect(wmiCapecRun.liveSources.every((s) => s.status === "live")).toBe(true);
  });

  it("emits the four planner stages: probe, draft, gate, emit", () => {
    expect(wmiCapecRun.plannerStages.map((s) => s.id)).toEqual([
      "stage-probe",
      "stage-draft",
      "stage-gate",
      "stage-emit",
    ]);
    const gate = wmiCapecRun.plannerStages.find((s) => s.id === "stage-gate");
    expect(gate?.shield).toBe(true);
  });

  it("runs two specialist lanes, each with all eight micro-steps", () => {
    expect(wmiCapecRun.lanes).toHaveLength(2);
    for (const lane of wmiCapecRun.lanes) {
      expect(lane.steps.map((s) => s.key)).toEqual(EXPECTED_STEPS);
      // pre-run gate and normalize are the never-cut checkpoints.
      const emphasized = lane.steps.filter((s) => s.emphasis).map((s) => s.key);
      expect(emphasized).toEqual(["gate", "normalize"]);
      expect(lane.query.length).toBeGreaterThan(0);
    }
  });

  it("normalizes four evidence records across both sources", () => {
    expect(wmiCapecRun.evidence).toHaveLength(4);
    const totalRecords = wmiCapecRun.federated.results.reduce(
      (n, r) => n + r.record_count,
      0,
    );
    expect(totalRecords).toBe(4);
  });

  it("declares two cross-source join candidates", () => {
    expect(wmiCapecRun.joinIndex).toHaveLength(2);
    expect(wmiCapecRun.federated.cross_source_join_values).toEqual([
      "T1047",
      "T1546.003",
    ]);
  });

  it("keeps every evidence record's provenance complete", () => {
    for (const result of wmiCapecRun.federated.results) {
      for (const rec of result.records) {
        expect(rec.provenance).not.toBeNull();
        const p = rec.provenance!;
        expect(p.source && p.dataset && p.backend && p.query && p.record_id && p.timestamp).toBeTruthy();
      }
    }
  });
});
