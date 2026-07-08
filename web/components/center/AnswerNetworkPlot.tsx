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
import { CollapsibleSection } from "./CollapsibleSection";

/** Deliverable #4 — the compact CAPEC–ATT&CK–mitigation network plot.
 *
 *  Reuses the whole-graph force-graph engine (`toForceGraphData` + `GraphCanvas`)
 *  over a per-answer subgraph derived from the verified claims. Today the edges
 *  are INFERRED (join index + within-claim co-citation), so the plot is labelled
 *  "derived" — it must never read as provenance-exact ground truth. Option B
 *  swaps the edge source for explicit composer edges and relabels it. */
export function AnswerNetworkPlot({
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
  const nodeCount = payload.counts.nodes;
  const linkCount = payload.counts.relationships;

  return (
    <CollapsibleSection
      label="Network plot"
      count={`${nodeCount} node${nodeCount === 1 ? "" : "s"} · ${linkCount} link${linkCount === 1 ? "" : "s"}`}
    >
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
    </CollapsibleSection>
  );
}
