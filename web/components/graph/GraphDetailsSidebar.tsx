"use client";

/**
 * GraphDetailsSidebar — a right-hand panel that appears only when a node or edge
 * is selected in the graph canvas. It mirrors the left filter sidebar's width and
 * surface styling (with a left-edge divider) and hosts the ElementInspector.
 */

import { ElementInspector } from "./ElementInspector";
import type { SelectedElement } from "./ElementInspector";
import { CloseIcon } from "@/components/ui/icons";

interface GraphDetailsSidebarProps {
  selected: SelectedElement;
  onClose: () => void;
}

export function GraphDetailsSidebar({ selected, onClose }: GraphDetailsSidebarProps) {
  // The panel only exists while something is selected; the canvas reclaims the
  // width when nothing is inspected.
  if (!selected) return null;

  const heading = selected.kind === "node" ? "Node" : "Edge";

  return (
    <aside
      className="flex min-h-0 w-[288px] flex-shrink-0 flex-col overflow-hidden bg-surface"
      style={{ boxShadow: "rgba(235,230,220,0.10) -1px 0 0 0" }}
      aria-label={`${heading} details`}
    >
      <div
        className="flex flex-shrink-0 items-center justify-between px-4 pb-2 pt-4"
        style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
      >
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
          {heading} details
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close details"
          className="flex h-6 w-6 items-center justify-center rounded-md border-0 bg-transparent text-text-muted transition-colors hover:text-primary focus-visible:outline-none"
        >
          <CloseIcon size={14} />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-4 pt-3">
        <ElementInspector selected={selected} />
      </div>
    </aside>
  );
}
