"use client";

import { useMemo, useState } from "react";
import type { GraphPayload } from "@/lib/types";
import { labelColor, edgeTypeColorMap } from "@/lib/graph";

/* -------------------------------------------------------------------------- */
/* Props                                                                       */
/* -------------------------------------------------------------------------- */

interface GraphSidebarProps {
  payload: GraphPayload | null;
  hiddenLabels: Set<string>;
  hiddenTypes: Set<string>;
  onToggleLabel: (label: string, hidden: boolean) => void;
  onToggleType: (type: string, hidden: boolean) => void;
  onResetFilters: () => void;
}

/* -------------------------------------------------------------------------- */
/* Skeleton row                                                                */
/* -------------------------------------------------------------------------- */

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between gap-2 py-[5px]">
      <div
        className="h-[11px] w-24 rounded-[3px]"
        style={{ background: "rgba(235,230,220,0.06)", animation: "pulse 1.6s ease-in-out infinite" }}
      />
      <div
        className="h-[11px] w-8 rounded-[3px]"
        style={{ background: "rgba(235,230,220,0.06)", animation: "pulse 1.6s ease-in-out infinite" }}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Collapsible section                                                         */
/* -------------------------------------------------------------------------- */

function CollapsibleSection({
  label,
  children,
  defaultOpen = true,
}: {
  label: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="flex flex-col">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 py-[5px] text-left focus-visible:outline-none"
        aria-expanded={open}
      >
        <span
          className="flex-shrink-0 font-mono text-[10px] transition-transform"
          style={{
            color: "var(--color-text-muted)",
            transform: open ? "rotate(90deg)" : "rotate(0deg)",
            display: "inline-block",
          }}
          aria-hidden="true"
        >
          ▶
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-text-muted">
          {label}
        </span>
      </button>
      {open && <div className="flex flex-col pb-2">{children}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Checkbox row                                                                */
/* -------------------------------------------------------------------------- */

function FilterRow({
  id,
  label,
  count,
  checked,
  onToggle,
  color,
}: {
  id: string;
  label: string;
  count: number;
  checked: boolean;
  onToggle: (checked: boolean) => void;
  color?: string;
}) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center justify-between gap-2 py-[4px]"
      style={{ opacity: checked ? 1 : 0.5 }}
    >
      <div className="flex min-w-0 items-center gap-2">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onToggle(e.target.checked)}
          className="h-3 w-3 flex-shrink-0 cursor-pointer rounded-[2px] border-0 accent-teal-500"
          style={{ accentColor: color ?? "var(--color-primary)" }}
        />
        {color && (
          <span
            className="inline-block h-2 w-2 flex-shrink-0 rounded-full"
            style={{ background: color }}
            aria-hidden="true"
          />
        )}
        <span className="truncate font-mono text-[11px] text-text-soft">
          {label}
        </span>
      </div>
      <span
        className="flex-shrink-0 font-mono text-[11px] tabular-nums text-text-muted"
        style={{ fontFeatureSettings: '"tnum"' }}
      >
        {count.toLocaleString()}
      </span>
    </label>
  );
}

/* -------------------------------------------------------------------------- */
/* Main sidebar                                                                */
/* -------------------------------------------------------------------------- */

export function GraphSidebar({
  payload,
  hiddenLabels,
  hiddenTypes,
  onToggleLabel,
  onToggleType,
  onResetFilters,
}: GraphSidebarProps) {
  // Sort labels descending by count
  const labelEntries: [string, number][] = payload
    ? Object.entries(payload.nodes_by_label).sort(([, a], [, b]) => b - a)
    : [];

  // Derive edge type → count map from payload edges (computed once per payload)
  const edgeTypeCounts = useMemo<[string, number][]>(() => {
    if (!payload) return [];
    const counts = new Map<string, number>();
    for (const edge of payload.edges) {
      counts.set(edge.type, (counts.get(edge.type) ?? 0) + 1);
    }
    return [...counts.entries()].sort(([, a], [, b]) => b - a);
  }, [payload]);

  // Unique color per relationship type — shared with the canvas (same function).
  const typeColors = useMemo(
    () => edgeTypeColorMap(payload ? payload.edges.map((e) => e.type) : []),
    [payload],
  );

  const filtersActive =
    hiddenLabels.size > 0 || hiddenTypes.size > 0;

  return (
    <aside
      className="flex min-h-0 w-[260px] flex-shrink-0 flex-col overflow-hidden bg-surface"
      style={{ boxShadow: "rgba(235,230,220,0.10) 1px 0 0 0" }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Filters section — the sole content of the left sidebar              */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="flex flex-shrink-0 items-center justify-between px-4 pb-2 pt-4"
        style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
          Filters
        </span>
        {payload && filtersActive && (
          <button
            type="button"
            onClick={onResetFilters}
            className="font-mono text-[10px] uppercase tracking-[0.06em] transition-opacity hover:opacity-90 focus-visible:outline-none"
            style={{ color: "var(--color-secondary)" }}
          >
            Reset
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 pt-3">
        {!payload ? (
          <div className="flex flex-col gap-0.5">
            {Array.from({ length: 8 }).map((_, i) => (
              // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            {/* Node types */}
            {labelEntries.length > 0 && (
              <CollapsibleSection label="Node types">
                {labelEntries.map(([label, count]) => (
                  <FilterRow
                    key={label}
                    id={`filter-label-${label}`}
                    label={label}
                    count={count}
                    checked={!hiddenLabels.has(label)}
                    onToggle={(checked) => onToggleLabel(label, !checked)}
                    color={labelColor(label)}
                  />
                ))}
              </CollapsibleSection>
            )}

            {/* Relationship types */}
            {edgeTypeCounts.length > 0 && (
              <CollapsibleSection label="Relationship types">
                {edgeTypeCounts.map(([type, count]) => (
                  <FilterRow
                    key={type}
                    id={`filter-type-${type}`}
                    label={type}
                    count={count}
                    checked={!hiddenTypes.has(type)}
                    onToggle={(checked) => onToggleType(type, !checked)}
                    color={typeColors.get(type)}
                  />
                ))}
              </CollapsibleSection>
            )}

            {labelEntries.length === 0 && edgeTypeCounts.length === 0 && (
              <p className="font-mono text-[11px] text-text-muted">
                No filters available.
              </p>
            )}
          </div>
        )}
      </div>
    </aside>
  );
}
