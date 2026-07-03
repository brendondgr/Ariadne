/**
 * graph.ts — Pure, synchronous graph-data utilities for the force-graph canvas.
 * No React, no canvas imports — unit-testable in isolation.
 */

import type { GraphPayload, GraphNode } from "./types";

/* -------------------------------------------------------------------------- */
/* Palette                                                                     */
/* -------------------------------------------------------------------------- */

/**
 * A curated set of 16 muted, hue-separated colors fitting the Woven Dusk dark
 * dusky teal/amber theme. Avoid neon; prefer muted, dark-background-readable
 * tones. 16 entries so the largest relationship-type set (CAPEC has 14) gets a
 * unique color with no wraparound collisions.
 */
export const LABEL_PALETTE: string[] = [
  "#4e9e96", // teal (primary brand)
  "#c9924a", // amber (secondary brand)
  "#7aab8c", // sage
  "#b07a5c", // clay / terracotta
  "#6a82a8", // slate-blue
  "#a37884", // rose-taupe
  "#8da870", // moss
  "#5b8fa0", // steel teal
  "#a09060", // sand
  "#8a7aab", // lavender
  "#c07d76", // coral
  "#9a9a55", // olive
  "#6aa46f", // green
  "#7b7fbf", // indigo
  "#a778b0", // orchid
  "#bd77a0", // pink
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

/**
 * Assign a UNIQUE palette color to each distinct relationship type.
 *
 * Unlike the hash-based `labelColor`, this maps the sorted set of types to
 * palette slots by index, so no two relationship types collide (up to
 * `LABEL_PALETTE.length` types). The result is stable for a given set of types
 * because the input is sorted before assignment. Both the sidebar legend and the
 * canvas derive their colors from this single function so they always agree.
 */
export function edgeTypeColorMap(types: Iterable<string>): Map<string, string> {
  const unique = [...new Set(types)].sort();
  const map = new Map<string, string>();
  unique.forEach((type, i) => {
    map.set(type, LABEL_PALETTE[i % LABEL_PALETTE.length]);
  });
  return map;
}

/** Convert a `#rrggbb` hex color to an `rgba()` string at the given alpha. */
export function hexToRgba(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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
  /** Translucent per-relationship-type color for the canvas link stroke. */
  color: string;
  /** Solid per-relationship-type color (for the inspector heading/swatch). */
  typeColor: string;
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
  /** Free-text search; matches node name/id/label/description and edge type. */
  query?: string;
}

/**
 * Does a node match the (already lowercased) search query? Matches its name, id,
 * any label, or its (server-truncated) `description` property. An empty query
 * matches everything.
 */
export function nodeMatchesQuery(node: GraphNode, q: string): boolean {
  if (!q) return true;
  if (node.name && node.name.toLowerCase().includes(q)) return true;
  if (node.id.toLowerCase().includes(q)) return true;
  if (node.labels.some((l) => l.toLowerCase().includes(q))) return true;
  const desc = node.properties?.description;
  if (typeof desc === "string" && desc.toLowerCase().includes(q)) return true;
  return false;
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
  const query = (opts.query ?? "").trim().toLowerCase();

  // Unique color per relationship type (shared with the sidebar legend).
  const typeColors = edgeTypeColorMap(payload.edges.map((e) => e.type));

  // `passesLabel` is the label-filter gate; a node can only ever be shown if it
  // passes it. Search then narrows further (below).
  const passesLabel = (node: GraphNode) => !hiddenLabels || !hiddenLabels.has(node.label);
  const nodeById = new Map(payload.nodes.map((n) => [n.id, n]));

  // Determine the surviving node id set.
  //  - No query: every label-passing node.
  //  - Query: nodes whose text matches, PLUS the endpoints of any non-hidden
  //    edge whose `type` matches the query (so a matched edge shows its nodes).
  const survivingIds = new Set<string>();
  for (const node of payload.nodes) {
    if (passesLabel(node) && nodeMatchesQuery(node, query)) survivingIds.add(node.id);
  }
  if (query) {
    for (const edge of payload.edges) {
      if (hiddenTypes && hiddenTypes.has(edge.type)) continue;
      if (!edge.type.toLowerCase().includes(query)) continue;
      const s = nodeById.get(edge.source);
      const t = nodeById.get(edge.target);
      if (s && passesLabel(s)) survivingIds.add(edge.source);
      if (t && passesLabel(t)) survivingIds.add(edge.target);
    }
  }

  // Build the node list from the surviving ids.
  const nodes: FGNode[] = [];
  for (const node of payload.nodes) {
    if (!survivingIds.has(node.id)) continue;
    nodes.push({
      ...node,
      color: labelColor(node.label),
    });
  }

  // Build the filtered link list — drop hidden types and dangling links
  const links: FGLink[] = [];

  for (const edge of payload.edges) {
    if (hiddenTypes && hiddenTypes.has(edge.type)) continue;
    // Drop if either endpoint is not visible — no dangling links
    if (!survivingIds.has(edge.source)) continue;
    if (!survivingIds.has(edge.target)) continue;

    const solid = typeColors.get(edge.type) ?? LABEL_PALETTE[0];
    links.push({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type,
      color: hexToRgba(solid, 0.55),
      typeColor: solid,
      sourceId: edge.source,
      targetId: edge.target,
    });
  }

  return { nodes, links };
}
