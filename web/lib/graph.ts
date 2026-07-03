/**
 * graph.ts — Pure, synchronous graph-data utilities for the force-graph canvas.
 * No React, no canvas imports — unit-testable in isolation.
 */

import type { GraphPayload, GraphNode } from "./types";

/* -------------------------------------------------------------------------- */
/* Palette                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * A curated set of ~10 muted colors fitting the Woven Dusk dark dusky
 * teal/amber theme. Avoid neon; prefer muted, dark-background-readable tones.
 *
 * Hex values:
 *  teal    #4e9e96  — primary brand
 *  amber   #c9924a  — secondary brand
 *  sage    #7aab8c  — muted green
 *  clay    #b07a5c  — muted terracotta
 *  slate   #6a82a8  — muted slate-blue
 *  rose    #a37884  — muted rose-taupe
 *  moss    #8da870  — muted olive/moss
 *  steel   #5b8fa0  — steel teal variant
 *  sand    #a09060  — warm sand
 *  lavender #8a7aab — muted lavender
 */
export const LABEL_PALETTE: string[] = [
  "#4e9e96", // teal
  "#c9924a", // amber
  "#7aab8c", // sage
  "#b07a5c", // clay
  "#6a82a8", // slate-blue
  "#a37884", // rose-taupe
  "#8da870", // moss
  "#5b8fa0", // steel teal
  "#a09060", // sand
  "#8a7aab", // lavender
];

/**
 * Deterministic stable hash of a string (djb2 variant) — always the same
 * result for the same input across renders and datasets.
 */
function hashLabel(label: string): number {
  let hash = 5381;
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 33) ^ label.charCodeAt(i);
  }
  // Convert to unsigned 32-bit integer before modulo so negatives don't sneak in
  return hash >>> 0;
}

/**
 * Map a node's primary `label` string to a palette color deterministically.
 * The same label always returns the same color, regardless of render order.
 */
export function labelColor(label: string): string {
  const idx = hashLabel(label) % LABEL_PALETTE.length;
  return LABEL_PALETTE[idx];
}

/* -------------------------------------------------------------------------- */
/* ForceGraph data types                                                       */
/* -------------------------------------------------------------------------- */

/**
 * Node shape passed to react-force-graph-2d.
 * force-graph mutates `source`/`target` link fields at runtime into object
 * references, but it NEVER mutates the node objects themselves beyond adding
 * x/y/vx/vy — which we intentionally leave untyped here so TypeScript doesn't
 * complain about the runtime additions.
 */
export interface FGNode extends GraphNode {
  color: string;
}

/**
 * Link shape passed to react-force-graph-2d.
 *
 * IMPORTANT: force-graph replaces `source`/`target` strings with node object
 * references after the first render. To preserve the original IDs for the
 * inspector, we store them separately as `sourceId`/`targetId`.
 */
export interface FGLink {
  id: string;
  source: string;
  target: string;
  type: string;
  /** Original source node id — survives force-graph's mutation of `source`. */
  sourceId: string;
  /** Original target node id — survives force-graph's mutation of `target`. */
  targetId: string;
}

export interface ForceGraphData {
  nodes: FGNode[];
  links: FGLink[];
}

/* -------------------------------------------------------------------------- */
/* toForceGraphData                                                            */
/* -------------------------------------------------------------------------- */

export interface ToForceGraphOpts {
  hiddenLabels?: Set<string>;
  hiddenTypes?: Set<string>;
}

/**
 * Convert a GraphPayload to the shape react-force-graph-2d expects.
 *
 * - Drops nodes whose `label` is in `hiddenLabels`.
 * - Drops links whose `type` is in `hiddenTypes` OR whose source/target node
 *   was dropped (prevents dangling-link errors in the force sim).
 * - Returns brand-new arrays each call so force-graph can mutate safely.
 */
export function toForceGraphData(
  payload: GraphPayload,
  opts: ToForceGraphOpts = {},
): ForceGraphData {
  const { hiddenLabels, hiddenTypes } = opts;

  // Build the filtered node list and an O(1) lookup set of surviving ids
  const nodes: FGNode[] = [];
  const survivingIds = new Set<string>();

  for (const node of payload.nodes) {
    if (hiddenLabels && hiddenLabels.has(node.label)) continue;
    survivingIds.add(node.id);
    nodes.push({
      ...node,
      color: labelColor(node.label),
    });
  }

  // Build the filtered link list — drop hidden types and dangling links
  const links: FGLink[] = [];

  for (const edge of payload.edges) {
    if (hiddenTypes && hiddenTypes.has(edge.type)) continue;
    // Drop if either endpoint was removed — no dangling links
    if (!survivingIds.has(edge.source)) continue;
    if (!survivingIds.has(edge.target)) continue;

    links.push({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      sourceId: edge.source,
      targetId: edge.target,
    });
  }

  return { nodes, links };
}
