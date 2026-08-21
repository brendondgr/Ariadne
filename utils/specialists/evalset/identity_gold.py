#!/usr/bin/env python3
"""Gold answers for the identity dataset, computed from the generator blueprint.

**Never from the loaded graph.** That is the whole point, and it is the same
property :mod:`utils.specialists.evalset.gold_bank` gets by parsing the raw STIX
bundle deliberately outside ``kg_builder``: gold and answers agree only if the
build and the load were both faithful, so the suite doubles as an ingestion
check. If gold were read back from Neo4j, a dropped edge would cancel out on
both sides and be invisible — and this experiment already caught one such
divergence during the load (a duplicated edge that Neo4j MERGEd away), which is
the evidence that the property is worth paying for.

Six question kinds, chosen so each hypothesis in
``EXP-2026-08-011/PROTOCOL.md`` has a population to be measured over:

===============  ===================================================  ========
Kind             What it asks                                         Bears on
===============  ===================================================  ========
``describe``     an attribute of one node                             H1
``facet-out``    neighbours along an edge the anchor is the source of  H1
``facet-in``     neighbours along an edge the anchor is the target of  H1, H3
``homo-out``     as facet-out, on a same-label-both-ends triple         H3
``homo-in``      as facet-in, on a same-label-both-ends triple          H3
``multihop``     a planted chain, two or three edges deep              H1
``unanswerable`` something the schema cannot support                   H4, C-017
===============  ===================================================  ========

The ``homo-*`` kinds exist because a ``PlausibleFacet`` is ``(rel_type,
direction, neighbour_label)``, so when both endpoints carry the same label the
neighbour field carries no disambiguating signal and only the direction
separates the two readings. ATT&CK has essentially no such edges, so no bank on
record has ever exercised this.

Every gold entry records whether its answer depends on an *inferred* edge, so
results traversing this project's reconstruction of the truncated export stay
reportable separately from results that do not.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from utils.kg_builder.catalog.declared import DECLARED, INFERRED
from utils.kg_builder.synthetic.spec import TenantSpec

DESCRIBE = "describe"
FACET_OUT = "facet-out"
FACET_IN = "facet-in"
HOMO_OUT = "homo-out"
HOMO_IN = "homo-in"
MULTIHOP = "multihop"
UNANSWERABLE = "unanswerable"

KINDS = (DESCRIBE, FACET_OUT, FACET_IN, HOMO_OUT, HOMO_IN, MULTIHOP, UNANSWERABLE)


@dataclass
class GoldEntry:
    """One question's expected answer, derived from the blueprint alone.

    ``expected_ids`` is the set of node ids that must appear in the retrieved
    evidence. An empty set is meaningful rather than missing: for
    ``unanswerable`` it is the correct answer, and the arm is expected to
    abstain rather than return rows.
    """

    question_id: str
    kind: str
    anchor_id: str | None
    anchor_label: str
    anchor_name: str
    edge: str | None
    direction: str | None
    neighbour_label: str | None
    expected_ids: list[str]
    expected_names: list[str]
    uses_inferred: bool
    homogeneous: bool
    note: str = ""
    # The four fields the author is allowed to see, and nothing else. Kept here
    # so the separation is visible in the data rather than only in prose.
    author_view: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "kind": self.kind,
            "anchor_id": self.anchor_id,
            "anchor_label": self.anchor_label,
            "anchor_name": self.anchor_name,
            "edge": self.edge,
            "direction": self.direction,
            "neighbour_label": self.neighbour_label,
            "expected_ids": sorted(self.expected_ids),
            "expected_names": sorted(self.expected_names),
            "expected_count": len(self.expected_ids),
            "uses_inferred": self.uses_inferred,
            "homogeneous": self.homogeneous,
            "note": self.note,
            "author_view": self.author_view,
        }


def _names(spec: TenantSpec, ids: list[str]) -> list[str]:
    return sorted({spec.name_of(i) for i in ids})


def _edge_origin(spec: TenantSpec, source: str, edge: str, target: str) -> str:
    for record in spec.edges:
        if (record["source_id"], record["edge"], record["target_id"]) == (
            source,
            edge,
            target,
        ):
            return record["origin"]
    return DECLARED


def _triple_is_inferred(spec: TenantSpec, anchor: str, edge: str, direction: str) -> bool:
    """Whether the edge kind being walked is one this project inferred."""
    for record in spec.edges:
        if record["edge"] != edge:
            continue
        if direction == "out" and record["source_id"] == anchor:
            return record["origin"] == INFERRED
        if direction == "in" and record["target_id"] == anchor:
            return record["origin"] == INFERRED
    return False


def describe_gold(spec: TenantSpec, anchor: str, prop: str, qid: str) -> GoldEntry:
    """Gold for "what is <prop> of <anchor>" — the anchor itself is the answer."""
    node = spec.nodes[anchor]
    return GoldEntry(
        question_id=qid,
        kind=DESCRIBE,
        anchor_id=anchor,
        anchor_label=node["label"],
        anchor_name=node["name"],
        edge=None,
        direction=None,
        neighbour_label=None,
        expected_ids=[anchor],
        expected_names=[node["name"]],
        uses_inferred=False,
        homogeneous=False,
        note=f"property {prop} = {node['properties'].get(prop)!r}",
        author_view={
            "label": node["label"],
            "name": node["name"],
            "property": prop,
            "value": node["properties"].get(prop),
        },
    )


def facet_gold(
    spec: TenantSpec,
    anchor: str,
    edge: str,
    direction: str,
    qid: str,
    kind: str | None = None,
    neighbour_label: str | None = None,
) -> GoldEntry:
    """Gold for "which X does <anchor> reach along <edge>", in one direction.

    ``neighbour_label`` scopes the answer to one *triple* rather than to one
    edge label, and it matters more here than it would on ATT&CK. In this schema
    a single edge label spans many triples: ``ALL_EXTENDED_RIGHTS`` runs from
    ``GROUP`` to ``CONTAINER``, ``DEVICE``, ``DOMAIN``, ``GROUP``, ``OU`` and
    ``USER``. Walking the label alone therefore returns a mixed-label
    neighbourhood, and a question meant to be about the homogeneous
    ``GROUP -ALL_EXTENDED_RIGHTS-> GROUP`` triple would silently become a
    question about six triples at once -- which would make H3 unmeasurable,
    because its population would no longer be homogeneous.

    That is also precisely the retrieval problem being posed: the system has to
    filter on neighbour label *and* direction, not on the relationship name.
    """
    node = spec.nodes[anchor]
    neighbours = spec.neighbours(anchor, edge=edge, direction=direction)
    if neighbour_label is not None:
        neighbours = [n for n in neighbours if spec.label_of(n) == neighbour_label]
    neighbour_labels = {spec.label_of(n) for n in neighbours}
    homogeneous = bool(neighbour_labels) and neighbour_labels == {node["label"]}
    if kind is None:
        kind = (
            (HOMO_OUT if direction == "out" else HOMO_IN)
            if homogeneous
            else (FACET_OUT if direction == "out" else FACET_IN)
        )
    return GoldEntry(
        question_id=qid,
        kind=kind,
        anchor_id=anchor,
        anchor_label=node["label"],
        anchor_name=node["name"],
        edge=edge,
        direction=direction,
        neighbour_label=(
            neighbour_label
            if neighbour_label is not None
            else (sorted(neighbour_labels)[0] if neighbour_labels else None)
        ),
        expected_ids=neighbours,
        expected_names=_names(spec, neighbours),
        uses_inferred=_triple_is_inferred(spec, anchor, edge, direction),
        homogeneous=homogeneous,
        author_view={
            "label": node["label"],
            "name": node["name"],
            "relationship": edge,
            "direction": direction,
        },
    )


def multihop_gold(spec: TenantSpec, path_name: str, qid: str) -> GoldEntry:
    """Gold for a planted chain: every node the chain passes through."""
    path = next(p for p in spec.planted_paths if p.name == path_name)
    ids: list[str] = []
    for source, _edge, target in path.steps:
        ids.extend((source, target))
    ordered = list(dict.fromkeys(ids))
    start = spec.nodes[path.start]
    return GoldEntry(
        question_id=qid,
        kind=MULTIHOP,
        anchor_id=path.start,
        anchor_label=start["label"],
        anchor_name=start["name"],
        edge=path.steps[0][1],
        direction="out",
        neighbour_label=spec.label_of(path.end),
        expected_ids=ordered,
        expected_names=_names(spec, ordered),
        uses_inferred=path.uses_inferred,
        homogeneous=any(
            spec.label_of(s) == spec.label_of(t) for s, _e, t in path.steps
        ),
        note=f"planted path {path_name}, {path.length} hops",
        author_view={
            "label": start["label"],
            "name": start["name"],
            "relationship": " then ".join(e for _s, e, _t in path.steps),
            "direction": "out",
        },
    )


def unanswerable_gold(
    spec: TenantSpec, anchor: str, edge: str, qid: str, note: str
) -> GoldEntry:
    """Gold for a question the schema cannot support: the empty set.

    The arm is expected to abstain and to carry the query that proves the
    absence. Returning rows here is a failure whatever the rows are.
    """
    node = spec.nodes[anchor]
    return GoldEntry(
        question_id=qid,
        kind=UNANSWERABLE,
        anchor_id=anchor,
        anchor_label=node["label"],
        anchor_name=node["name"],
        edge=edge,
        direction="out",
        neighbour_label=None,
        expected_ids=[],
        expected_names=[],
        uses_inferred=False,
        homogeneous=False,
        note=note,
        author_view={
            "label": node["label"],
            "name": node["name"],
            "relationship": edge,
            "direction": "out",
        },
    )


def write_gold(entries: list[GoldEntry], path: str | Path, meta: dict) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": meta,
        "counts_by_kind": {
            kind: sum(1 for e in entries if e.kind == kind) for kind in KINDS
        },
        "entries": {e.question_id: e.to_dict() for e in entries},
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def read_gold(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
