"use client";

/**
 * GraphCanvas — renders the force-directed graph using react-force-graph-2d.
 *
 * SSR safety: react-force-graph-2d touches `window` at import time, so we
 * load it via next/dynamic with { ssr: false }. The module is never evaluated
 * on the server.
 *
 * Container sizing: a ResizeObserver in useEffect measures the wrapper div
 * and passes width/height to ForceGraph2D. No measurement happens during SSR
 * or before mount.
 */

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ForceGraphProps, NodeObject } from "react-force-graph-2d";
import type { ForceGraphData, FGNode, FGLink } from "@/lib/graph";

// Dynamically import the canvas component — ssr:false prevents the library
// from touching `window` during Next.js server rendering.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => null,
});

/* -------------------------------------------------------------------------- */
/* Types                                                                       */
/* -------------------------------------------------------------------------- */

interface GraphCanvasProps {
  data: ForceGraphData;
  onSelectNode: (node: FGNode) => void;
  onSelectLink: (link: FGLink) => void;
  /** Id of the currently-selected element for highlight ring. */
  selectedId?: string | null;
}

/* -------------------------------------------------------------------------- */
/* Component                                                                   */
/* -------------------------------------------------------------------------- */

export function GraphCanvas({
  data,
  onSelectNode,
  onSelectLink,
  selectedId,
}: GraphCanvasProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState<{ width: number; height: number } | null>(null);

  // Measure container with ResizeObserver — only runs client-side after mount
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;

    const measure = () => {
      const { width, height } = el.getBoundingClientRect();
      if (width > 0 && height > 0) {
        setDims({ width, height });
      }
    };

    measure(); // initial

    const ro = new ResizeObserver(measure);
    ro.observe(el);

    return () => {
      ro.disconnect();
    };
  }, []);

  // Node canvas object — draws the node plus a selection ring when selected.
  // Must be defined before any early returns to satisfy rules-of-hooks.
  // Type matches ForceGraphProps["nodeCanvasObject"] which expects NodeObject<{}>.
  const nodeCanvasObject = useCallback(
    (node: NodeObject<{ color?: string; name?: string }>, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const r = 4; // nodeRelSize=4 radius
      const x = node.x ?? 0;
      const y = node.y ?? 0;
      const nodeId = typeof node.id === "string" ? node.id : String(node.id ?? "");

      // Selection ring
      if (selectedId != null && nodeId === selectedId) {
        ctx.beginPath();
        ctx.arc(x, y, r + 2.5 / globalScale, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(235,230,220,0.18)";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x, y, r + 2.5 / globalScale, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(235,230,220,0.7)";
        ctx.lineWidth = 1 / globalScale;
        ctx.stroke();
      }

      // Node dot
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = node.color ?? "#4e9e96";
      ctx.fill();
    },
    [selectedId],
  ) satisfies NonNullable<ForceGraphProps["nodeCanvasObject"]>;

  // Don't render if empty — parent handles the empty state
  if (data.nodes.length === 0) return null;

  return (
    <div
      ref={wrapperRef}
      style={{ width: "100%", height: "100%", position: "absolute", inset: 0 }}
      aria-label="Force-directed graph canvas"
    >
      {dims && (
        <ForceGraph2D
          graphData={data}
          width={dims.width}
          height={dims.height}
          backgroundColor="#15191a"
          // Nodes
          nodeColor={(n) => (n as FGNode).color}
          nodeRelSize={4}
          nodeLabel={(n) => (n as FGNode).name || (n as FGNode).id}
          nodeCanvasObjectMode={() => "replace"}
          nodeCanvasObject={nodeCanvasObject}
          // Links — subtle, low opacity for ~21k edge datasets
          linkColor={() => "rgba(138,158,152,0.18)"}
          linkWidth={0.5}
          // No directional arrows / particles — performance
          // Simulation settling
          cooldownTicks={100}
          warmupTicks={20}
          cooldownTime={4000}
          // Disable drag for large graphs — panning is sufficient
          enableNodeDrag={false}
          // Selection callbacks
          onNodeClick={(n) => onSelectNode(n as FGNode)}
          onLinkClick={(l) => onSelectLink(l as unknown as FGLink)}
        />
      )}
    </div>
  );
}
