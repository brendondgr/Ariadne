#!/usr/bin/env python3
"""Assemble the identity source card: derived schema + hand-authored overlay.

Same division of labour the ATT&CK and CAPEC cards already use. The generated
half is everything the catalog knows — labels, properties, relationship types
and endpoints. The authored half is everything it cannot know: where the store
is, what the safety limits are, and what a ``DC_SYNC`` edge *means* to an
analyst.

The glosses are not decoration. This schema has 72 labels including six kinds of
"group" — ``GROUP``, ``ENTRA_GROUP``, ``OKTA_GROUP``, ``GCP_GROUP``,
``AWS_SSO_GROUP`` and ``AWS_EC2_SECURITY_GROUP``, the last of which is a network
control and not a principal at all — plus the real ``ENTRA_LICENCE`` /
``ENTRA_LICENSE`` spelling collision. When a question says "group", the
descriptions are the deterministic planner's only signal for which one is meant.

Two fields exist on this card that no other card has, because no other dataset
needed them:

``identity.declared_endpoints``
    The full ``(source, edge, target, origin)`` list, not just the flat
    relationship-type names. Direction resolution reads it, and the ``origin``
    field is how a result that traversed an inferred edge stays reportable
    separately from one that did not.

``provenance.schema_provenance`` / ``provenance.instance_provenance``
    ``declared`` and ``synthetic``. Stated on the card itself so nothing
    downstream has to remember which half of this source is real.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .declared import DECLARED, INFERRED, DeclaredCatalog

_TYPE_MAP = {
    "STRING": "string",
    "BOOLEAN": "boolean",
    "INTEGER": "integer",
    "LIST_STRING": "array",
}


def _node_properties(
    catalog: DeclaredCatalog,
    examples: dict[str, dict[str, Any]],
    names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Per-label property schema, with an example drawn from real instances.

    Examples come from the generated tenant rather than being invented, so a
    reader of the card sees what an identifier on this source actually looks
    like — which for a schema mixing ARNs, SIDs, GUIDs and UPNs is the only way
    the card conveys shape at all, since ``STRING`` conveys none.
    """
    names = names or {}
    out: dict[str, Any] = {}
    for label, attrs in sorted(catalog.node_attributes.items()):
        sample = examples.get(label, {})
        # `name` is declared for every label even though no catalog row mentions
        # it. That is not an invention: the canonical loader writes a top-level
        # `name` on every node, exactly as it does for ATT&CK, whose card
        # declares it on all eleven labels.
        #
        # Omitting it is not cosmetic. Anchor resolution offers a name anchor
        # only for a property the card declares, so a card without `name` leaves
        # a question like "what can Database Admins write" with no name to bind
        # to -- the planner falls back to matching schema words against 72 label
        # names and 21 relationship names, and ordinary IT English collides with
        # those constantly. The first sweep floored at 0.07 on both arms for
        # exactly this reason, which was a defect in this card and not a finding
        # about the system.
        properties: dict[str, Any] = {
            attr.name: {
                "type": _TYPE_MAP.get(attr.value_type, "string"),
                "declared_type": attr.value_type,
                "optional": attr.name not in sample,
                "example": sample.get(attr.name),
            }
            for attr in sorted(attrs.values())
        }
        properties["name"] = {
            "type": "string",
            "declared_type": "STRING",
            "optional": False,
            "example": names.get(label),
            "source": "canonical loader, not the customer catalog",
        }
        out[label] = properties
    return out


def build_card(
    catalog: DeclaredCatalog,
    overlay: dict[str, Any],
    out_dir: str | Path,
    examples: dict[str, dict[str, Any]] | None = None,
    dataset: str = "identity",
    names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Merge the derived schema with the authored overlay into one card."""
    prefix = Path(out_dir).as_posix()
    declared = catalog.declared_triples()
    inferred = catalog.inferred_triples()

    card: dict[str, Any] = {
        "schema_version": "1.0",
        "dataset": dataset,
        "runtime_backend": "neo4j",
        "canonical_dir": f"{prefix}/graphs/{dataset}/canonical",
        "canonical_manifest": f"{prefix}/graphs/{dataset}/canonical/manifest.json",
        "endpoints": {"neo4j": "", "gremlin": ""},
        "exports": {
            "neo4j": {
                "constraints_cypher": f"{prefix}/graphs/{dataset}/exports/neo4j/constraints.cypher"
            }
        },
        "node_labels": sorted(catalog.node_attributes),
        "relationship_types": sorted({t.edge for t in catalog.triples}),
        "node_properties": _node_properties(catalog, examples or {}, names or {}),
        "identity": {
            "join_key": ["id"],
            "unique_backstop": "id",
            "constraints": [f"{dataset}_id_unique"],
            "known_collisions": {
                "ENTRA_LICENCE / ENTRA_LICENSE": (
                    "Both spellings are declared as separate node types in the "
                    "delivered catalog. This is the customer's real schema, not "
                    "a transcription error on our side, and it is preserved. A "
                    "question about licences may be genuinely ambiguous; saying "
                    "so is the correct answer."
                )
            },
            "policy": (
                "Every node carries a globally unique opaque `id`. Unlike ATT&CK "
                "there is no analyst-facing public identifier, and unlike CAPEC "
                "the id is not the name — so joins are on `id` alone and a "
                "human-readable reference must come from `name`."
            ),
            "declared_endpoints": [
                {
                    "source": t.source,
                    "type": t.edge,
                    "target": t.target,
                    "origin": t.origin,
                    "homogeneous": t.is_homogeneous,
                }
                for t in sorted(catalog.triples)
            ],
            "not_traversable": {
                label: (
                    "Declared node type with no declared relationship of any "
                    "kind. 58 of this catalog's 72 labels are in this position, "
                    "because the delivered export inner-joined to the attribute "
                    "catalog and dropped every attribute-less edge. Instances "
                    "exist and are describable; nothing can be traversed from "
                    "them. Never route a multi-hop question through this label."
                )
                for label in sorted(
                    set(catalog.node_attributes)
                    - {t.source for t in catalog.triples}
                    - {t.target for t in catalog.triples}
                )
            },
        },
        "catalog": {
            "source_files": catalog.source_files,
            "counts": catalog.counts(),
            "declared_triples": len(declared),
            "inferred_triples": len(inferred),
            "inferred_detail": [
                {"source": t.source, "type": t.edge, "target": t.target} for t in inferred
            ],
            "truncated": bool(catalog.truncation and catalog.truncation.suspected),
            "truncation_reason": (
                catalog.truncation.reason if catalog.truncation else None
            ),
        },
    }

    # The authored half wins wherever it speaks: it is the only source for
    # connection, safety, provenance and glosses, and it must be able to correct
    # a generated value rather than being silently overridden by one.
    for key, value in overlay.items():
        if key.startswith("_"):
            continue
        card[key] = value
    return card


def load_overlay(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_card(card: dict[str, Any], path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def examples_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """First-seen property dict per label, used to fill the card's examples."""
    out: dict[str, dict[str, Any]] = {}
    for node in nodes:
        out.setdefault(node["label"], node["properties"])
    return out


def names_from_nodes(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """First-seen `name` per label, for the declared `name` property's example."""
    out: dict[str, str] = {}
    for node in nodes:
        if node.get("name"):
            out.setdefault(node["label"], node["name"])
    return out
