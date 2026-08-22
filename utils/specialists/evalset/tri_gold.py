#!/usr/bin/env python3
"""Gold for the tri-source bank: the customer graph joined to ATT&CK.

Two provenances, and neither is a query against the system under test.

The identity side comes from the generator blueprint, exactly as
``identity_gold`` does — which anchors hold which edges is a fact the generator
recorded before anything was loaded.

The ATT&CK side comes from the **declared correspondence**
(``utils.planner.edge_correspondence``) and from ATT&CK's own canonical export,
read off disk. It is not read from the live store. The mitigations of T1003.006
are a fact of a public catalogue rather than something this system computes, so
using them is the same move as using the blueprint — but reading the export
rather than the running database keeps the rule intact without needing an
argument for an exception.

**The honest limit, stated where it cannot be missed.** The mapping is authored
by us. A score computed against this gold measures whether the system *uses the
declared bridge correctly* — routes to both sources, walks the right edge,
produces the right technique ids, seeds ATT&CK with them, and abstains where the
declaration says there is nothing to assert. It does **not** measure whether the
mapping is right. Nothing here can, and a figure quoted without that sentence is
being quoted wrongly.

Five kinds, and the last three are the ones that make this a measurement rather
than a demonstration:

``bridge-technique``   an anchor and one mapped edge; which technique is that?
``bridge-mitigation``  the same, plus what ATT&CK says mitigates it.
``bridge-refusal``     an anchor whose edges are all declared NOT a technique.
                       Naming any technique is a false claim.
``bridge-partial``     an anchor holding one half of the DCSync right pair.
                       The customer's own catalog says that is insufficient, so
                       claiming T1003.006 asserts what they deny.
``identity-control``   an ordinary identity question. Reaching ATT&CK at all is
                       contamination, and this is what proves the bridge is
                       inert when it is not invoked.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils.kg_builder.synthetic.spec import TenantSpec
from utils.planner.edge_correspondence import (
    NOT_A_TECHNIQUE,
    correspondence_for,
    mapped_edges,
    produced_technique_ids,
)

from .identity_gold import GoldEntry

BRIDGE_TECHNIQUE = "bridge-technique"
BRIDGE_MITIGATION = "bridge-mitigation"
BRIDGE_REFUSAL = "bridge-refusal"
BRIDGE_PARTIAL = "bridge-partial"
IDENTITY_CONTROL = "identity-control"

KINDS = (
    BRIDGE_TECHNIQUE,
    BRIDGE_MITIGATION,
    BRIDGE_REFUSAL,
    BRIDGE_PARTIAL,
    IDENTITY_CONTROL,
)

# Kinds whose correct answer is that NO technique may be asserted. Scored by
# leakage, like ``unanswerable`` in the identity bank.
REFUSAL_KINDS = frozenset({BRIDGE_REFUSAL, BRIDGE_PARTIAL, IDENTITY_CONTROL})

TRI_SEED = 20260822

_ATTACK_CANONICAL = Path("data-tri/graphs/attack/canonical")


# -- ATT&CK facts, read off the canonical export ----------------------------


def attack_index(canonical: str | Path | None = None) -> dict[str, Any]:
    """``{attack_id -> name}`` and ``{technique_id -> [mitigation_id...]}``.

    Read from the export rather than the live store, so gold never comes from
    the database the run will query.
    """
    base = Path(canonical or _ATTACK_CANONICAL)
    by_stix: dict[str, str] = {}
    names: dict[str, str] = {}
    for line in (base / "nodes.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        aid = (node.get("properties") or {}).get("attack_id")
        if aid:
            by_stix[node["id"]] = aid
            names[aid] = node.get("name") or ""
    mitigations: dict[str, list[str]] = defaultdict(list)
    for line in (base / "relationships.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rel = json.loads(line)
        if rel.get("type") != "MITIGATES":
            continue
        src = by_stix.get(rel.get("source_id") or "")
        dst = by_stix.get(rel.get("target_id") or "")
        if src and dst:
            mitigations[dst].append(src)
    return {"names": names, "mitigations": {k: sorted(set(v)) for k, v in mitigations.items()}}


# -- blueprint views ---------------------------------------------------------


def _edges_by_anchor(spec: TenantSpec, *, both_directions: bool = False) -> dict[str, set[str]]:
    """Edge types touching each node — outgoing only, or in either direction.

    ``both_directions`` matters for the negative controls and nothing else. A
    positive question is about a right the anchor *holds*, so outgoing is the
    right view. But the runtime walk is direction-agnostic (``-[r]-``), so an
    anchor selected as "holds no mapped edge" on outgoing edges alone can still
    have one pointing **at** it and legitimately produce a technique.

    That is not hypothetical: the first draw of this bank picked `dc202` as a
    refusal control because its only outgoing edge is RUNS_AS, and the run
    produced T1098 — from a WRITE_ACCOUNT_RESTRICTIONS edge held *over* it by
    something else. The declaration was right, the system was right, and the
    gold was wrong. Scored naively that reads as the bridge inventing a
    technique, which is the most damaging thing this bank could get wrong.
    """
    out: dict[str, set[str]] = defaultdict(set)
    for edge in spec.edges:
        out[edge["source_id"]].add(edge["edge"])
        if both_directions:
            out[edge["target_id"]].add(edge["edge"])
    return out


def _anchor_fields(spec: TenantSpec, anchor: str) -> tuple[str, str]:
    node = spec.nodes[anchor]
    return node["label"], node["name"]


# -- gold builders -----------------------------------------------------------


def bridge_gold(
    spec: TenantSpec,
    anchor: str,
    edge: str,
    qid: str,
    index: dict[str, Any],
    *,
    with_mitigations: bool,
) -> GoldEntry:
    """Gold for "anchor holds <edge>; which technique is that (and what stops it)".

    Scoped to the **named edge**, not to everything the anchor holds. Every
    anchor in this tenant that has any mapped edge has several, so gold over all
    of them would be satisfied by walking the wrong one — which is precisely the
    scoping failure worth measuring.
    """
    label, name = _anchor_fields(spec, anchor)
    techniques = list(produced_technique_ids([edge]))
    expected = list(techniques)
    if with_mitigations:
        for tid in techniques:
            expected.extend(index["mitigations"].get(tid, []))
    expected = sorted(set(expected))
    entry = correspondence_for(edge)
    return GoldEntry(
        question_id=qid,
        kind=BRIDGE_MITIGATION if with_mitigations else BRIDGE_TECHNIQUE,
        anchor_id=anchor,
        anchor_label=label,
        anchor_name=name,
        edge=edge,
        direction="out",
        neighbour_label=None,
        expected_ids=expected,
        expected_names=sorted({index["names"].get(e, e) for e in expected}),
        uses_inferred=False,
        homogeneous=False,
        note=(
            f"declared correspondence: {edge} -> {', '.join(techniques)}"
            + (f"; basis {entry.basis}" if entry else "")
        ),
        author_view={
            "label": label,
            "name": name,
            "relationship": edge,
            "direction": "out",
            "wants": "mitigation" if with_mitigations else "technique",
        },
    )


def refusal_gold(
    spec: TenantSpec, anchor: str, edge: str, qid: str, kind: str
) -> GoldEntry:
    """Gold for an anchor whose edge establishes no technique.

    ``expected_ids`` is empty and that is the answer, not a gap. The score is a
    leakage check: naming any ATT&CK technique is a false claim, whether it came
    from the bridge or from a keyword landing in the catalogue by accident.
    """
    label, name = _anchor_fields(spec, anchor)
    if kind == BRIDGE_PARTIAL:
        note = (
            f"{edge} is HALF of the DCSync right pair; the catalog says it is "
            "insufficient alone, so T1003.006 must not be asserted"
        )
    else:
        note = f"{edge} is declared not-a-technique: {NOT_A_TECHNIQUE.get(edge, '')}"
    return GoldEntry(
        question_id=qid,
        kind=kind,
        anchor_id=anchor,
        anchor_label=label,
        anchor_name=name,
        edge=edge,
        direction="out",
        neighbour_label=None,
        expected_ids=[],
        expected_names=[],
        uses_inferred=False,
        homogeneous=False,
        note=note,
        author_view={
            "label": label,
            "name": name,
            "relationship": edge,
            "direction": "out",
            "wants": "technique",
        },
    )


def control_gold(spec: TenantSpec, anchor: str, edge: str, qid: str) -> GoldEntry:
    """An ordinary identity question. Reaching ATT&CK at all is contamination."""
    label, name = _anchor_fields(spec, anchor)
    neighbours = spec.neighbours(anchor, edge=edge, direction="out")
    return GoldEntry(
        question_id=qid,
        kind=IDENTITY_CONTROL,
        anchor_id=anchor,
        anchor_label=label,
        anchor_name=name,
        edge=edge,
        direction="out",
        neighbour_label=None,
        expected_ids=sorted(neighbours),
        expected_names=sorted({spec.name_of(n) for n in neighbours}),
        uses_inferred=False,
        homogeneous=False,
        note="identity-only; no ATT&CK technique may appear in the evidence",
        author_view={
            "label": label,
            "name": name,
            "relationship": edge,
            "direction": "out",
            "wants": "plain",
        },
    )


# -- sampler -----------------------------------------------------------------


def draw(
    spec: TenantSpec,
    *,
    seed: int = TRI_SEED,
    n_technique: int = 24,
    n_mitigation: int = 16,
    n_refusal: int = 12,
    n_partial: int = 9,
    n_control: int = 12,
    canonical: str | Path | None = None,
) -> list[GoldEntry]:
    """Draw the bank. Deterministic in ``seed``; never touches a database."""
    rng = random.Random(seed)
    index = attack_index(canonical)
    by_anchor = _edges_by_anchor(spec)
    touching = _edges_by_anchor(spec, both_directions=True)
    mapped = mapped_edges()

    # (anchor, edge) pairs where the edge carries a whole technique.
    whole = sorted(
        (a, e)
        for a, edges in by_anchor.items()
        for e in edges
        if e in mapped and produced_technique_ids([e])
    )
    rng.shuffle(whole)

    # A partial right in isolation. NOT DRAWABLE from this tenant: every anchor
    # holding GET_CHANGES also holds another mapped right in some direction --
    # usually ALL_EXTENDED_RIGHTS, which the declaration maps to T1003.006 in
    # its own right, on the customer's wording that it includes "on a domain,
    # the replication rights". So a T1003.006 in the evidence cannot be
    # attributed to the half-right rather than to the whole one, and the control
    # cannot distinguish the behaviour it exists to test. Left here, empty and
    # explained, rather than drawn wrongly: testing it needs a tenant generated
    # with an isolated replication right, which is a new experiment.
    partial_pairs: list[tuple[str, str]] = [
        (a, "GET_CHANGES")
        for a, edges in touching.items()
        if "GET_CHANGES" in edges
        and "GET_CHANGES_ALL" not in edges
        and not (edges & (mapped - {"GET_CHANGES"}))
    ]
    rng.shuffle(partial_pairs)

    # An anchor no mapped edge touches in EITHER direction, so any technique in
    # the evidence is a false claim rather than a correctly-derived one.
    refusal_pairs = sorted(
        (a, sorted(touching[a] & set(NOT_A_TECHNIQUE))[0])
        for a, edges in touching.items()
        if edges and not (edges & mapped) and (edges & set(NOT_A_TECHNIQUE))
    )
    rng.shuffle(refusal_pairs)

    entries: list[GoldEntry] = []
    used: set[tuple[str, str]] = set()

    def take(pairs: list[tuple[str, str]], want: int) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for pair in pairs:
            if len(out) >= want:
                break
            if pair in used:
                continue
            used.add(pair)
            out.append(pair)
        return out

    for i, (anchor, edge) in enumerate(take(whole, n_technique), 1):
        entries.append(
            bridge_gold(spec, anchor, edge, f"TRI-TECH-{i:02d}", index, with_mitigations=False)
        )
    for i, (anchor, edge) in enumerate(take(whole, n_mitigation), 1):
        entries.append(
            bridge_gold(spec, anchor, edge, f"TRI-MIT-{i:02d}", index, with_mitigations=True)
        )
    for i, (anchor, edge) in enumerate(take(refusal_pairs, n_refusal), 1):
        entries.append(refusal_gold(spec, anchor, edge, f"TRI-REF-{i:02d}", BRIDGE_REFUSAL))
    for i, (anchor, edge) in enumerate(take(partial_pairs, n_partial), 1):
        entries.append(refusal_gold(spec, anchor, edge, f"TRI-PART-{i:02d}", BRIDGE_PARTIAL))
    for i, (anchor, edge) in enumerate(take(refusal_pairs, n_control), 1):
        entries.append(control_gold(spec, anchor, edge, f"TRI-CTL-{i:02d}"))
    return entries
