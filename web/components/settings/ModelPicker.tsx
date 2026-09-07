"use client";

import type { ApiModelList } from "@/lib/types";
import { SHADOW } from "@/lib/ui";

/**
 * The model field: a dropdown of what the server actually serves, a Refresh
 * button, and a free-text fallback that always remains usable.
 *
 * The field stays an input rather than becoming a pure <select> on purpose.
 * Discovery can legitimately return nothing — a gateway that proxies completions
 * but not `/models`, an Azure-style deployment, a server that is momentarily
 * down — and a picker that offers no way to type a name in those cases is worse
 * than the plain text box it replaced.
 *
 * The three empty states are kept distinct because they need three different
 * fixes, and telling someone to check their port when the server answered fine
 * wastes their afternoon.
 */
export function ModelPicker({
  value,
  onChange,
  result,
  loading,
  onRefresh,
}: {
  value: string;
  onChange: (v: string) => void;
  result: ApiModelList | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const models = result?.models ?? [];
  const listId = `models-${result?.base_url ?? "none"}`;

  return (
    <div className="block">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          Model
        </span>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="rounded-md border-0 bg-transparent px-2 py-0.5 font-mono text-[10px] text-text-muted shadow-border transition-colors hover:text-primary disabled:opacity-40"
          title="Ask this endpoint what models it serves"
        >
          {loading ? "refreshing…" : "refresh"}
        </button>
      </div>

      <input
        list={models.length ? listId : undefined}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="default-model"
        className="w-full rounded-md bg-bg px-2.5 py-1.5 text-[13px] text-text outline-none shadow-border focus:shadow-[rgba(78,158,150,0.6)_0_0_0_1px]"
      />
      {models.length > 0 && (
        <datalist id={listId}>
          {models.map((m) => (
            <option key={m.id} value={m.id} label={m.label} />
          ))}
        </datalist>
      )}

      <ModelHint result={result} loading={loading} count={models.length} />
    </div>
  );
}

function ModelHint({
  result,
  loading,
  count,
}: {
  result: ApiModelList | null;
  loading: boolean;
  count: number;
}) {
  if (loading) {
    return <Hint tone="muted">Asking the endpoint what it serves…</Hint>;
  }
  if (!result) {
    return <Hint tone="muted">Refresh to list the models this endpoint serves.</Hint>;
  }
  if (count > 0) {
    return (
      <Hint tone="ok">
        {count} model{count === 1 ? "" : "s"} available — start typing to filter.
      </Hint>
    );
  }
  // Every remaining case is an empty state with its own fix, carried verbatim
  // from the server so the operator sees the real reason rather than a summary.
  return <Hint tone={result.state === "unreachable" ? "warn" : "muted"}>{result.reason}</Hint>;
}

function Hint({ tone, children }: { tone: "ok" | "warn" | "muted"; children: React.ReactNode }) {
  const color =
    tone === "ok"
      ? "var(--color-primary)"
      : tone === "warn"
        ? "var(--color-secondary)"
        : "var(--color-text-muted)";
  return (
    <span className="mt-1 block font-mono text-[10.5px]" style={{ color }}>
      {children}
    </span>
  );
}

export { SHADOW };
