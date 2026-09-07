/**
 * Pure helpers behind the settings modal's LLM section.
 *
 * Kept out of the components so the two things most likely to be got wrong —
 * what an "inherit" toggle actually sends, and whether a thinking budget is
 * legal — are testable without rendering anything.
 */

import type {
  ApiLLMGroup,
  ApiLLMGroupUpdate,
  LLMField,
  LLMStage,
} from "./types";
import type { EndpointDraft } from "@/components/settings/EndpointFields";

/** Every field a stage can override. */
export const LLM_FIELDS: LLMField[] = [
  "enabled",
  "provider",
  "base_url",
  "model",
  "api_key",
  "timeout_s",
  "max_tokens",
  "thinking_budget",
];

/**
 * `max_tokens` and `thinking_budget` move together.
 *
 * A stage that overrode only one of them would run a budget sized against the
 * other scope's token cap, which is exactly the invariant the pair exists to
 * hold. The server couples them too; this mirrors it so the UI never shows a
 * state the server would reject.
 */
export const COUPLED: LLMField[] = ["max_tokens", "thinking_budget"];

/** Fields a stage clears to go back to following the primary group. */
export const INHERITABLE: LLMField[] = LLM_FIELDS.filter((f) => f !== "enabled");

export function budgetError(maxTokens: string, thinkingBudget: string): string | null {
  const max = Number(maxTokens);
  const budget = Number(thinkingBudget);
  if (!Number.isFinite(max) || !Number.isFinite(budget)) return null;
  if (budget < 0) return "Thinking budget must not be negative.";
  // 0 means "send no cap" — what every run predating the cap did — so it stays
  // legal regardless of max_tokens.
  if (budget === 0) return null;
  if (budget >= max) {
    return `Thinking budget (${budget}) must be less than max tokens (${max}). Use 0 for no cap.`;
  }
  return null;
}

/** Turn a draft into the partial update the API expects. */
export function draftToUpdate(draft: EndpointDraft): ApiLLMGroupUpdate {
  const update: ApiLLMGroupUpdate = {
    enabled: draft.enabled,
    provider: draft.provider,
    base_url: draft.base_url,
    model: draft.model,
    timeout_s: Number(draft.timeout_s),
    max_tokens: Number(draft.max_tokens),
    thinking_budget: Number(draft.thinking_budget),
  };
  // An empty key means "keep the stored one". Sending "" would be indistinguishable
  // from clearing it, and clearing goes through `inherit`.
  if (draft.api_key) update.api_key = draft.api_key;
  return update;
}

/**
 * Build the `llm_stages` payload from the per-stage drafts.
 *
 * A stage marked `custom` sends its values. A stage marked `inherit` sends the
 * field names to CLEAR — never the primary group's current values, which would
 * pin it to a snapshot that stops tracking the default.
 */
export function stagesToUpdate(
  drafts: Record<LLMStage, { custom: boolean; fields: EndpointDraft }>,
  original: Record<LLMStage, ApiLLMGroup>,
): Partial<Record<LLMStage, ApiLLMGroupUpdate>> {
  const out: Partial<Record<LLMStage, ApiLLMGroupUpdate>> = {};
  for (const stage of Object.keys(drafts) as LLMStage[]) {
    const draft = drafts[stage];
    const wasCustom = (original[stage]?.inherited.length ?? 0) < LLM_FIELDS.length;

    if (draft.custom) {
      out[stage] = draftToUpdate(draft.fields);
    } else if (wasCustom) {
      // Only emit a clear for a stage that actually had an override; sending
      // `inherit` for an already-inheriting stage is noise in the .env.
      out[stage] = { inherit: INHERITABLE };
    }
  }
  return out;
}

/** One-line summary of the primary endpoint, shown on an inheriting stage row. */
export function endpointSummary(draft: EndpointDraft): string {
  let host = draft.base_url;
  try {
    host = new URL(draft.base_url).host || draft.base_url;
  } catch {
    // A half-typed URL is normal while editing; show it as-is rather than
    // blanking the line.
  }
  return `${draft.model || "(no model)"} @ ${host}`;
}
