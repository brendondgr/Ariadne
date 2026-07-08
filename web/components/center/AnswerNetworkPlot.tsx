"use client";

import { useMemo, useState } from "react";
import type { JoinPair, SynthesisView } from "@/lib/types";
import { labelColor, toForceGraphData } from "@/lib/graph";
import type { FGLink, FGNode } from "@/lib/graph";
import {
  synthesisToGraphPayload,
  isRenderableSubgraph,
  type EntityDetail,
} from "@/lib/synthesisGraph";
import { SHADOW } from "@/lib/ui";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { ElementInspector, type SelectedElement } from "@/components/graph/ElementInspector";
import { CloseIcon } from "@/components/ui/icons";

/** Whether the per-answer subgraph is worth plotting, plus its node/link counts.
 *  Lets the answer card decide if the Network Plot tab should appear (and its
 *  badge) without rendering the canvas. */
export function networkPlotMeta(synthesis: SynthesisView, joinPairs: JoinPair[]) {
  const payload = synthesisToGraphPayload(synthesis, joinPairs);
  return {
    renderable: isRenderableSubgraph(payload),
    nodeCount: payload.counts.nodes,
    linkCount: payload.counts.relationships,
  };
}

/** Deliverable #4 — the compact CAPEC–ATT&CK–mitigation network plot body
 *  (rendered inside the Network Plot tab).
 *
 *  Reuses the whole-graph force-graph engine (`toForceGraphData` + `GraphCanvas`)
 *  over a per-answer subgraph derived from the verified claims' provenance-exact
 *  edges. Nodes are enriched with the real names/descriptions the turn's
 *  federated evidence already carries (`entityDetails`), so clicking a node or
 *  edge opens an in-plot detail panel that names what was selected instead of
 *  showing a bare identifier. Renders nothing when there is nothing worth
 *  plotting. */
export function NetworkPlotBody({
  synthesis,
  joinPairs,
  entityDetails,
}: {
  synthesis: SynthesisView;
  joinPairs: JoinPair[];
  /** id → {name, label, properties} projected from the turn's federated evidence. */
  entityDetails?: Map<string, EntityDetail>;
}) {
  const [selected, setSelected] = useState<SelectedElement>(null);

  const payload = useMemo(
    () => synthesisToGraphPayload(synthesis, joinPairs, entityDetails),
    [synthesis, joinPairs, entityDetails],
  );
  const data = useMemo(() => toForceGraphData(payload), [payload]);

  // Nothing worth plotting (no edges / a single node) — the table and prose
  // still carry the answer.
  if (!isRenderableSubgraph(payload)) return null;

  const legend = Object.entries(payload.nodes_by_label);
  const abstentions = synthesis.abstentions.length;

  const selectedId =
    selected?.kind === "node"
      ? selected.node.id
      : selected?.kind === "link"
        ? selected.link.id
        : null;

  return (
    <div>
      {/* Legend: node type → palette color (shared with the canvas). */}
      <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1">
        {legend.map(([label, count]) => (
          <span key={label} className="inline-flex items-center gap-1.5 font-mono text-[10.5px] text-text-muted">
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: labelColor(label) }}
            />
            {label} <span className="text-text-soft">{count}</span>
          </span>
        ))}
      </div>

      {/* GraphCanvas positions itself absolutely — give it a sized, relative box.
          The inspector panel overlays the right edge of this same box so details
          stay inside the plot area (no layout shift, no separate surface). */}
      <div
        className="relative w-full overflow-hidden rounded-[8px]"
        style={{ height: 240, boxShadow: SHADOW.hairline }}
      >
        <GraphCanvas
          data={data}
          selectedId={selectedId}
          onSelectNode={(n: FGNode) => setSelected({ kind: "node", node: n })}
          onSelectLink={(l: FGLink) =>
            setSelected({ kind: "link", link: l as FGLink & Record<string, unknown> })
          }
          onBackgroundClick={() => setSelected(null)}
        />

        {selected && (
          <aside
            className="absolute inset-y-0 right-0 z-10 flex w-[220px] max-w-[70%] flex-col overflow-hidden bg-surface"
            style={{ boxShadow: "rgba(235,230,220,0.12) -1px 0 0 0, rgba(0,0,0,0.25) -8px 0 20px -8px" }}
            aria-label={`${selected.kind === "node" ? "Node" : "Edge"} details`}
          >
            <div
              className="flex flex-shrink-0 items-center justify-between px-3 pb-2 pt-2.5"
              style={{ boxShadow: "rgba(235,230,220,0.08) 0 1px 0 0" }}
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-text-muted">
                {selected.kind === "node" ? "Node" : "Edge"} details
              </span>
              <button
                type="button"
                onClick={() => setSelected(null)}
                aria-label="Close details"
                className="flex h-6 w-6 items-center justify-center rounded-md border-0 bg-transparent text-text-muted transition-colors hover:text-primary focus-visible:outline-none"
              >
                <CloseIcon size={13} />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3 pt-2.5">
              <ElementInspector selected={selected} />
            </div>
          </aside>
        )}
      </div>

      <p className="m-0 mt-2 font-mono text-[10.5px] leading-[1.5] text-text-muted">
        Each line links a CAPEC attack pattern to the ATT&CK technique it maps to.
        {" "}Click any node or line to see its name and details.
        {abstentions > 0 && ` Questions the sources couldn't answer aren't drawn here.`}
      </p>
    </div>
  );
}
