"use client";

import { useEffect, useState } from "react";
import type { ApiConfig, ApiConfigUpdate, ApiLLMGroup } from "@/lib/types";
import { getConfig, putConfig } from "@/lib/api";
import { SHADOW } from "@/lib/ui";
import { CloseIcon } from "@/components/ui/icons";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";
import { InfraActions } from "./InfraActions";

type Agent = "planner" | "specialist" | "synthesis" | "eval";

const AGENTS: Agent[] = ["planner", "specialist", "synthesis", "eval"];

interface GroupForm {
  enabled: boolean;
  base_url: string;
  model: string;
  timeout_s: string;
  max_tokens: string;
}

interface Form {
  planner: GroupForm;
  specialist: GroupForm;
  synthesis: GroupForm;
  eval: GroupForm;
  connection: { neo4j_uri: string; neo4j_user: string; neo4j_password: string; gremlin_uri: string };
}

function toForm(c: ApiConfig): Form {
  const group = (g: ApiLLMGroup): GroupForm => ({
    enabled: g.enabled,
    base_url: g.base_url,
    model: g.model,
    timeout_s: String(g.timeout_s),
    max_tokens: String(g.max_tokens),
  });
  return {
    planner: group(c.llm.planner),
    specialist: group(c.llm.specialist),
    synthesis: group(c.llm.synthesis),
    eval: group(c.llm.eval),
    connection: {
      neo4j_uri: c.connection.neo4j_uri,
      neo4j_user: c.connection.neo4j_user,
      neo4j_password: "",
      gremlin_uri: c.connection.gremlin_uri,
    },
  };
}

/** Human labels for the LLM sections (eval = the LLM-as-judge). */
const AGENT_LABEL: Record<Agent, string> = {
  planner: "planner",
  specialist: "specialist",
  synthesis: "synthesis",
  eval: "evaluator (judge)",
};

const LABEL = "mb-1 block font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted";
const INPUT =
  "w-full rounded-md bg-bg px-2.5 py-1.5 text-[13px] text-text outline-none shadow-border focus:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]";

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className={LABEL}>{label}</span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={INPUT}
      />
    </label>
  );
}

function LLMSection({
  agent,
  form,
  onChange,
}: {
  agent: Agent;
  form: GroupForm;
  onChange: (patch: Partial<GroupForm>) => void;
}) {
  return (
    <fieldset className="m-0 rounded-lg border-0 p-3.5" style={{ boxShadow: SHADOW.border }}>
      <legend className="flex items-center gap-2 px-1 font-mono text-[11px] uppercase tracking-[0.08em] text-text-soft">
        {AGENT_LABEL[agent]} LLM
        <button
          type="button"
          role="switch"
          aria-checked={form.enabled}
          onClick={() => onChange({ enabled: !form.enabled })}
          className="rounded-full px-2 py-0.5 text-[10px] transition-colors"
          style={{
            background: form.enabled ? "rgba(78,158,150,0.18)" : "rgba(138,158,152,0.12)",
            color: form.enabled ? "var(--color-primary)" : "var(--color-text-muted)",
            boxShadow: SHADOW.border,
          }}
        >
          {form.enabled ? "enabled" : "disabled"}
        </button>
      </legend>
      <div className="mt-2 flex flex-col gap-2.5">
        <Field label="Base URL" value={form.base_url} onChange={(v) => onChange({ base_url: v })} placeholder="http://localhost:9090/v1" />
        <Field label="Model" value={form.model} onChange={(v) => onChange({ model: v })} placeholder="default-model" />
        <div className="grid grid-cols-2 gap-2.5">
          <Field label="Timeout (s)" value={form.timeout_s} onChange={(v) => onChange({ timeout_s: v })} type="number" />
          <Field label="Max tokens" value={form.max_tokens} onChange={(v) => onChange({ max_tokens: v })} type="number" />
        </div>
      </div>
    </fieldset>
  );
}

/** Modal for viewing/editing the env-backed LLM and connection settings. */
export function SettingsPanel() {
  const { settingsOpen, setSettingsOpen } = useWorkbench();
  const [form, setForm] = useState<Form | null>(null);
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

  const patchGroup = (agent: Agent, patch: Partial<GroupForm>) =>
    setForm((f) => (f ? { ...f, [agent]: { ...f[agent], ...patch } } : f));
  const patchConn = (patch: Partial<Form["connection"]>) =>
    setForm((f) => (f ? { ...f, connection: { ...f.connection, ...patch } } : f));

  const groupUpdate = (g: GroupForm) => ({
    enabled: g.enabled,
    base_url: g.base_url,
    model: g.model,
    timeout_s: Number(g.timeout_s),
    max_tokens: Number(g.max_tokens),
  });

  const save = async () => {
    if (!form) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const update: ApiConfigUpdate = {
      planner: groupUpdate(form.planner),
      specialist: groupUpdate(form.specialist),
      synthesis: groupUpdate(form.synthesis),
      eval: groupUpdate(form.eval),
      connection: {
        neo4j_uri: form.connection.neo4j_uri,
        neo4j_user: form.connection.neo4j_user,
        gremlin_uri: form.connection.gremlin_uri,
        ...(form.connection.neo4j_password ? { neo4j_password: form.connection.neo4j_password } : {}),
      },
    };
    try {
      const cfg = await putConfig(update);
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
              {AGENTS.map((agent) => (
                <LLMSection
                  key={agent}
                  agent={agent}
                  form={form[agent]}
                  onChange={(p) => patchGroup(agent, p)}
                />
              ))}

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
          {saved && <span className="font-mono text-[11px] text-primary">Saved · applies to the next query</span>}
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
            disabled={saving || !form}
            className="rounded-lg border-0 bg-primary px-4 py-2 font-mono text-xs font-semibold text-bg transition-colors hover:bg-[#5bb0a7] disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
