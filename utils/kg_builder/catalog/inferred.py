#!/usr/bin/env python3
"""Edges this project adds because the delivered export could not contain them.

The delivered catalog is truncated by an inner join (see
:func:`utils.kg_builder.catalog.reader.detect_truncation`), and no corrected
export is coming. Some of what it lost is load-bearing: without
``USER -MEMBER_OF-> GROUP`` a user is never the *source* of any Active Directory
edge, so 48 of the 60 delivered triples are unreachable from a user anchor and
the graph cannot express a privilege-escalation path at all.

So a small number of edges are added here. Everything about how they are handled
follows from one rule: **an inferred edge is this project's construction, not
ReliaQuest's schema, and no reader should ever have to guess which is which.**

* Each carries a written justification, kept next to the edge rather than in a
  document that can drift away from it.
* They are tagged :data:`~utils.kg_builder.catalog.declared.INFERRED` in the
  artifact, in the source card, and in the generated graph.
* Adding one that collides with a delivered triple raises rather than
  overwrites -- a collision means the inference was unnecessary.
* Every result that traverses one is reported separately from results that do
  not, because on any such question the inference is a confound.

The list is deliberately as short as it can be while leaving the graph
functional. The temptation to reconstruct a plausible whole BloodHound schema is
exactly the thing to resist: each addition is another degree of freedom between
what is measured and what ReliaQuest actually runs.
"""

from __future__ import annotations

from .declared import INFERRED, DeclaredCatalog, DeclaredTriple, add_triples

# (source, edge, target) -> why this project added it.
#
# Three entries. Each one is here because its absence breaks something
# structural, not because a real AD schema would plausibly have it -- that
# weaker standard would admit dozens.
INFERRED_EDGES: dict[tuple[str, str, str], str] = {
    ("USER", "MEMBER_OF", "GROUP"): (
        "Without this a USER is never the source of an Active Directory edge. "
        "48 of the 60 delivered triples have GROUP as source, so every one of "
        "them is unreachable from a user anchor and no user-anchored outbound "
        "question can return anything. MEMBER_OF is delivered into GCP_GROUP "
        "and OKTA_GROUP but not GROUP, which is itself the clearest single "
        "piece of evidence that the export dropped attribute-less edges."
    ),
    ("GROUP", "MEMBER_OF", "GROUP"): (
        "Nested groups are how Active Directory privilege actually accumulates: "
        "a user in a low-privilege group inherits through a chain of group "
        "memberships. Without nesting every planted attack path is depth-1 from "
        "a group, which would make the multi-hop retrieval this experiment "
        "measures trivial in a way real tenants are not."
    ),
    ("USER", "MEMBER_OF", "ENTRA_GROUP"): (
        "Parity with the two cloud MEMBER_OF triples that did survive the join "
        "(GCP_GROUP, OKTA_GROUP). ENTRA_GROUP is a delivered node type with 18 "
        "declared attributes and no delivered inbound edge of any kind, which "
        "is not a coherent schema. Included so the Entra plane is reachable at "
        "all; excluded from any question whose gold depends on it alone."
    ),
}


def inferred_triples() -> list[DeclaredTriple]:
    """The inferred edges as triples, tagged so they cannot pass as declared."""
    return [
        DeclaredTriple(source, edge, target, INFERRED)
        for (source, edge, target) in sorted(INFERRED_EDGES)
    ]


def justification(source: str, edge: str, target: str) -> str | None:
    """Why this project added an edge, or ``None`` if it did not add it."""
    return INFERRED_EDGES.get((source, edge, target))


def apply_inferred(catalog: DeclaredCatalog) -> DeclaredCatalog:
    """Add the inferred edges to ``catalog`` in place and return it.

    Raises if any inferred edge is already declared -- see the module docstring.
    """
    add_triples(catalog, inferred_triples())
    return catalog
