"use client";

/**
 * ElementInspector — displays properties of the currently-selected node or
 * edge. Purely presentational: no data fetching, no state.
 */

import { labelColor } from "@/lib/graph";
import type { GraphNode } from "@/lib/types";
import type { FGLink } from "@/lib/graph";

/* -------------------------------------------------------------------------- */
/* Types                                                                       */
/* -------------------------------------------------------------------------- */

export type SelectedElement =
  | { kind: "node"; node: GraphNode }
  | { kind: "link"; link: FGLink & Record<string, unknown> }
  | null;

interface ElementInspectorProps {
  selected: SelectedElement;
}

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

/* -------------------------------------------------------------------------- */
/* Sub-components                                                              */
/* -------------------------------------------------------------------------- */

function KVRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 py-[5px]" style={{ borderTop: "rgba(235,230,220,0.06) 1px solid" }}>
      <span
        className="font-mono text-[10px] uppercase tracking-[0.08em]"
        style={{ color: "var(--color-text-muted)" }}
      >
        {label}
      </span>
      <span
        className="break-all font-mono text-[11px] leading-relaxed"
        style={{ color: "var(--color-text-soft)" }}
      >
        {value}
      </span>
    </div>
  );
}

function LabelChip({ label }: { label: string }) {
  const color = labelColor(label);
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.06em]"
      style={{
        background: `${color}1a`, // ~10% opacity fill
        color,
        boxShadow: `${color}55 0 0 0 1px`,
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 flex-shrink-0 rounded-full"
        style={{ background: color }}
        aria-hidden="true"
      />
      {label}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Node inspector                                                              */
/* -------------------------------------------------------------------------- */

function NodeInspector({ node }: { node: GraphNode }) {
  const propEntries = Object.entries(node.properties ?? {});

  return (
    <div className="flex flex-col gap-2">
      {/* Name heading */}
      <p
        className="break-words font-sans text-[13px] font-medium leading-snug"
        style={{ color: "var(--color-text)", letterSpacing: "-0.01em" }}
      >
        {node.name || node.id}
      </p>

      {/* Label chips */}
      <div className="flex flex-wrap gap-1">
        {node.labels.map((lbl) => (
          <LabelChip key={lbl} label={lbl} />
        ))}
      </div>

      {/* ID */}
      <KVRow
        label="id"
        value={
          <span className="break-all">{node.id}</span>
        }
      />

      {/* Properties */}
      {propEntries.length > 0 && (
        <div className="flex flex-col">
          {propEntries.map(([key, val]) => (
            <KVRow key={key} label={key} value={formatValue(val)} />
          ))}
        </div>
      )}

      {propEntries.length === 0 && (
        <p
          className="font-mono text-[11px]"
          style={{ color: "var(--color-text-muted)", opacity: 0.6 }}
        >
          No properties.
        </p>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Link inspector                                                              */
/* -------------------------------------------------------------------------- */

function LinkInspector({ link }: { link: FGLink & Record<string, unknown> }) {
  // Collect extra fields beyond the known ones
  const knownKeys = new Set(["id", "source", "target", "type", "sourceId", "targetId", "index", "__indexColor", "__controlPoints"]);
  const extraEntries = Object.entries(link).filter(
    ([k]) => !knownKeys.has(k) && !k.startsWith("__"),
  );

  return (
    <div className="flex flex-col gap-2">
      {/* Type heading */}
      <p
        className="font-mono text-[12px] font-medium uppercase tracking-[0.06em]"
        style={{ color: "var(--color-primary)" }}
      >
        {link.type}
      </p>

      {/* Source → Target */}
      <div
        className="flex items-center gap-1.5 rounded-md px-2 py-1.5"
        style={{ background: "rgba(235,230,220,0.04)" }}
      >
        <span className="break-all font-mono text-[10px]" style={{ color: "var(--color-text-muted)" }}>
          {link.sourceId}
        </span>
        <span className="flex-shrink-0 font-mono text-[10px]" style={{ color: "var(--color-text-faint, rgba(235,230,220,0.3))" }}>
          →
        </span>
        <span className="break-all font-mono text-[10px]" style={{ color: "var(--color-text-muted)" }}>
          {link.targetId}
        </span>
      </div>

      {/* Edge id */}
      <KVRow label="id" value={<span className="break-all">{link.id}</span>} />

      {/* Extra fields */}
      {extraEntries.map(([k, v]) => (
        <KVRow key={k} label={k} value={formatValue(v)} />
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Main export                                                                 */
/* -------------------------------------------------------------------------- */

export function ElementInspector({ selected }: ElementInspectorProps) {
  if (!selected) {
    return (
      <p
        className="font-sans text-[12px] leading-relaxed"
        style={{ color: "var(--color-text-muted)", opacity: 0.7 }}
      >
        Select a node or edge to inspect its properties.
      </p>
    );
  }

  if (selected.kind === "node") {
    return <NodeInspector node={selected.node} />;
  }

  return <LinkInspector link={selected.link} />;
}
