/**
 * synthesisMatrix.ts — Derive a technique×mitigation coverage matrix from a
 * verified `answer.synthesis` view: rows are the ATT&CK techniques in the
 * answer, columns are mitigations, and a filled cell means a `mitigatedBy`
 * edge connects them. The grid alternative to the network plot — "which
 * mitigations cover which of these techniques, and where are the gaps?" at a
 * glance, without tracing force-graph edges.
 *
 * Topology comes from the same `deriveEdges` seam the network plot uses (one
 * authority: explicit verifier edges when present, co-citation inference
 * otherwise), filtered to `mitigatedBy`. No React, no canvas imports:
 * unit-testable in isolation.
 */

import {
  classifyEntity,
  deriveEdges,
  isProvenanceExact,
  REL_MITIGATED_BY,
  type EntityDetail,
} from "./synthesisGraph";
import type { JoinPair, SynthesisView } from "./types";

export interface MatrixEntity {
  id: string;
  name: string;
}

export interface MitigationMatrix {
  /** Row entities, sorted by id for a deterministic render. */
  techniques: MatrixEntity[];
  /** Column entities, sorted by id for a deterministic render. */
  mitigations: MatrixEntity[];
  /** Filled cells, keyed by `cellKey(techniqueId, mitigationId)`. */
  cells: Set<string>;
  /** Whether the underlying edges are the verifier's provenance-exact set
   *  rather than frontend-inferred — drives the honesty caption. */
  provenanceExact: boolean;
}

export function cellKey(techniqueId: string, mitigationId: string): string {
  return `${techniqueId}__${mitigationId}`;
}

/**
 * Build the matrix from the answer's `mitigatedBy` edges. Endpoints are
 * oriented defensively by id classification (technique row, mitigation
 * column) so a reversed edge cannot corrupt the grid; edges whose endpoints
 * are not a technique/mitigation pair are ignored. Display names come from
 * `details` (the turn's federated evidence) with the id as fallback.
 */
export function buildMitigationMatrix(
  synthesis: SynthesisView,
  joinPairs: JoinPair[],
  details?: Map<string, EntityDetail>,
): MitigationMatrix {
  const edges = deriveEdges(synthesis.claims, joinPairs, synthesis.edges).filter(
    (e) => e.type === REL_MITIGATED_BY,
  );

  const nameOf = (id: string) => details?.get(id)?.name || id;
  const techniques = new Map<string, MatrixEntity>();
  const mitigations = new Map<string, MatrixEntity>();
  const cells = new Set<string>();

  for (const edge of edges) {
    const sourceKind = classifyEntity(edge.source).kind;
    const targetKind = classifyEntity(edge.target).kind;
    let technique: string;
    let mitigation: string;
    if (sourceKind === "technique" && targetKind === "mitigation") {
      technique = edge.source;
      mitigation = edge.target;
    } else if (sourceKind === "mitigation" && targetKind === "technique") {
      technique = edge.target;
      mitigation = edge.source;
    } else {
      continue;
    }
    if (!techniques.has(technique)) {
      techniques.set(technique, { id: technique, name: nameOf(technique) });
    }
    if (!mitigations.has(mitigation)) {
      mitigations.set(mitigation, { id: mitigation, name: nameOf(mitigation) });
    }
    cells.add(cellKey(technique, mitigation));
  }

  const byId = (a: MatrixEntity, b: MatrixEntity) => a.id.localeCompare(b.id);
  return {
    techniques: [...techniques.values()].sort(byId),
    mitigations: [...mitigations.values()].sort(byId),
    cells,
    provenanceExact: isProvenanceExact(synthesis),
  };
}

/** A matrix is worth drawing only when it has at least one filled cell across
 *  a real row×column grid. */
export function isRenderableMatrix(matrix: MitigationMatrix): boolean {
  return (
    matrix.techniques.length > 0 &&
    matrix.mitigations.length > 0 &&
    matrix.cells.size > 0
  );
}
