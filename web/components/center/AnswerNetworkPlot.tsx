"use client";

import { useMemo, useState } from "react";
import type { JoinPair, SynthesisView } from "@/lib/types";
import { labelColor, toForceGraphData } from "@/lib/graph";
import {
  synthesisToGraphPayload,
  isRenderableSubgraph,
} from "@/lib/synthesisGraph";
import { SHADOW } from "@/lib/ui";
import { GraphCanvas } from "@/components/graph/GraphCanvas";

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
 *  edges. Renders nothing when there is nothing worth plotting. */
export function NetworkPlotBody({
  synthesis,
  joinPairs,
}: {
  synthesis: SynthesisView;
  joinPairs: JoinPair[];
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const payload = useMemo(
    () => synthesisToGraphPayload(synthesis, joinPairs),
    [synthesis, joinPairs],
  );
  const data = useMemo(() => toForceGraphData(payload), [payload]);

  // Nothing worth plotting (no edges / a single node) — the table and prose
  // still carry the answer.
  if (!isRenderableSubgraph(payload)) return null;

  const legend = Object.entries(payload.nodes_by_label);
  const abstentions = synthesis.abstentions.length;

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

      {/* GraphCanvas positions itself absolutely — give it a sized, relative box. */}
      <div
        className="relative w-full overflow-hidden rounded-[8px]"
        style={{ height: 240, boxShadow: SHADOW.hairline }}
      >
        <GraphCanvas
          data={data}
          selectedId={selectedId}
          onSelectNode={(n) => setSelectedId(n.id)}
          onSelectLink={() => setSelectedId(null)}
        />
      </div>

      <p className="m-0 mt-2 font-mono text-[10.5px] leading-[1.5] text-text-muted">
        Each line links a CAPEC attack pattern to the ATT&CK technique it maps to.
        {abstentions > 0 && ` Questions the sources couldn't answer aren't drawn here.`}
      </p>
    </div>
  );
}
