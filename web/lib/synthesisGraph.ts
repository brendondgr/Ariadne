/**
 * synthesisGraph.ts — Derive a compact per-answer CAPEC–ATT&CK–mitigation
 * subgraph from a verified `answer.synthesis` view, shaped as a `GraphPayload`
 * so the existing `toForceGraphData` transform and `GraphCanvas` render it with
 * no new engine.
 *
 * Deliverable #4's network plot. Nodes are the entities the verified claims
 * cite; edges are the CAPEC→ATT&CK→mitigation relationships between them.
 *
 * EDGE-DERIVATION SEAM (Option A → B): `deriveEdges` is the ONLY place topology
 * is decided. Today it *infers* edges from the federation join index
 * (`joinPairs`, exact CAPEC↔ATT&CK) plus same-claim technique↔mitigation
 * co-citation. When the synthesis payload later carries explicit typed edges
 * (Option B), only this function changes to consume them — the node set, the
 * component, the table, and the renderer stay put. No React, no canvas imports:
 * unit-testable in isolation.
 */

import type {
  FederatedEvidence,
  GraphEdge,
  GraphNode,
  GraphPayload,
  JoinPair,
  SynthesisGraphEdge,
  SynthesisView,
} from "./types";

export type EntityKind = "capec" | "technique" | "mitigation" | "other";

export interface EntityClass {
  kind: EntityKind;
  /** Node `label` — drives the palette color in `toForceGraphData`. */
  label: string;
}

/** Classify an identifier by its canonical prefix. This is what lets the plot
 *  type nodes without any new backend field: CAPEC patterns, ATT&CK techniques
 *  (incl. sub-techniques `T####.###`), and mitigations `M####`. */
export function classifyEntity(id: string): EntityClass {
  if (/^CAPEC-\d+$/i.test(id)) return { kind: "capec", label: "CAPEC Pattern" };
  if (/^T\d{4}(?:\.\d{3})?$/i.test(id)) return { kind: "technique", label: "ATT&CK Technique" };
  if (/^M\d{4}$/i.test(id)) return { kind: "mitigation", label: "Mitigation" };
  return { kind: "other", label: "Entity" };
}

/** All identifiers one claim touches: its citation ids ∪ its asserted
 *  `entityIds`, de-duplicated in first-seen order. */
function claimIds(claim: SynthesisView["claims"][number]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const id of [...claim.chips.map((c) => c.id), ...claim.entityIds]) {
    if (id && !seen.has(id)) {
      seen.add(id);
      out.push(id);
    }
  }
  return out;
}

/** Relationship types used in the plot (also the color keys). */
export const REL_MAPS_TO = "mapsTo";
export const REL_MITIGATED_BY = "mitigatedBy";

/**
 * Derive the plot's edges. Two modes behind one seam:
 *
 * EXPLICIT MODE (Option B): when the payload carries provenance-exact `explicit`
 * edges (verifier-derived, verifier-pruned), use them verbatim — no inference.
 *
 * INFERENCE MODE (Option A, the fallback when `explicit` is empty):
 *  - CAPEC→ATT&CK from the federation join index (`joinPairs`) — oriented
 *    pattern→technique regardless of pair order.
 *  - technique→mitigation from within-claim co-citation (a claim that cites
 *    both a `T####` and an `M####` asserts the mitigation link).
 *  - CAPEC→ATT&CK also inferred from a claim co-citing both (redundant with the
 *    join index, de-duplicated).
 *
 * Edges are de-duplicated by (source, type, target). Self-loops are dropped.
 */
export function deriveEdges(
  claims: SynthesisView["claims"],
  joinPairs: JoinPair[],
  explicit: SynthesisGraphEdge[] = [],
): GraphEdge[] {
  const edges = new Map<string, GraphEdge>();
  const add = (source: string, target: string, type: string) => {
    if (!source || !target || source === target) return;
    const id = `${source}__${type}__${target}`;
    if (!edges.has(id)) edges.set(id, { id, source, target, type });
  };

  // Option B: trust the verifier's exact edges; skip all inference.
  if (explicit.length > 0) {
    for (const e of explicit) add(e.source, e.target, e.rel);
    return [...edges.values()];
  }

  // Join index → CAPEC→ATT&CK, oriented pattern→technique regardless of order.
  for (const p of joinPairs) {
    const l = classifyEntity(p.left).kind;
    const r = classifyEntity(p.right).kind;
    if (l === "capec" && r === "technique") add(p.left, p.right, REL_MAPS_TO);
    else if (l === "technique" && r === "capec") add(p.right, p.left, REL_MAPS_TO);
    else add(p.left, p.right, REL_MAPS_TO);
  }

  // Within-claim co-citation.
  for (const claim of claims) {
    const ids = claimIds(claim);
    const capecs = ids.filter((i) => classifyEntity(i).kind === "capec");
    const techs = ids.filter((i) => classifyEntity(i).kind === "technique");
    const mits = ids.filter((i) => classifyEntity(i).kind === "mitigation");
    for (const c of capecs) for (const t of techs) add(c, t, REL_MAPS_TO);
    for (const t of techs) for (const m of mits) add(t, m, REL_MITIGATED_BY);
  }

  return [...edges.values()];
}

/** Human-readable detail for one entity id, projected from the turn's federated
 *  evidence. Lets the plot label nodes with real names and show their
 *  properties (description, provenance, join values) in the inspector. */
export interface EntityDetail {
  name: string;
  label: string;
  properties: Record<string, unknown>;
}

/**
 * Build an `id → EntityDetail` lookup from a turn's federated evidence.
 *
 * The rich source is every specialist record (`results[].records[]`), which
 * carries the entity's `name`, `label`, and full `properties` (description,
 * etc.). Join-index entries (`join_index[*]`) are a name-only fallback for the
 * cross-source endpoints that never surfaced as a full record. Records win over
 * join-index entries because they carry properties. No React, no canvas imports:
 * unit-testable in isolation.
 */
export function buildEntityDetails(
  federated: FederatedEvidence | null | undefined,
): Map<string, EntityDetail> {
  const details = new Map<string, EntityDetail>();
  if (!federated) return details;

  // Name-only fallback first, so full records overwrite it below.
  for (const entries of Object.values(federated.join_index ?? {})) {
    for (const entry of entries) {
      if (entry.primary_id && !details.has(entry.primary_id)) {
        details.set(entry.primary_id, {
          name: entry.name || entry.primary_id,
          label: "",
          properties: {},
        });
      }
    }
  }

  for (const result of federated.results ?? []) {
    for (const rec of result.records) {
      if (!rec.primary_id) continue;
      details.set(rec.primary_id, {
        name: rec.name || rec.primary_id,
        label: rec.label ?? "",
        properties: rec.properties ?? {},
      });
    }
  }

  // A record's `related` entries (e.g. a technique's MITIGATES mitigations)
  // are a name-only fallback for ids that never surfaced as their own record —
  // set-if-absent after the record pass so full records always win.
  for (const result of federated.results ?? []) {
    for (const rec of result.records) {
      for (const rel of rec.related ?? []) {
        const raw = rel.id ?? rel.entry_id;
        const id = typeof raw === "string" ? raw : "";
        if (!id || details.has(id)) continue;
        details.set(id, {
          name: typeof rel.name === "string" && rel.name ? rel.name : id,
          label: "",
          properties: {},
        });
      }
    }
  }

  return details;
}

function countByLabel(nodes: GraphNode[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const n of nodes) out[n.label] = (out[n.label] ?? 0) + 1;
  return out;
}

/**
 * Build the per-answer subgraph as a `GraphPayload`. Nodes are every identifier
 * the verified claims cite or assert, plus the join-index endpoints; edges come
 * from `deriveEdges`. Feed the result straight into `toForceGraphData`.
 */
export function synthesisToGraphPayload(
  synthesis: SynthesisView,
  joinPairs: JoinPair[],
  details?: Map<string, EntityDetail>,
): GraphPayload {
  const edges = deriveEdges(synthesis.claims, joinPairs, synthesis.edges);

  const ids = new Set<string>();
  for (const claim of synthesis.claims) for (const id of claimIds(claim)) ids.add(id);
  for (const p of joinPairs) {
    if (p.left) ids.add(p.left);
    if (p.right) ids.add(p.right);
  }
  for (const e of edges) {
    ids.add(e.source);
    ids.add(e.target);
  }

  const nodes: GraphNode[] = [...ids].map((id) => {
    // `label` (the palette key) always comes from the id's canonical prefix so
    // the color legend stays stable; only the display name and properties are
    // enriched from the evidence, when present.
    const { label } = classifyEntity(id);
    const detail = details?.get(id);
    return {
      id,
      label,
      labels: [label],
      name: detail?.name || id,
      properties: detail?.properties ?? {},
    };
  });

  return {
    dataset: "synthesis",
    backend: "synthesis",
    counts: { nodes: nodes.length, relationships: edges.length },
    nodes_by_label: countByLabel(nodes),
    nodes,
    edges,
  };
}

/** A plot is worth drawing only when it has at least one edge (a lone node or a
 *  disconnected pair carries no CAPEC–ATT&CK–mitigation story). */
export function isRenderableSubgraph(payload: GraphPayload): boolean {
  return payload.edges.length > 0 && payload.nodes.length >= 2;
}

/** Whether the plot's edges are the backend's provenance-exact set (Option B)
 *  rather than frontend-inferred (Option A). Drives the plot's honesty label. */
export function isProvenanceExact(synthesis: SynthesisView): boolean {
  return synthesis.edges.length > 0;
}
