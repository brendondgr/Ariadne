import { describe, expect, it } from "vitest";
import { deprecatedCapecRun, seededRuns, wmiCapecRun } from "../fixtures";
import type { SpecialistStep } from "../types";

const EXPECTED_STEPS: SpecialistStep[] = [
  "intake",
  "resolve",
  "gate",
  "execute",
  "assess",
  "normalize",
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

  it("runs two specialist lanes, each with all six canonical micro-steps", () => {
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

describe("deprecatedCapecRun fixture (exclude-at-load abstention)", () => {
  it("is a seeded follow-up turn in the opening conversation", () => {
    expect(seededRuns.map((r) => r.id)).toEqual(["turn-1", "turn-2"]);
    expect(seededRuns[1]).toBe(deprecatedCapecRun);
  });

  it("runs cleanly (answered, exit 0) yet returns zero records", () => {
    expect(deprecatedCapecRun.status).toBe("answered");
    expect(deprecatedCapecRun.exitCode).toBe(0);
    expect(deprecatedCapecRun.federated.partial).toBe(false);
    const totalRecords = deprecatedCapecRun.federated.results.reduce(
      (n, r) => n + r.record_count,
      0,
    );
    expect(totalRecords).toBe(0);
    expect(deprecatedCapecRun.evidence).toHaveLength(0);
    // The single CAPEC specialist ran without error — an honest empty, not a failure.
    expect(deprecatedCapecRun.federated.results).toHaveLength(1);
    expect(deprecatedCapecRun.federated.results[0].ok).toBe(true);
  });

  it("carries the query as proof and an exclude-at-load abstention", () => {
    const capec = deprecatedCapecRun.federated.results[0];
    expect(capec.query.length).toBeGreaterThan(0);
    expect(deprecatedCapecRun.federated.unsupported).toHaveLength(1);
    expect(deprecatedCapecRun.federated.unsupported[0].reason.toLowerCase()).toContain(
      "excluded at load",
    );
    // No fabricated cross-source join for a pattern that does not exist.
    expect(deprecatedCapecRun.joinIndex).toHaveLength(0);
    expect(deprecatedCapecRun.answer.joinPairs).toHaveLength(0);
  });
});

describe("seeded turns carry the verified synthesis view (Step 7b)", () => {
  it("wmi turn: three supported cited claims, clean verification", () => {
    const synth = wmiCapecRun.answer.synthesis;
    expect(synth).not.toBeNull();
    expect(synth!.claims).toHaveLength(3);
    expect(synth!.claims.every((c) => c.chips.length > 0)).toBe(true);
    expect(synth!.claims.map((c) => c.kind)).toContain("correlation");
    expect(synth!.abstentions).toHaveLength(0);
    expect(synth!.flagged).toHaveLength(0);
    expect(synth!.verification).toMatchObject({ supported: 3, total: 3, ok: true });
  });

  it("deprecated-CAPEC turn: pure abstention with the executed query as proof", () => {
    const synth = deprecatedCapecRun.answer.synthesis;
    expect(synth).not.toBeNull();
    expect(synth!.claims).toHaveLength(0);
    expect(synth!.abstentions).toHaveLength(1);
    const abst = synth!.abstentions[0];
    expect(abst.statement).toContain("doesn't establish");
    expect(abst.query).toContain("capec_id");
    expect(abst.query).toContain("557");
    expect(synth!.verification).toMatchObject({ supported: 0, total: 0, ok: true });
  });
});
