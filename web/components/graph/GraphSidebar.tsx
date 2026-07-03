"use client";

import type { GraphPayload } from "@/lib/types";

interface GraphSidebarProps {
  payload: GraphPayload | null;
}

/** Skeleton row for loading state */
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

export function GraphSidebar({ payload }: GraphSidebarProps) {
  // Sort labels descending by count
  const labelEntries: [string, number][] = payload
    ? Object.entries(payload.nodes_by_label).sort(([, a], [, b]) => b - a)
    : [];

  return (
    <aside
      className="flex min-h-0 w-[260px] flex-shrink-0 flex-col overflow-hidden bg-surface"
      style={{ boxShadow: "rgba(235,230,220,0.10) 1px 0 0 0" }}
    >
      {/* Graph legend section */}
      <div className="flex min-h-0 flex-col border-b border-transparent" style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}>
        <div className="flex items-center justify-between px-4 pb-2 pt-4">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
            Graph
          </span>
          {payload && (
            <span className="font-mono text-[10px] tabular-nums text-text-muted" style={{ fontFeatureSettings: '"tnum"' }}>
              {payload.backend}
            </span>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
          {!payload ? (
            // Loading skeleton
            <div className="flex flex-col gap-0.5">
              {Array.from({ length: 6 }).map((_, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: skeleton placeholders have no meaningful key
                <SkeletonRow key={i} />
              ))}
            </div>
          ) : labelEntries.length === 0 ? (
            <p className="pt-1 font-mono text-[11px] text-text-muted">
              No node labels found.
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5" aria-label="Node labels">
              {labelEntries.map(([label, count]) => (
                <li key={label} className="flex items-center justify-between gap-2 py-[5px]">
                  <div className="flex items-center gap-2">
                    {/* Color swatch — neutral now, wired to canvas palette in the next step */}
                    <span
                      className="inline-block h-2 w-2 flex-shrink-0 rounded-full"
                      style={{ background: "rgba(235,230,220,0.25)" }}
                      aria-hidden="true"
                    />
                    <span className="font-mono text-[11px] text-text-soft">
                      {label}
                    </span>
                  </div>
                  <span
                    className="font-mono text-[11px] tabular-nums text-text-muted"
                    style={{ fontFeatureSettings: '"tnum"' }}
                  >
                    {count.toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Inspection section (placeholder — real inspector arrives with the canvas step) */}
      <div className="flex flex-col px-4 pb-4 pt-4">
        <span className="pb-2 font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
          Inspection
        </span>
        <p className="font-sans text-[12px] leading-relaxed text-text-muted" style={{ opacity: 0.7 }}>
          Select a node or edge to see its properties.
        </p>
      </div>
    </aside>
  );
}
