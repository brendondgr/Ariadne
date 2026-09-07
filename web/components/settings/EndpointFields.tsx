"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ApiLlmEndpointProbe, ApiLLMGroup, ApiModelList } from "@/lib/types";
import { getLlmModels } from "@/lib/api";
import { SHADOW } from "@/lib/ui";
import { ModelPicker } from "./ModelPicker";
import { TestConnection } from "./TestConnection";

/**
 * The endpoint block: provider, base URL, model, key, timeout, budgets.
 *
 * Deliberately one component used by BOTH the primary group and every per-stage
 * override. There is exactly one implementation of "ask this URL what it
 * serves", so a stage override gets Refresh and Test for free and the two can
 * never drift apart.
 */

export interface EndpointDraft {
  enabled: boolean;
  provider: string;
  base_url: string;
  model: string;
  api_key: string;
  timeout_s: string;
  max_tokens: string;
  thinking_budget: string;
}

export function groupToDraft(group: ApiLLMGroup): EndpointDraft {
  return {
    enabled: group.enabled,
    provider: group.provider,
    base_url: group.base_url,
    model: group.model,
    // Never prefilled — the server does not return it, and a fake placeholder
    // would invite someone to "confirm" a value they cannot see.
    api_key: "",
    timeout_s: String(group.timeout_s),
    max_tokens: String(group.max_tokens),
    thinking_budget: String(group.thinking_budget),
  };
}

/** Providers offered in the select, with the local default first. */
const PROVIDERS: { value: string; label: string; hint: string }[] = [
  {
    value: "openai-compatible",
    label: "OpenAI-compatible",
    hint: "vLLM, llama.cpp, LM Studio, DeepSeek, any /v1 server",
  },
  { value: "openai", label: "OpenAI", hint: "api.openai.com" },
  { value: "anthropic", label: "Anthropic", hint: "Claude" },
  { value: "gemini", label: "Google Gemini", hint: "generativelanguage" },
  { value: "ollama", label: "Ollama", hint: "localhost:11434/v1" },
];

/** Providers that will refuse a call without credentials. */
const NEEDS_KEY = new Set(["openai", "anthropic", "gemini"]);

const LABEL =
  "mb-1 block font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted";
const INPUT =
  "w-full rounded-md bg-bg px-2.5 py-1.5 text-[13px] text-text outline-none shadow-border focus:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]";

export function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  hint,
  invalid,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  hint?: string;
  invalid?: string;
}) {
  return (
    <label className="block">
      <span className={LABEL}>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={invalid ? true : undefined}
        className={INPUT}
        style={invalid ? { boxShadow: "rgba(201,146,74,0.7) 0 0 0 1px" } : undefined}
      />
      {invalid ? (
        <span className="mt-1 block font-mono text-[10.5px] text-secondary">{invalid}</span>
      ) : hint ? (
        <span className="mt-1 block font-mono text-[10.5px] text-text-muted">{hint}</span>
      ) : null}
    </label>
  );
}

export function EndpointFields({
  draft,
  onChange,
  scope,
  apiKeySet,
  showEnabled = true,
}: {
  draft: EndpointDraft;
  onChange: (patch: Partial<EndpointDraft>) => void;
  /** "default" for the primary group, else the stage name. */
  scope: string;
  apiKeySet: boolean;
  showEnabled?: boolean;
}) {
  const [models, setModels] = useState<ApiModelList | null>(null);
  const [loading, setLoading] = useState(false);

  // Every discovery request carries a sequence number and only the newest one is
  // allowed to write state. Without this, typing a URL races: a slow reply for
  // "http://gpu" can land after a fast one for "http://gpu-box:8000" and
  // repopulate the dropdown with the wrong server's models.
  const requestId = useRef(0);
  const abort = useRef<AbortController | null>(null);

  const probe = useCallback(
    (): ApiLlmEndpointProbe => ({
      scope,
      provider: draft.provider,
      base_url: draft.base_url,
      model: draft.model,
      // Only send a key the operator just typed; an empty string means "use the
      // one already stored", which the server understands.
      api_key: draft.api_key || undefined,
    }),
    [scope, draft.provider, draft.base_url, draft.model, draft.api_key],
  );

  const refresh = useCallback(async () => {
    const id = ++requestId.current;
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setLoading(true);
    try {
      const result = await getLlmModels(probe(), controller.signal);
      if (id === requestId.current) setModels(result);
    } catch {
      // A transport failure here is not an error state worth a banner: the
      // server reports unreachable endpoints in the body, so reaching this
      // branch means the request was aborted or the API itself is down, and the
      // picker simply stays a free-text field.
      if (id === requestId.current) setModels(null);
    } finally {
      if (id === requestId.current) setLoading(false);
    }
  }, [probe]);

  // Discover once when the block first renders with a usable URL. Not on every
  // keystroke: a fetch per character is what makes a settings modal feel frozen,
  // and Refresh is right there.
  const discovered = useRef(false);
  useEffect(() => {
    if (discovered.current || !draft.base_url.startsWith("http")) return;
    discovered.current = true;
    void refresh();
  }, [draft.base_url, refresh]);

  useEffect(() => () => abort.current?.abort(), []);

  const maxTokens = Number(draft.max_tokens);
  const budget = Number(draft.thinking_budget);
  const budgetInvalid =
    Number.isFinite(maxTokens) && Number.isFinite(budget) && budget > 0 && budget >= maxTokens
      ? `Must be below max tokens (${maxTokens || "?"}). Use 0 for no cap.`
      : undefined;

  const providerHint = PROVIDERS.find((p) => p.value === draft.provider)?.hint;
  const needsKey = NEEDS_KEY.has(draft.provider);

  return (
    <div className="flex flex-col gap-2.5">
      {showEnabled && (
        <button
          type="button"
          role="switch"
          aria-checked={draft.enabled}
          onClick={() => onChange({ enabled: !draft.enabled })}
          className="self-start rounded-full px-2.5 py-1 font-mono text-[10px] transition-colors"
          style={{
            background: draft.enabled ? "rgba(78,158,150,0.18)" : "rgba(138,158,152,0.12)",
            color: draft.enabled ? "var(--color-primary)" : "var(--color-text-muted)",
            boxShadow: SHADOW.border,
          }}
        >
          {draft.enabled ? "LLM enabled" : "LLM disabled"}
        </button>
      )}

      <label className="block">
        <span className={LABEL}>Provider</span>
        <select
          value={draft.provider}
          onChange={(e) => onChange({ provider: e.target.value })}
          className={INPUT}
        >
          {PROVIDERS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
        {providerHint && (
          <span className="mt-1 block font-mono text-[10.5px] text-text-muted">{providerHint}</span>
        )}
      </label>

      <Field
        label="Base URL"
        value={draft.base_url}
        onChange={(v) => onChange({ base_url: v })}
        placeholder="http://localhost:9090/v1"
      />

      <ModelPicker
        value={draft.model}
        onChange={(v) => onChange({ model: v })}
        result={models}
        loading={loading}
        onRefresh={refresh}
      />

      <Field
        label={needsKey ? "API key (required)" : "API key (optional)"}
        type="password"
        value={draft.api_key}
        onChange={(v) => onChange({ api_key: v })}
        placeholder={
          apiKeySet
            ? "•••••• (set — leave blank to keep)"
            : needsKey
              ? "required for this provider"
              : "not needed for a local server"
        }
      />

      <div className="grid grid-cols-2 gap-2.5">
        <Field
          label="Timeout (s)"
          value={draft.timeout_s}
          onChange={(v) => onChange({ timeout_s: v })}
          type="number"
        />
        <Field
          label="Max tokens"
          value={draft.max_tokens}
          onChange={(v) => onChange({ max_tokens: v })}
          type="number"
        />
      </div>

      <div className="grid grid-cols-2 items-start gap-2.5">
        <Field
          label="Thinking budget"
          value={draft.thinking_budget}
          onChange={(v) => onChange({ thinking_budget: v })}
          type="number"
          hint="0 = no cap"
          invalid={budgetInvalid}
        />
        <button
          type="button"
          onClick={() =>
            onChange({ thinking_budget: String(Math.max(0, Math.floor(maxTokens / 2) || 0)) })
          }
          disabled={!Number.isFinite(maxTokens) || maxTokens < 2}
          className="mt-[18px] rounded-md border-0 bg-transparent px-2.5 py-1.5 font-mono text-[11px] text-text-muted shadow-border transition-colors hover:text-primary disabled:opacity-40"
          title="Write half of max tokens as a real number — the budget never derives itself"
        >
          use half of max
        </button>
      </div>

      <TestConnection probe={probe} />
    </div>
  );
}

export { PROVIDERS, NEEDS_KEY };
