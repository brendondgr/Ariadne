"use client";

import { useState } from "react";
import type { ApiLLMGroup, LLMStage } from "@/lib/types";
import { LLM_STAGES } from "@/lib/types";
import { SHADOW } from "@/lib/ui";
import { EndpointFields, type EndpointDraft } from "./EndpointFields";

/**
 * Per-stage endpoint overrides, collapsed by default.
 *
 * This is what lets one menu still express "the judge runs on the second GPU"
 * or "route with a cheap local model, answer with a hosted one", without the
 * modal becoming five endpoint forms again. Each row reads `inherit` and shows
 * what it is inheriting until someone deliberately overrides it, so the common
 * case — one model everywhere — stays a single section at a glance.
 *
 * Switching a row back to Inherit sends the field names to CLEAR, never the
 * default's current values. Writing those in would pin the stage to a snapshot
 * that silently stops tracking the default the next time it changes.
 */

const STAGE_LABEL: Record<LLMStage, string> = {
  planner: "Planner",
  specialist: "Specialist",
  synthesis: "Synthesis",
  conversation: "Conversation",
  eval: "Evaluator (judge)",
};

const STAGE_NOTE: Record<LLMStage, string> = {
  planner: "drafts the routing plan",
  specialist: "writes the graph queries",
  synthesis: "composes the answer's narrative",
  conversation: "the chat pane's visible reply",
  eval: "offline LLM-as-judge scoring",
};

export interface StageDraft {
  custom: boolean;
  fields: EndpointDraft;
}

export function StageOverrides({
  stages,
  drafts,
  onToggle,
  onChange,
  defaultSummary,
}: {
  stages: Record<LLMStage, ApiLLMGroup>;
  drafts: Record<LLMStage, StageDraft>;
  onToggle: (stage: LLMStage, custom: boolean) => void;
  onChange: (stage: LLMStage, patch: Partial<EndpointDraft>) => void;
  defaultSummary: string;
}) {
  const [open, setOpen] = useState(false);
  const overrideCount = LLM_STAGES.filter((s) => drafts[s]?.custom).length;

  return (
    <fieldset className="m-0 rounded-lg border-0 p-3.5" style={{ boxShadow: SHADOW.border }}>
      <legend className="px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
        Per-stage endpoints
      </legend>

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-md border-0 bg-transparent px-0 py-1 text-left transition-colors hover:text-text"
      >
        <span className="font-mono text-[11.5px] text-text-muted">
          {overrideCount === 0
            ? "All five stages follow the model above"
            : `${overrideCount} stage${overrideCount === 1 ? "" : "s"} using a different endpoint`}
        </span>
        <span className="font-mono text-[10px] text-text-muted">{open ? "hide" : "show"}</span>
      </button>

      {open && (
        <div className="mt-2.5 flex flex-col gap-2.5">
          {LLM_STAGES.map((stage) => {
            const draft = drafts[stage];
            if (!draft) return null;
            return (
              <div
                key={stage}
                className="rounded-md p-2.5"
                style={{ boxShadow: SHADOW.hairline }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[12.5px] text-text">{STAGE_LABEL[stage]}</div>
                    <div className="font-mono text-[10.5px] text-text-muted">
                      {STAGE_NOTE[stage]}
                    </div>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Choice
                      active={!draft.custom}
                      onClick={() => onToggle(stage, false)}
                      label="inherit"
                    />
                    <Choice
                      active={draft.custom}
                      onClick={() => onToggle(stage, true)}
                      label="custom"
                    />
                  </div>
                </div>

                {draft.custom ? (
                  <div className="mt-2.5">
                    <EndpointFields
                      draft={draft.fields}
                      onChange={(patch) => onChange(stage, patch)}
                      scope={stage}
                      apiKeySet={stages[stage]?.api_key_set ?? false}
                      showEnabled={false}
                    />
                  </div>
                ) : (
                  <div className="mt-1.5 font-mono text-[10.5px] text-text-muted">
                    → {defaultSummary}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </fieldset>
  );
}

function Choice({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="rounded-full px-2 py-0.5 font-mono text-[10px] transition-colors"
      style={{
        background: active ? "rgba(78,158,150,0.18)" : "transparent",
        color: active ? "var(--color-primary)" : "var(--color-text-muted)",
        boxShadow: SHADOW.border,
      }}
    >
      {label}
    </button>
  );
}
