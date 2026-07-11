"use client";

import type { Accent, Plan } from "@/lib/types";
import { ACCENT } from "@/lib/ui";

/**
 * Planner step one, made legible: the classified analyst intent with the
 * evidence for it — **what** (the label), **why** (confidence, the cues that
 * fired, the rationale, and which classifier produced it), and **how** (the
 * routing consequence: which sources the plan targets and any declared join).
 * Renders only when the plan carries an intent (older plans simply omit it).
 */

const INTENT_ACCENT: Record<string, Accent> = {
  correlation: "teal",
  definitional: "teal",
  remediation: "amber",
  unsupported: "amber",
  traversal: "sage",
  enumeration: "sage",
  lookup: "sage",
};

const SOURCE_LABEL: Record<string, string> = {
  deterministic: "deterministic",
  llm: "LLM",
  fallback: "LLM→deterministic fallback",
};

function MicroLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[9.5px] uppercase tracking-[0.09em] text-text-muted">
      {children}
    </span>
  );
}

export function IntentCard({ plan }: { plan: Plan | null }) {
  const intent = plan?.intent;
  if (!plan || !intent) return null;

  const accent = ACCENT[INTENT_ACCENT[intent.label] ?? "sage"];
  const pct = Math.round(intent.confidence * 100);
  const sources = [...new Set(plan.sub_questions.map((s) => s.source))];
  const joins = plan.joins.map((j) => j.key);

  return (
    <div
      className="mx-[18px] mt-3 rounded-[9px] px-3.5 py-3"
      style={{ background: "rgba(14,15,17,0.5)", boxShadow: `${accent.ring} 0 0 0 1px` }}
    >
      {/* WHAT — the classified label + confidence + which classifier decided it */}
      <div className="flex flex-wrap items-center gap-2">
        <MicroLabel>Intent</MicroLabel>
        <span
          className="rounded-full px-2 py-[2px] font-mono text-[10.5px] uppercase tracking-[0.06em]"
          style={{ color: accent.fg, background: accent.tintBgStrong }}
        >
          {intent.label}
        </span>
        <span className="font-mono text-[10.5px]" style={{ color: accent.fg }}>
          {pct}%
        </span>
        <span className="font-mono text-[10px] text-text-soft">
          · via {SOURCE_LABEL[intent.source] ?? intent.source}
        </span>
      </div>

      {/* WHY — the rationale and the exact cues that fired */}
      {intent.rationale && (
        <p className="m-0 mt-2 text-[12.5px] leading-[1.5] text-text-soft">{intent.rationale}</p>
      )}
      {intent.cues.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <MicroLabel>cues</MicroLabel>
          {intent.cues.map((cue, i) => (
            <span
              key={i}
              className="rounded-[4px] px-1.5 py-[1px] font-mono text-[10px] text-[#c9c6bd]"
              style={{ background: "rgba(235,230,220,0.07)" }}
            >
              {cue}
            </span>
          ))}
        </div>
      )}

      {/* HOW — the routing consequence this intent produced */}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        <MicroLabel>routed</MicroLabel>
        <span className="font-mono text-[10.5px] text-text-soft">
          {sources.length ? sources.join(", ") : "—"}
        </span>
        {joins.length > 0 && (
          <>
            <span className="text-[10px] text-text-muted">·</span>
            <MicroLabel>join</MicroLabel>
            <span className="font-mono text-[10.5px]" style={{ color: ACCENT.teal.fg }}>
              {joins.join(", ")}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
