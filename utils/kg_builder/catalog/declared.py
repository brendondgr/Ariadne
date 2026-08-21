#!/usr/bin/env python3
"""The data model for a schema that was *declared* rather than observed.

Every schema this repository has handled until now was derived by walking
instances: :func:`utils.specialists.schema.build.build_dataset_schema` reads
``nodes.jsonl`` and ``relationships.jsonl`` and learns label -> property keys and
``(source, rel, target)`` triples from what it finds. That works because we built
those files ourselves.

A customer catalog inverts the situation. ReliaQuest supplied the schema of their
production graph and none of its records, which is the ordinary case for a source
somebody else operates -- and it is the input this project's architecture claims
to need. So the catalog needs a home of its own, and the distinction it carries
has to survive into the registry rather than being flattened on the way in:

**Observed means "some node actually has this edge." Declared means "the catalog
permits this edge."** A facet block asserting an honest zero rests on the first
reading. Under the second, a zero says the tenant has no such edge *today*, which
is a weaker and different statement. Recording which one is in play is the whole
reason :class:`DeclaredCatalog` exists instead of a dict of triples.

Two further things this model insists on carrying:

* **Declared value types.** The scan path infers nothing about types -- it sees
  a value and records the key. A catalog states ``STRING`` / ``BOOLEAN`` /
  ``INTEGER`` / ``LIST_STRING`` outright, which is strictly more than a scan
  produces and is worth not discarding.
* **What the catalog cannot see.** See :class:`Truncation`. A schema that is
  quietly incomplete is far more dangerous than one that says so.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# The four value types the customer catalog declares. Anything else is recorded
# verbatim rather than coerced -- an unexpected type is a fact about the
# delivery, not a parse error to paper over.
KNOWN_VALUE_TYPES = frozenset({"STRING", "BOOLEAN", "INTEGER", "LIST_STRING"})

# Provenance of a triple. `DECLARED` came from the delivered catalog and is
# authoritative. `INFERRED` was added by this project to make the graph
# functional, and is never authoritative -- see utils/kg_builder/catalog/inferred.py.
DECLARED = "declared"
INFERRED = "inferred"


@dataclass(frozen=True, order=True)
class DeclaredAttribute:
    """One attribute the catalog declares on a node type or an edge."""

    name: str
    value_type: str

    @property
    def is_known_type(self) -> bool:
        return self.value_type in KNOWN_VALUE_TYPES


@dataclass(frozen=True, order=True)
class DeclaredTriple:
    """One ``(source_label, edge_label, target_label)`` the catalog permits.

    ``origin`` is :data:`DECLARED` or :data:`INFERRED` and is deliberately part
    of the value rather than tracked alongside it, so a triple cannot be moved
    between sets by accident.
    """

    source: str
    edge: str
    target: str
    origin: str = DECLARED

    @property
    def is_homogeneous(self) -> bool:
        """Both endpoints carry the same label.

        These are the hard direction case and the reason for EXP-2026-08-011's
        H3: a ``PlausibleFacet`` is ``(rel_type, direction, neighbour_label)``,
        so when source and target labels are equal the neighbour label carries
        no disambiguating signal and only the direction field separates the two
        readings. ATT&CK has essentially no such edges; this catalog has eight.
        """
        return self.source == self.target

    def key(self) -> tuple[str, str, str]:
        return (self.source, self.edge, self.target)


@dataclass(frozen=True)
class Truncation:
    """What the delivered export structurally could not contain.

    ReliaQuest's export ran ``select distinct ... from customer_edge_catalog e
    join customer_attribute_catalog a on e.uuid = a.edge_uuid``. That join is an
    inner join, so **an edge type carrying no attributes never reached the
    file.** The same holds for node types on the vertex query.

    This is not a suspicion. It is visible in the delivered data: ``MEMBER_OF``
    appears only into ``GCP_GROUP`` and ``OKTA_GROUP``, there is no
    ``USER -MEMBER_OF-> GROUP``, and 48 of the 60 triples have ``GROUP`` as
    source -- an Active Directory graph in which no user belongs to any group.

    The operator confirmed on 2026-08-21 that no corrected export is coming, so
    this is a permanent property of the dataset. Recording it *in the artifact*
    rather than only in prose means every downstream consumer -- the source
    card, the generator, the results table -- can see it without being told.
    """

    suspected: bool
    reason: str
    corrected_query: str
    evidence: tuple[str, ...] = ()


@dataclass
class DeclaredCatalog:
    """A whole schema as declared by a customer catalog.

    ``node_attributes`` maps label -> attribute name -> :class:`DeclaredAttribute`.
    ``edge_attributes`` maps a triple key -> attribute name -> attribute.
    ``triples`` holds both declared and inferred entries; the split is available
    through :meth:`declared_triples` and :meth:`inferred_triples` and is never
    collapsed.
    """

    name: str
    source_files: dict[str, str]
    node_attributes: dict[str, dict[str, DeclaredAttribute]] = field(default_factory=dict)
    edge_attributes: dict[tuple[str, str, str], dict[str, DeclaredAttribute]] = field(
        default_factory=dict
    )
    triples: list[DeclaredTriple] = field(default_factory=list)
    truncation: Truncation | None = None

    # -- projections -------------------------------------------------------

    @property
    def node_labels(self) -> list[str]:
        return sorted(self.node_attributes)

    @property
    def edge_labels(self) -> list[str]:
        return sorted({t.edge for t in self.triples})

    def declared_triples(self) -> list[DeclaredTriple]:
        return sorted(t for t in self.triples if t.origin == DECLARED)

    def inferred_triples(self) -> list[DeclaredTriple]:
        return sorted(t for t in self.triples if t.origin == INFERRED)

    def homogeneous_triples(self) -> list[DeclaredTriple]:
        """Triples whose endpoints share a label. See :meth:`DeclaredTriple.is_homogeneous`."""
        return sorted(t for t in self.triples if t.is_homogeneous)

    def triples_from(self, label: str) -> list[DeclaredTriple]:
        return sorted(t for t in self.triples if t.source == label)

    def triples_into(self, label: str) -> list[DeclaredTriple]:
        return sorted(t for t in self.triples if t.target == label)

    def permits(self, source: str, edge: str, target: str) -> bool:
        """Whether the catalog (declared *or* inferred) allows this edge.

        The generator uses this as its conformance rule, which is why the graph
        it emits cannot drift from the catalog: an edge that is not permitted is
        never written in the first place.
        """
        return any(t.key() == (source, edge, target) for t in self.triples)

    def attribute_names(self, label: str) -> list[str]:
        return sorted(self.node_attributes.get(label, {}))

    def counts(self) -> dict[str, int]:
        """The countable shape of the catalog, for tests and for the record."""
        return {
            "node_types": len(self.node_attributes),
            "edge_labels": len(self.edge_labels),
            "triples": len(self.triples),
            "triples_declared": len(self.declared_triples()),
            "triples_inferred": len(self.inferred_triples()),
            "triples_homogeneous": len(self.homogeneous_triples()),
            "node_attributes": sum(len(v) for v in self.node_attributes.values()),
            "edge_attributes": sum(len(v) for v in self.edge_attributes.values()),
        }

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_files": self.source_files,
            "counts": self.counts(),
            "truncation": (
                None
                if self.truncation is None
                else {
                    "suspected": self.truncation.suspected,
                    "reason": self.truncation.reason,
                    "corrected_query": self.truncation.corrected_query,
                    "evidence": list(self.truncation.evidence),
                }
            ),
            "node_attributes": {
                label: {a.name: a.value_type for a in sorted(attrs.values())}
                for label, attrs in sorted(self.node_attributes.items())
            },
            "triples": [
                {
                    "source": t.source,
                    "edge": t.edge,
                    "target": t.target,
                    "origin": t.origin,
                    "homogeneous": t.is_homogeneous,
                    "attributes": {
                        a.name: a.value_type
                        for a in sorted(self.edge_attributes.get(t.key(), {}).values())
                    },
                }
                for t in sorted(self.triples)
            ],
        }

    def write(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n", encoding="utf-8")
        return out

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeclaredCatalog":
        catalog = cls(
            name=payload["name"],
            source_files=dict(payload.get("source_files") or {}),
        )
        for label, attrs in (payload.get("node_attributes") or {}).items():
            catalog.node_attributes[label] = {
                n: DeclaredAttribute(n, v) for n, v in attrs.items()
            }
        for entry in payload.get("triples") or []:
            triple = DeclaredTriple(
                entry["source"], entry["edge"], entry["target"], entry.get("origin", DECLARED)
            )
            catalog.triples.append(triple)
            attrs = entry.get("attributes") or {}
            if attrs:
                catalog.edge_attributes[triple.key()] = {
                    n: DeclaredAttribute(n, v) for n, v in attrs.items()
                }
        trunc = payload.get("truncation")
        if trunc:
            catalog.truncation = Truncation(
                suspected=trunc["suspected"],
                reason=trunc["reason"],
                corrected_query=trunc["corrected_query"],
                evidence=tuple(trunc.get("evidence") or ()),
            )
        return catalog

    @classmethod
    def read(cls, path: str | Path) -> "DeclaredCatalog":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def add_triples(catalog: DeclaredCatalog, triples: Iterable[DeclaredTriple]) -> None:
    """Append triples, refusing a duplicate key regardless of origin.

    Refusing rather than overwriting is deliberate: if an inferred triple ever
    collides with a declared one, that means the inference was unnecessary and
    the inference list should shrink, not that the declared entry should be
    shadowed by ours.
    """
    seen = {t.key() for t in catalog.triples}
    for triple in triples:
        if triple.key() in seen:
            raise ValueError(
                f"refusing to add {triple.key()} as {triple.origin}: already present"
            )
        seen.add(triple.key())
        catalog.triples.append(triple)
