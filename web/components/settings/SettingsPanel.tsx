"use client";

import { useEffect, useState } from "react";
import type { ApiConfig, ApiConfigUpdate, LLMStage } from "@/lib/types";
import { LLM_STAGES } from "@/lib/types";
import { getConfig, putConfig } from "@/lib/api";
import {
  LLM_FIELDS,
  budgetError,
  draftToUpdate,
  endpointSummary,
  stagesToUpdate,
} from "@/lib/llmSettings";
import { SHADOW } from "@/lib/ui";
import { CloseIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { EndpointFields, Field, groupToDraft, type EndpointDraft } from "./EndpointFields";
import { StageOverrides, type StageDraft } from "./StageOverrides";
import { InfraActions } from "./InfraActions";

interface OrchForm {
  checkpointer: boolean;
  recursion_limit: string;
  pipeline_timeout_s: string;
}

interface Form {
  llm: EndpointDraft;
  stages: Record<LLMStage, StageDraft>;
  connection: { neo4j_uri: string; neo4j_user: string; neo4j_password: string; gremlin_uri: string };
  orchestration: OrchForm;
}

function toForm(c: ApiConfig): Form {
  const stages = {} as Record<LLMStage, StageDraft>;
  for (const stage of LLM_STAGES) {
    const group = c.llm.stages[stage];
    stages[stage] = {
      // A stage counts as custom when it overrides ANY field. `inherited` comes
      // from the server, so this is read rather than inferred.
      custom: (group?.inherited.length ?? LLM_FIELDS.length) < LLM_FIELDS.length,
      fields: groupToDraft(group ?? c.llm.default),
    };
  }
  return {
    llm: groupToDraft(c.llm.default),
    stages,
    connection: {
      neo4j_uri: c.connection.neo4j_uri,
      neo4j_user: c.connection.neo4j_user,
      neo4j_password: "",
      gremlin_uri: c.connection.gremlin_uri,
    },
    orchestration: {
      checkpointer: c.orchestration.checkpointer,
      recursion_limit: String(c.orchestration.recursion_limit),
      pipeline_timeout_s: String(c.orchestration.pipeline_timeout_s),
    },
  };
}

/**
 * Modal for viewing and editing the LLM and connection settings.
 *
 * There is ONE language-model section. It used to be four — planner,
 * specialist, synthesis, evaluator — which read as flexibility and behaved as
 * confusion: the chat pane actually ran on a fifth group this modal never
 * showed, and two of the four on screen did nothing to a chat turn. An operator
 * could fill in an endpoint, flip toggles, and have no way to tell which one
 * made the model answer.
 *
 * Stage-level endpoints did not go away; they moved into a collapsed disclosure
 * that defaults to "inherit", so the common case is one section and the second
 * GPU is still two clicks away.
 */
export function SettingsPanel() {
  const { settingsOpen, setSettingsOpen } = useWorkbench();
  const [form, setForm] = useState<Form | null>(null);
  // The server's own view, kept alongside the editable draft. `inherited` and
  // `api_key_set` are facts only the server has, and inferring them from the
  // draft would be guessing.
  const [config, setConfig] = useState<ApiConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [passwordSet, setPasswordSet] = useState(false);

  // Load current config whenever the panel opens. State is only set inside the
  // async callbacks (after the await), never synchronously in the effect body.
  useEffect(() => {
    if (!settingsOpen) return;
    let active = true;
    const controller = new AbortController();
    getConfig(controller.signal)
      .then((cfg) => {
        if (!active) return;
        setConfig(cfg);
        setForm(toForm(cfg));
        setPasswordSet(cfg.connection.neo4j_password_set);
        setError(null);
        setSaved(false);
      })
      .catch((e: unknown) => {
        if (!active || controller.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [settingsOpen]);

  useEffect(() => {
    if (!settingsOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSettingsOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [settingsOpen, setSettingsOpen]);

  if (!settingsOpen) return null;

  const loading = form === null && error === null;

  const patchLlm = (patch: Partial<EndpointDraft>) =>
    setForm((f) => (f ? { ...f, llm: { ...f.llm, ...patch } } : f));

  const patchStage = (stage: LLMStage, patch: Partial<EndpointDraft>) =>
    setForm((f) =>
      f
        ? {
            ...f,
            stages: {
              ...f.stages,
              [stage]: { ...f.stages[stage], fields: { ...f.stages[stage].fields, ...patch } },
            },
          }
        : f,
    );

  const toggleStage = (stage: LLMStage, custom: boolean) =>
    setForm((f) =>
      f
        ? {
            ...f,
            stages: {
              ...f.stages,
              [stage]: {
                custom,
                // Switching to custom seeds the row from the primary endpoint, so
                // the operator edits from a working configuration instead of a
                // blank form. Switching back to inherit keeps the old values in
                // local state only — Save sends a CLEAR, never these numbers.
                fields: custom ? { ...f.llm } : f.stages[stage].fields,
              },
            },
          }
        : f,
    );
  const patchConn = (patch: Partial<Form["connection"]>) =>
    setForm((f) => (f ? { ...f, connection: { ...f.connection, ...patch } } : f));
  const patchOrch = (patch: Partial<OrchForm>) =>
    setForm((f) => (f ? { ...f, orchestration: { ...f.orchestration, ...patch } } : f));

  // A thinking budget at or above max tokens makes the model spend its whole
  // allowance reasoning and return empty content, which surfaces downstream as a
  // silent "LLM unavailable". The server rejects it with a 422; catching it here
  // means Save is disabled with the reason on screen rather than after a round
  // trip. Checked across the primary group and every custom stage.
  const validationError = form
    ? budgetError(form.llm.max_tokens, form.llm.thinking_budget) ??
      LLM_STAGES.map((stage) =>
        form.stages[stage]?.custom
          ? budgetError(form.stages[stage].fields.max_tokens, form.stages[stage].fields.thinking_budget)
          : null,
      ).find(Boolean) ??
      null
    : null;

  const save = async () => {
    if (!form || !config || validationError) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const update: ApiConfigUpdate = {
      llm: draftToUpdate(form.llm),
      llm_stages: stagesToUpdate(form.stages, config.llm.stages),
      connection: {
        neo4j_uri: form.connection.neo4j_uri,
        neo4j_user: form.connection.neo4j_user,
        gremlin_uri: form.connection.gremlin_uri,
        ...(form.connection.neo4j_password ? { neo4j_password: form.connection.neo4j_password } : {}),
      },
      orchestration: {
        checkpointer: form.orchestration.checkpointer,
        recursion_limit: Number(form.orchestration.recursion_limit),
        pipeline_timeout_s: Number(form.orchestration.pipeline_timeout_s),
      },
    };
    try {
      const cfg = await putConfig(update);
      setConfig(cfg);
      setForm(toForm(cfg));
      setPasswordSet(cfg.connection.neo4j_password_set);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-black/55 p-4 pt-[6vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Settings"
      onClick={() => setSettingsOpen(false)}
    >
      <div
        className="w-full max-w-[560px] rounded-[14px] bg-surface"
        style={{ boxShadow: SHADOW.answerCard }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-5 py-3.5"
          style={{ boxShadow: SHADOW.insetBottom }}
        >
          <h2 className="m-0 text-[15px] font-semibold text-text">Settings</h2>
          <button
            type="button"
            onClick={() => setSettingsOpen(false)}
            aria-label="Close settings"
            className="flex h-7 w-7 items-center justify-center rounded-md border-0 bg-transparent text-text-muted transition-colors hover:text-text"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="flex flex-col gap-4 px-5 py-4">
          {form ? (
            <>
              <fieldset
                className="m-0 rounded-lg border-0 p-3.5"
                style={{ boxShadow: SHADOW.border }}
              >
                <legend className="px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
                  Language model
                </legend>
                <p className="mt-1 mb-2.5 font-mono text-[10.5px] text-text-muted">
                  Every stage uses this unless it is overridden below.
                </p>
                <EndpointFields
                  draft={form.llm}
                  onChange={patchLlm}
                  scope="default"
                  apiKeySet={config?.llm.default.api_key_set ?? false}
                />
              </fieldset>

              {config && (
                <StageOverrides
                  stages={config.llm.stages}
                  drafts={form.stages}
                  onToggle={toggleStage}
                  onChange={patchStage}
                  defaultSummary={endpointSummary(form.llm)}
                />
              )}

              <fieldset className="m-0 rounded-lg border-0 p-3.5" style={{ boxShadow: SHADOW.border }}>
                <legend className="px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
                  Graph connection
                </legend>
                <div className="mt-2 flex flex-col gap-2.5">
                  <Field label="Neo4j URI" value={form.connection.neo4j_uri} onChange={(v) => patchConn({ neo4j_uri: v })} placeholder="bolt://localhost:5456" />
                  <div className="grid grid-cols-2 gap-2.5">
                    <Field label="Neo4j user" value={form.connection.neo4j_user} onChange={(v) => patchConn({ neo4j_user: v })} />
                    <Field
                      label="Neo4j password"
                      type="password"
                      value={form.connection.neo4j_password}
                      onChange={(v) => patchConn({ neo4j_password: v })}
                      placeholder={passwordSet ? "•••••• (set — leave blank to keep)" : "not set"}
                    />
                  </div>
                  <Field label="Gremlin URI" value={form.connection.gremlin_uri} onChange={(v) => patchConn({ gremlin_uri: v })} placeholder="ws://localhost:6455/gremlin" />
                </div>
              </fieldset>

              <fieldset className="m-0 rounded-lg border-0 p-3.5" style={{ boxShadow: SHADOW.border }}>
                <legend className="flex items-center gap-2 px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
                  Orchestration (LangGraph)
                  <button
                    type="button"
                    role="switch"
                    aria-checked={form.orchestration.checkpointer}
                    onClick={() => patchOrch({ checkpointer: !form.orchestration.checkpointer })}
                    className="rounded-full px-2 py-0.5 text-[10px] transition-colors"
                    style={{
                      background: form.orchestration.checkpointer ? "rgba(78,158,150,0.18)" : "rgba(138,158,152,0.12)",
                      color: form.orchestration.checkpointer ? "var(--color-primary)" : "var(--color-text-muted)",
                      boxShadow: SHADOW.border,
                    }}
                  >
                    {form.orchestration.checkpointer ? "checkpointer on" : "checkpointer off"}
                  </button>
                </legend>
                <div className="mt-2 grid grid-cols-2 gap-2.5">
                  <Field
                    label="Recursion limit"
                    value={form.orchestration.recursion_limit}
                    onChange={(v) => patchOrch({ recursion_limit: v })}
                    type="number"
                  />
                  <Field
                    label="Pipeline timeout (s)"
                    value={form.orchestration.pipeline_timeout_s}
                    onChange={(v) => patchOrch({ pipeline_timeout_s: v })}
                    type="number"
                  />
                </div>
              </fieldset>

              <InfraActions />
            </>
          ) : loading ? (
            <p className="py-6 text-center font-mono text-xs text-text-muted">Loading configuration…</p>
          ) : null}

          {error && (
            <p className="m-0 rounded-md px-3 py-2 font-mono text-[11.5px] text-secondary" style={{ boxShadow: "rgba(201,146,74,0.5) 0 0 0 1px" }}>
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 px-5 py-3.5" style={{ boxShadow: SHADOW.insetTop }}>
          {validationError && (
            <span className="mr-auto font-mono text-[11px] text-secondary">{validationError}</span>
          )}
          {saved && !validationError && (
            <span className="font-mono text-[11px] text-primary">Saved · applies to the next query</span>
          )}
          <button
            type="button"
            onClick={() => setSettingsOpen(false)}
            className="rounded-lg border-0 bg-transparent px-3.5 py-2 font-mono text-xs text-text-muted shadow-border transition-colors hover:text-text"
          >
            Close
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving || !form || !!validationError}
            className="rounded-lg border-0 bg-primary px-4 py-2 font-mono text-xs font-semibold text-bg transition-colors hover:bg-[#5bb0a7] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
