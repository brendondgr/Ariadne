"use client";

import type { GraphDataset } from "@/lib/types";
import { useWorkbench } from "@/components/workbench/WorkbenchContext";

const DATASETS: { id: GraphDataset; label: string; sublabel: string }[] = [
  { id: "attack", label: "ATT&CK", sublabel: "Neo4j · attack" },
  { id: "capec",  label: "CAPEC",  sublabel: "Gremlin · capec" },
];

// Node/edge counts moved onto the search toolbar line (GraphSearchBar) so
// they sit beside the control that changes what is visible.
export function GraphSecondaryNav() {
  const { graphDataset, setGraphDataset } = useWorkbench();

  return (
    <nav
      className="flex flex-shrink-0 items-center justify-between bg-surface px-4"
      style={{ boxShadow: "rgba(235,230,220,0.10) 0 1px 0 0", minHeight: 48 }}
      aria-label="Graph dataset navigation"
    >
      {/* Dataset tabs */}
      <div
        role="tablist"
        aria-label="Select graph dataset"
        className="flex items-center gap-1"
      >
        {DATASETS.map(({ id, label, sublabel }) => {
          const active = graphDataset === id;
          return (
            <button
              key={id}
              role="tab"
              aria-selected={active}
              type="button"
              onClick={() => setGraphDataset(id)}
              className="flex flex-col items-start rounded-md px-3 py-2 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              style={
                active
                  ? {
                      background: "rgba(78,158,150,0.10)",
                      boxShadow: "rgba(78,158,150,0.45) 0 0 0 1px",
                      color: "var(--color-primary)",
                    }
                  : {
                      background: "transparent",
                      color: "var(--color-text-muted)",
                    }
              }
              onMouseEnter={(e) => {
                if (!active) {
                  (e.currentTarget as HTMLButtonElement).style.background = "rgba(235,230,220,0.04)";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                }
              }}
            >
              <span
                className="font-sans text-[13px] font-medium leading-none"
                style={{ letterSpacing: "-0.01em" }}
              >
                {label}
              </span>
              <span
                className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.08em]"
                style={{ color: active ? "rgba(78,158,150,0.7)" : "var(--color-text-muted)", opacity: active ? 1 : 0.7 }}
              >
                {sublabel}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
