"use client";

import type { E2EOverall } from "@/lib/types";

function pct(x: number): string {
  return `${(x * 100).toFixed(1)}%`;
}

/**
 * LLM-evaluator panel. The unsupported-claim rate is always deterministic; the
 * three qualitative dimensions come from the deterministic proxy (reproducible)
 * unless the opt-in LLM judge contributed — surfaced by the source pill.
 */
export function JudgePanel({ judge }: { judge: E2EOverall["llm_judge"] }) {
  const isLLM = judge.source !== "deterministic";
  const dims: [string, number][] = [
    ["faithfulness", judge.mean_faithfulness],
    ["groundedness", judge.mean_groundedness],
    ["evidence sufficiency", judge.mean_evidence_sufficiency],
    ["unsupported-claim rate", judge.mean_unsupported_claim_rate],
  ];
  return (
    <section className="rounded-lg p-4" style={{ boxShadow: "rgba(235,230,220,0.08) 0 0 0 1px" }}>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="m-0 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">LLM Evaluator</h2>
        <span
          className="rounded-full px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.04em]"
          style={{
            background: isLLM ? "rgba(201,146,74,0.16)" : "rgba(78,158,150,0.16)",
            color: isLLM ? "var(--color-secondary)" : "var(--color-primary)",
          }}
        >
          {isLLM ? `${judge.source} · non-reproducible` : "deterministic proxy · reproducible"}
        </span>
      </div>
      <dl className="m-0 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {dims.map(([label, v]) => (
          <div key={label} className="flex flex-col gap-1">
            <dt className="font-mono text-[10px] uppercase tracking-[0.04em] text-text-muted">{label}</dt>
            <dd className="m-0 font-sans text-[18px] font-semibold text-text tabular-nums">{pct(v)}</dd>
          </div>
        ))}
      </dl>
      {isLLM && (
        <p className="mt-3 font-sans text-[11px] leading-snug text-text-faint">
          {judge.llm_covered} of {judge.answers_scored} answers judged by the LLM; the rest use the deterministic proxy.
        </p>
      )}
    </section>
  );
}
