r"""Enumerate answerable question specifications, with gold, from the raw graph.

This is the generator's deterministic half. It walks `raw_graph` and emits
**specs**: a structured description of a question, the path that answers it, and
the gold set computed by walking that path. No model is involved and none may
be — a spec's gold must be a fact about the sources, not a model's opinion about
them. `Fable` renders a spec into English later; if it ever influenced the
answer, every score computed against that gold would be circular.

Difficulty is a structural fact, not a label someone applied:

| tier | shape |
|------|-------|
| D0   | plausible but unanswerable — gold is empty *by construction* |
| D1   | read one property of one named entity |
| D2   | one hop, forward |
| D3   | one hop, reverse |
| D4   | two hops, one source |
| D5   | one hop plus a facet filter, or a count |
| D6   | cross-source: the path spans ATT&CK and CAPEC |

The tiers are a hypothesis, not a result. `EXP` must show that tier predicts
score before they are worth reporting; if D4 does not sit below D2, they are
decoration and should be dropped rather than defended.

**The neutral query form.** Each spec carries `query`, a declarative path in
JSON — start node, steps, filters, return field. It is deliberately not Cypher
and not Gremlin: a gold query written in one dialect would favour whichever arm
speaks it, which is the circularity that has blocked releasing executable gold
(Q26). Renderers to both dialects belong with the release, not here.

Two exclusions that matter, both from the census:

* **Dangling cross-source references.** CAPEC declares 10 ATT&CK technique ids
  the pinned bundle has no live object for. A D6 spec anchored on one would have
  gold that is empty for a reason the question does not disclose, so they are
  excluded from D6 — and are exactly the right material for D0.
* **No fan-out cap.** Q29 measured judged score against gold width across 3,479
  judgments and found no effect, so width is recorded on every spec and
  stratified over later, never used to reject.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from utils.specialists.evalset import raw_graph as rg
from utils.specialists.evalset.raw_graph import RawGraph

#: Properties that make a poor question: bundle bookkeeping, or the identifier
#: the question already had to use to name the anchor.
UNASKABLE_PROPERTIES = frozenset({
    "x_mitre_version", "x_mitre_attack_spec_version", "x_mitre_domains",
    "x_mitre_first_seen_citation", "x_mitre_last_seen_citation",
    "name", "Name", "id", "Status",
})

#: Sub-element labels: instances of a parent, with no independent identity.
DERIVED_LABELS = frozenset({
    "ExecutionStep", "Consequence", "Skill", "CapecMitigation", "Prerequisite",
    "Indicator", "Example", "Resource", "AlternateTerm",
})


@dataclass(frozen=True)
class Step:
    predicate: str
    reverse: bool
    label: str  # the label arrived at

    def describe(self) -> str:
        arrow = "<-" if self.reverse else "->"
        return f"{arrow}[{self.predicate}]{arrow[::-1] if self.reverse else ''} {self.label}"


@dataclass(frozen=True)
class Filter:
    label: str
    property: str
    op: str  # eq | absent
    value: Any = None


@dataclass
class Spec:
    """One question, its answer path, and the gold that path produces."""

    id: str
    tier: str
    kind: str  # property | traverse | constrained | count | negative
    source: str  # attack | capec | federated
    anchor_id: str
    anchor_key: str
    anchor_label: str
    anchor_name: str | None
    steps: tuple[Step, ...]
    filters: tuple[Filter, ...]
    return_label: str
    return_field: str
    gold: tuple[str, ...]
    gold_width: int
    gold_kind: str  # set | text — a paragraph and an id set need different metrics
    dangling: tuple[str, ...]  # declared but not retrievable; see gold_and_dangling
    shapes: tuple[str, ...]
    query: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [asdict(s) for s in self.steps]
        payload["filters"] = [asdict(f) for f in self.filters]
        return payload


# ---------------------------------------------------------------------------
# path walking — the only place gold is ever produced
# ---------------------------------------------------------------------------


def walk(graph: RawGraph, start: str, steps: Sequence[Step]) -> list[str]:
    """Node ids reachable from `start` along `steps`. Deterministic and sorted.

    Each frontier node is expanded to its aliases before stepping. That is the
    only place the two catalogues are joined: a technique reached through
    CAPEC's taxonomy mapping is a placeholder carrying no ATT&CK edges, and
    without the alias expansion every cross-source path would dead-end at the
    bridge — silently, with an empty gold set that looks like a data gap.
    """
    frontier = [start]
    for step in steps:
        nxt: set[str] = set()
        for node_id in frontier:
            for alias in graph.aliases(node_id):
                for reached in graph.step(alias, step.predicate, reverse=step.reverse):
                    node = graph.nodes.get(reached)
                    if node and node.label == step.label:
                        nxt.add(reached)
        frontier = sorted(nxt)
        if not frontier:
            return []
    return frontier


def _passes(graph: RawGraph, node_id: str, filters: Sequence[Filter]) -> bool:
    node = graph.nodes.get(node_id)
    if node is None:
        return False
    for flt in filters:
        if node.label != flt.label:
            continue
        value = node.properties.get(flt.property)
        if flt.op == "absent":
            if value not in (None, [], ""):
                return False
        elif flt.op == "eq":
            values = value if isinstance(value, list) else [value]
            if flt.value not in values:
                return False
    return True


def _answer_key(graph: RawGraph, node_id: str) -> str:
    """What the gold set records: the id a question can be graded against."""
    node = graph.nodes[node_id]
    return node.key or node.id


def gold_for(
    graph: RawGraph, start: str, steps: Sequence[Step], filters: Sequence[Filter] = ()
) -> tuple[str, ...]:
    """The retrievable answer: what a correct system could actually return."""
    return gold_and_dangling(graph, start, steps, filters)[0]


def gold_and_dangling(
    graph: RawGraph, start: str, steps: Sequence[Step], filters: Sequence[Filter] = ()
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split what a path reaches into retrievable answers and dangling ids.

    CAPEC declares 10 ATT&CK technique ids the pinned bundle has no live object
    for. A path that lands on one has reached a *declared* answer that is not a
    *retrievable* one, and the two are different questions:

    * "which techniques does CAPEC-13 map to" is answered by the declaration,
      dangling ids included — that is what CAPEC says;
    * "which mitigations apply to the techniques CAPEC-13 maps to" can only be
      answered from techniques that exist, so a dangling id contributes nothing.

    Both are recorded. Silently keeping them would make federated chains grade
    against answers no system can produce; silently dropping them would hide the
    catalogues' version skew inside a gold set. Neither is acceptable, so the
    split is explicit and travels with the spec.
    """
    reached = walk(graph, start, steps)
    kept = [n for n in reached if _passes(graph, n, filters)]
    live = {_answer_key(graph, n) for n in kept if not graph.is_dangling(n)}
    dead = {_answer_key(graph, n) for n in kept if graph.is_dangling(n)}
    return tuple(sorted(live)), tuple(sorted(dead))


def neutral_query(spec_parts: dict[str, Any]) -> dict[str, Any]:
    """The dialect-free path a release ships as executable gold."""
    return {
        "start": spec_parts["start"],
        "steps": spec_parts["steps"],
        "filters": spec_parts["filters"],
        "return": spec_parts["return"],
    }


def _crosses_stores(graph: RawGraph, start_label: str, steps: Sequence[Step]) -> bool:
    """True when the path uses the one cross-source edge type.

    Federation in this snapshot rests entirely on
    `AttackPattern -[MAPS_TO[ATTACK]]-> Technique`. A path is cross-source
    exactly when it traverses that predicate, in either direction.
    """
    return any(step.predicate == "MAPS_TO[ATTACK]" for step in steps)


def _make_spec(
    graph: RawGraph,
    *,
    spec_id: str,
    tier: str,
    kind: str,
    anchor: rg.Node,
    steps: tuple[Step, ...],
    filters: tuple[Filter, ...],
    return_label: str,
    return_field: str,
    gold: tuple[str, ...],
    shapes: tuple[str, ...],
    gold_kind: str = "set",
    dangling: tuple[str, ...] = (),
) -> Spec:
    # Federated means the path traverses the one cross-source edge type — not
    # that it happens to touch a label the other catalogue also names.
    source = "federated" if _crosses_stores(graph, anchor.label, steps) else anchor.source
    return Spec(
        id=spec_id,
        tier=tier,
        kind=kind,
        source=source,
        anchor_id=anchor.id,
        anchor_key=anchor.key or anchor.id,
        anchor_label=anchor.label,
        anchor_name=anchor.name,
        steps=steps,
        filters=filters,
        return_label=return_label,
        return_field=return_field,
        gold=gold,
        gold_width=len(gold),
        gold_kind=gold_kind,
        dangling=dangling,
        shapes=shapes,
        query=neutral_query(
            {
                "start": {"label": anchor.label, "key": anchor.key or anchor.id},
                "steps": [
                    {
                        "predicate": s.predicate,
                        "direction": "in" if s.reverse else "out",
                        "label": s.label,
                    }
                    for s in steps
                ],
                "filters": [asdict(f) for f in filters],
                "return": {"label": return_label, "field": return_field},
            }
        ),
    )


# ---------------------------------------------------------------------------
# anchors
# ---------------------------------------------------------------------------


def anchors(graph: RawGraph, label: str) -> list[rg.Node]:
    """Entities of a label that a question can name. Sorted, so draws repeat."""
    return sorted(
        (
            n
            for n in graph.by_label(label)
            if n.key and n.label not in DERIVED_LABELS and not n.placeholder
        ),
        key=lambda n: n.id,
    )


def _sample(items: Sequence[Any], limit: int | None, seed: int, salt: str) -> list[Any]:
    """Deterministic subsample. Same (items, limit, seed, salt) -> same draw."""
    pool = list(items)
    if limit is None or len(pool) <= limit:
        return pool
    rng = random.Random(f"{seed}:{salt}")
    return sorted(rng.sample(pool, limit), key=lambda x: getattr(x, "id", x))


# ---------------------------------------------------------------------------
# tiers
# ---------------------------------------------------------------------------


def _edge_shapes(graph: RawGraph) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for subject, predicate, obj, _source, _origin in graph.triples():
        counts[(subject, predicate, obj)] += 1
    return dict(counts)


def _triple(subject: str, predicate: str, obj: str) -> str:
    return f"{subject} -[{predicate}]-> {obj}"


def property_kinds(census: dict[str, Any]) -> dict[tuple[str, str], str]:
    """(label, property) -> census kind. D1 asks only what a person can answer."""
    return {
        (node["label"], prop["name"]): prop["kind"]
        for node in census["nodes"]
        for prop in node["properties"]
    }


def property_specs(
    graph: RawGraph, census: dict[str, Any], *, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D1 — read one property of one named entity.

    `structured` properties are skipped: `x_mitre_log_source_references` is a
    list of dicts, and no natural question has a list of dicts as its answer.
    `text` properties are kept but marked, because a paragraph is graded by
    containment and a set of ids is graded by overlap — conflating them would
    make one metric wrong for half the tier.
    """
    kinds = property_kinds(census)
    by_label: dict[str, list[rg.Node]] = defaultdict(list)
    for node in graph.nodes.values():
        if graph.is_entity(node) and node.key and node.label not in DERIVED_LABELS:
            by_label[node.label].append(node)

    for label in sorted(by_label):
        properties = sorted(
            {
                key
                for node in by_label[label]
                for key, value in node.properties.items()
                if key not in UNASKABLE_PROPERTIES
                and value not in (None, [], "")
                and kinds.get((label, key)) != "structured"
            }
        )
        for prop in properties:
            eligible = sorted(
                (n for n in by_label[label] if n.properties.get(prop) not in (None, [], "")),
                key=lambda n: n.id,
            )
            for node in _sample(eligible, limit, seed, f"D1:{label}:{prop}"):
                value = node.properties[prop]
                gold = tuple(sorted(str(v) for v in (value if isinstance(value, list) else [value])))
                yield _make_spec(
                    graph,
                    spec_id=f"D1-{label}-{prop}-{node.key}",
                    tier="D1",
                    kind="property",
                    anchor=node,
                    steps=(),
                    filters=(),
                    return_label=label,
                    return_field=prop,
                    gold=gold,
                    gold_kind="text" if kinds.get((label, prop)) == "text" else "set",
                    shapes=(f"{label}.{prop}",),
                )


def hop_specs(
    graph: RawGraph, *, reverse: bool, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D2 (forward) and D3 (reverse) — one hop from a named entity."""
    tier = "D3" if reverse else "D2"
    for (subject, predicate, obj), _count in sorted(_edge_shapes(graph).items()):
        start_label, end_label = (obj, subject) if reverse else (subject, obj)
        if start_label in DERIVED_LABELS:
            continue
        eligible = [
            n
            for n in anchors(graph, start_label)
            if graph.step(n.id, predicate, reverse=reverse)
        ]
        step = (Step(predicate=predicate, reverse=reverse, label=end_label),)
        for node in _sample(eligible, limit, seed, f"{tier}:{subject}:{predicate}:{obj}"):
            gold, dead = gold_and_dangling(graph, node.id, step)
            if not gold:
                continue
            yield _make_spec(
                graph,
                spec_id=f"{tier}-{predicate}-{node.key}",
                tier=tier,
                kind="traverse",
                anchor=node,
                steps=step,
                filters=(),
                return_label=end_label,
                return_field="key",
                gold=gold,
                dangling=dead,
                shapes=(_triple(subject, predicate, obj),),
            )


def two_hop_specs(
    graph: RawGraph, *, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D4 — two hops inside one source, D6 when the path crosses stores."""
    shapes = _edge_shapes(graph)
    # Index shapes by the label each direction leaves you standing on.
    from_label: dict[str, list[tuple[str, str, str, bool]]] = defaultdict(list)
    for subject, predicate, obj in shapes:
        from_label[subject].append((subject, predicate, obj, False))
        from_label[obj].append((subject, predicate, obj, True))

    for start_label in sorted(from_label):
        if start_label in DERIVED_LABELS:
            continue
        for s1, p1, o1, rev1 in sorted(from_label[start_label]):
            mid = s1 if rev1 else o1
            for s2, p2, o2, rev2 in sorted(from_label.get(mid, [])):
                end = s2 if rev2 else o2
                # A second hop that immediately undoes the first is not a
                # two-hop question, it is the anchor's own neighbourhood.
                if (p1, not rev1) == (p2, rev2):
                    continue
                if end == start_label and p1 == p2:
                    continue
                steps = (
                    Step(predicate=p1, reverse=rev1, label=mid),
                    Step(predicate=p2, reverse=rev2, label=end),
                )
                salt = f"D4:{start_label}:{p1}:{rev1}:{p2}:{rev2}"
                eligible = [n for n in anchors(graph, start_label) if walk(graph, n.id, steps)]
                if not eligible:
                    continue
                crosses = _crosses_stores(graph, start_label, steps)
                tier = "D6" if crosses else "D4"
                for node in _sample(eligible, limit, seed, salt):
                    gold = gold_for(graph, node.id, steps)
                    if not gold:
                        continue
                    yield _make_spec(
                        graph,
                        spec_id=f"{tier}-{p1}-{p2}-{node.key}",
                        tier=tier,
                        kind="traverse",
                        anchor=node,
                        steps=steps,
                        filters=(),
                        return_label=end,
                        return_field="key",
                        gold=gold,
                        shapes=(
                            _triple(s1, p1, o1),
                            _triple(s2, p2, o2),
                        ),
                    )


def constrained_specs(
    graph: RawGraph, census: dict[str, Any], *, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D5 — one hop plus a facet filter on what the hop lands on.

    Facets come from the census, so this tier can only ask what the data
    actually supports filtering by. The banks contain none of these.
    """
    facets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for node_type in census["nodes"]:
        for prop in node_type["properties"]:
            if prop["facet"]:
                for value in prop["values"]:
                    facets[node_type["label"]].append((prop["name"], value))

    for (subject, predicate, obj), _count in sorted(_edge_shapes(graph).items()):
        if obj not in facets or subject in DERIVED_LABELS:
            continue
        for prop, value in sorted(facets[obj]):
            flt = (Filter(label=obj, property=prop, op="eq", value=value),)
            step = (Step(predicate=predicate, reverse=False, label=obj),)
            salt = f"D5:{subject}:{predicate}:{obj}:{prop}:{value}"
            # A constraint that removes nothing is decoration: the question
            # reads as constrained and grades identically to the unconstrained
            # one, so a system that ignores the filter scores full marks.
            eligible = [
                n
                for n in anchors(graph, subject)
                if (filtered := gold_for(graph, n.id, step, flt))
                and filtered != gold_for(graph, n.id, step)
            ]
            if not eligible:
                continue
            for node in _sample(eligible, limit, seed, salt):
                gold = gold_for(graph, node.id, step, flt)
                if not gold:
                    continue
                yield _make_spec(
                    graph,
                    spec_id=f"D5-{predicate}-{prop}-{node.key}",
                    tier="D5",
                    kind="constrained",
                    anchor=node,
                    steps=step,
                    filters=flt,
                    return_label=obj,
                    return_field="key",
                    gold=gold,
                    shapes=(_triple(subject, predicate, obj),),
                )


def negative_specs(
    graph: RawGraph, *, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D0 — plausible questions whose gold is empty by construction.

    Two kinds, and both are honest rather than nonsense:

    * a predicate that exists in the graph but never from this label — the shape
      is real, the combination is not;
    * a CAPEC pattern whose declared ATT&CK id the bundle has no live object
      for. Those are the federation's actual failure surface, so an abstention
      there is a property worth measuring rather than a trick.
    """
    shapes = _edge_shapes(graph)
    predicates_of: dict[str, set[str]] = defaultdict(set)
    subjects_of: dict[str, set[str]] = defaultdict(set)
    for subject, predicate, _obj in shapes:
        predicates_of[subject].add(predicate)
        subjects_of[predicate].add(subject)
    all_predicates = set(subjects_of)
    targets = {(p, o) for _s, p, o in shapes}

    # A label's source, for the plausibility rule below. Placeholders are
    # excluded: CAPEC declares ATT&CK technique ids, so counting them would put
    # `Technique` in both catalogues and let every CAPEC predicate through.
    source_of: dict[str, set[str]] = defaultdict(set)
    for node in graph.nodes.values():
        if not node.placeholder:
            source_of[node.label].add(node.source)

    for label in sorted(predicates_of):
        if label in DERIVED_LABELS:
            continue
        absent = sorted(all_predicates - predicates_of[label])
        for predicate in absent:
            # Plausibility: the predicate must be one that some label in the
            # same catalogue carries. Without this the tier fills with category
            # errors — "which attack patterns can this ATT&CK analytic also be"
            # tests nothing, because no analyst would ask it and abstaining is
            # not a judgement call.
            peers = {src for s in subjects_of[predicate] for src in source_of.get(s, set())}
            if not (peers & source_of.get(label, set())):
                continue
            end = sorted({o for p, o in targets if p == predicate})
            if not end:
                continue
            step = (Step(predicate=predicate, reverse=False, label=end[0]),)
            eligible = [n for n in anchors(graph, label) if not walk(graph, n.id, step)]
            for node in _sample(eligible, limit, seed, f"D0:{label}:{predicate}"):
                yield _make_spec(
                    graph,
                    spec_id=f"D0-{label}-{predicate}-{node.key}",
                    tier="D0",
                    kind="negative",
                    anchor=node,
                    steps=step,
                    filters=(),
                    return_label=end[0],
                    return_field="key",
                    gold=(),
                    shapes=(_triple(label, predicate, end[0]),),
                )

    dangling = {n.id for n in graph.dangling()}
    if dangling:
        eligible = [
            n
            for n in anchors(graph, "AttackPattern")
            if graph.out(n.id, "MAPS_TO[ATTACK]")
            and set(graph.out(n.id, "MAPS_TO[ATTACK]")) <= dangling
        ]
        for node in _sample(eligible, limit, seed, "D0:dangling"):
            yield _make_spec(
                graph,
                spec_id=f"D0-dangling-{node.key}",
                tier="D0",
                kind="negative",
                anchor=node,
                steps=(Step(predicate="MAPS_TO[ATTACK]", reverse=False, label="Technique"),),
                filters=(),
                return_label="Technique",
                return_field="key",
                gold=(),
                shapes=("AttackPattern -[MAPS_TO[ATTACK]]-> Technique",),
            )


def cross_source_specs(
    graph: RawGraph, *, limit: int | None = None, seed: int = 0
) -> Iterator[Spec]:
    """D6 — paths that must cross from CAPEC into ATT&CK, or back.

    Two-hop enumeration reaches these only when both hops happen to line up, and
    it found 7 shape-pairs. The federated questions an analyst actually asks are
    three hops — "which mitigations apply to the techniques CAPEC-66 maps to" —
    so they are generated explicitly rather than hoped for.

    Anchors whose every mapped technique is a dangling reference are excluded:
    their gold would be empty for a reason the question does not disclose. They
    are emitted as D0 instead, where empty is the point.
    """
    bridge = "MAPS_TO[ATTACK]"
    technique_steps: list[tuple[str, bool, str]] = []
    for subject, predicate, obj in sorted(_edge_shapes(graph)):
        if predicate == bridge:
            continue
        if obj == "Technique":
            technique_steps.append((predicate, True, subject))
        if subject == "Technique":
            technique_steps.append((predicate, False, obj))

    dangling = {n.id for n in graph.dangling()}

    # CAPEC -> Technique -> anywhere in ATT&CK
    for predicate, reverse, end in sorted(set(technique_steps)):
        steps = (
            Step(predicate=bridge, reverse=False, label="Technique"),
            Step(predicate=predicate, reverse=reverse, label=end),
        )
        eligible = [
            n
            for n in anchors(graph, "AttackPattern")
            if set(graph.out(n.id, bridge)) - dangling and walk(graph, n.id, steps)
        ]
        for node in _sample(eligible, limit, seed, f"D6:out:{predicate}:{reverse}:{end}"):
            gold = gold_for(graph, node.id, steps)
            if not gold:
                continue
            yield _make_spec(
                graph,
                spec_id=f"D6-{bridge}-{predicate}-{node.key}",
                tier="D6",
                kind="traverse",
                anchor=node,
                steps=steps,
                filters=(),
                return_label=end,
                return_field="key",
                gold=gold,
                shapes=(
                    "AttackPattern -[MAPS_TO[ATTACK]]-> Technique",
                    _triple(end, predicate, "Technique")
                    if reverse
                    else _triple("Technique", predicate, end),
                ),
            )

    # ATT&CK -> Technique -> CAPEC (the reverse-mapping direction, which the
    # blind holdout showed is the harder one).
    for predicate, reverse, end in sorted(set(technique_steps)):
        steps = (
            Step(predicate=predicate, reverse=not reverse, label="Technique"),
            Step(predicate=bridge, reverse=True, label="AttackPattern"),
        )
        eligible = [n for n in anchors(graph, end) if walk(graph, n.id, steps)]
        for node in _sample(eligible, limit, seed, f"D6:in:{predicate}:{reverse}:{end}"):
            gold = gold_for(graph, node.id, steps)
            if not gold:
                continue
            yield _make_spec(
                graph,
                spec_id=f"D6-rev-{predicate}-{node.key}",
                tier="D6",
                kind="traverse",
                anchor=node,
                steps=steps,
                filters=(),
                return_label="AttackPattern",
                return_field="key",
                gold=gold,
                shapes=(
                    _triple(end, predicate, "Technique")
                    if reverse
                    else _triple("Technique", predicate, end),
                    "AttackPattern -[MAPS_TO[ATTACK]]-> Technique",
                ),
            )


# ---------------------------------------------------------------------------


TIER_BUILDERS = ("D0", "D1", "D2", "D3", "D4", "D5", "D6")


def enumerate_specs(
    graph: RawGraph,
    census: dict[str, Any],
    *,
    per_shape_limit: int | None = 3,
    seed: int = 20260901,
    tiers: Iterable[str] = TIER_BUILDERS,
) -> list[Spec]:
    """Every tier, deterministically sampled per shape.

    `per_shape_limit` bounds anchors per shape rather than specs overall, so a
    rare shape is represented as well as a common one. That is the property the
    expansion needs: under-represented corners must not be crowded out by
    `Software -uses-> Technique`.
    """
    wanted = set(tiers)
    specs: list[Spec] = []
    if "D1" in wanted:
        specs += list(property_specs(graph, census, limit=per_shape_limit, seed=seed))
    if "D2" in wanted:
        specs += list(hop_specs(graph, reverse=False, limit=per_shape_limit, seed=seed))
    if "D3" in wanted:
        specs += list(hop_specs(graph, reverse=True, limit=per_shape_limit, seed=seed))
    if wanted & {"D4", "D6"}:
        specs += [
            s
            for s in two_hop_specs(graph, limit=per_shape_limit, seed=seed)
            if s.tier in wanted
        ]
    if "D5" in wanted:
        specs += list(constrained_specs(graph, census, limit=per_shape_limit, seed=seed))
    if "D6" in wanted:
        specs += list(cross_source_specs(graph, limit=per_shape_limit, seed=seed))
    if "D0" in wanted:
        specs += list(negative_specs(graph, limit=per_shape_limit, seed=seed))

    specs.sort(key=lambda s: (s.tier, s.id))
    return specs


def summarise(specs: Sequence[Spec]) -> dict[str, Any]:
    by_tier: dict[str, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    widths: list[int] = []
    shapes: set[str] = set()
    for spec in specs:
        by_tier[spec.tier] += 1
        by_source[spec.source] += 1
        shapes.update(spec.shapes)
        if spec.tier != "D0":
            widths.append(spec.gold_width)
    widths.sort()
    return {
        "specs": len(specs),
        "by_tier": dict(sorted(by_tier.items())),
        "by_source": dict(sorted(by_source.items())),
        "distinct_shapes": len(shapes),
        "gold_width": {
            "min": widths[0] if widths else 0,
            "median": widths[len(widths) // 2] if widths else 0,
            "p90": widths[int(0.9 * (len(widths) - 1))] if widths else 0,
            "max": widths[-1] if widths else 0,
        },
        "empty_gold_outside_D0": sum(
            1 for s in specs if s.tier != "D0" and not s.gold
        ),
    }


def write(specs: Sequence[Spec], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"summary": summarise(specs), "specs": [s.to_json() for s in specs]}
    path.write_text(json.dumps(payload, indent=1) + "\n")
