r"""Enumerate every question shape the pinned raw snapshot actually supports.

The census answers one question that nothing else in the repository answers:
**how much of the graph have we ever asked about?**

`holdout_protocol.ATTACK_CATEGORIES` and friends are a hand-written list of 16
question shapes. They were written from memory, not derived from the data, and
every bank we have ever built draws from them. This module reads the graph
`raw_graph` parses straight out of the pinned files and reports the shapes the
*sources* support: node types, their properties (with the cardinality that
decides whether a property can carry a filter), and every typed edge with its
fan-out in both directions.

Three properties are deliberate and load-bearing:

* **Raw files only** — see `raw_graph`. A census taken through the ingest
  pipeline could only ever report what the pipeline chose to keep, which is the
  opposite of what it is for.
* **Architecture-blind.** Nothing above `COVERAGE` knows that Ariadne has
  templates, primitives, or a composer. The one architecture-aware section is
  the coverage layer at the bottom, isolated on purpose, and it only *reads* the
  census — it cannot change what the census finds.
* **The load-time exclusion policy is mirrored**, so every shape reported is one
  a question could actually be answered from. Exclusions are counted, not
  silently applied.

Fan-out is recorded in both directions because direction is the axis the blind
holdout failed on. An edge with a median forward fan-out of 5 and a median
reverse fan-out of 300 supports a sane forward question and an unanswerable
reverse one, and only the census can tell them apart before a question is
written.

Regenerate with:
    uv run python -m utils.specialists.evalset.schema_census
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from utils.specialists.evalset import raw_graph as rg
from utils.specialists.evalset.raw_graph import DATA_DIR, REPO_ROOT, RawGraph

OUT_DIR = REPO_ROOT / "docs" / "evaluation" / "schema-census"

CENSUS_VERSION = 2

#: A property is `enumerable` when its distinct value count is at or under this.
ENUMERABLE_MAX_DISTINCT = 60
FREETEXT_MEAN_CHARS = 120

#: A property is a `facet` — something a question can *filter* on — when it is
#: enumerable AND its values are genuinely shared across nodes. `name` and
#: `aliases` are enumerable on a 56-node type and are still not filters, so a
#: distinct-count threshold alone is not enough.
FACET_MAX_DISTINCT_RATIO = 0.25

#: Enumerable properties that identify a node or record how the bundle was
#: assembled. Both are real properties and stay in the census; neither is a
#: facet, because "which campaigns are at version 1.1" is not a question.
NON_FACET_PROPERTIES = frozenset({
    "name", "Name", "aliases", "x_mitre_aliases", "x_mitre_shortname",
    "x_mitre_contributors", "x_mitre_version", "x_mitre_domains",
    "x_mitre_first_seen_citation", "x_mitre_last_seen_citation",
})

#: ISO-8601-ish leading value; date properties carry range filters, not equality
#: filters, so they are reported apart from the facets.
_DATEISH = ("19", "20")

#: p90 fan-out at or under this is an answer a grader can score. Recorded as a
#: reported property of each edge, NOT as a filter — Q29 measured the score
#: against gold width and found no effect, so nothing is excluded on it.
ASKABLE_P90 = 50


@dataclass
class PropertyStat:
    """One property of one node type, and whether a question can filter on it."""

    name: str
    kind: str  # scalar | list | text | structured | date
    present: int
    coverage: float
    distinct: int | None
    enumerable: bool
    facet: bool = False
    values: list[str] = field(default_factory=list)


@dataclass
class NodeType:
    source: str
    label: str
    count: int
    unmapped: bool = False
    referenced_only: bool = False
    properties: list[PropertyStat] = field(default_factory=list)


@dataclass
class EdgeType:
    """One typed edge, with the fan-out that decides if it can carry a question."""

    source: str
    subject: str
    predicate: str
    object: str
    count: int
    distinct_subjects: int
    distinct_objects: int
    forward_fanout: dict[str, float]
    reverse_fanout: dict[str, float]
    origin: str
    cross_source: bool = False

    @property
    def triple(self) -> str:
        return f"{self.subject} -[{self.predicate}]-> {self.object}"


def _fanout(pairs: Iterable[tuple[str, str]], *, reverse: bool = False) -> dict[str, float]:
    """Distribution of out-degree (or in-degree) over nodes that have one.

    Nodes with zero edges are excluded on purpose: "how big is the answer when
    there is one" is the question that decides whether a shape is askable.
    """
    grouped: dict[str, set[str]] = defaultdict(set)
    for subj, obj in pairs:
        key, val = (obj, subj) if reverse else (subj, obj)
        grouped[key].add(val)
    sizes = sorted(len(v) for v in grouped.values())
    if not sizes:
        return {"n": 0, "mean": 0.0, "median": 0.0, "p90": 0, "max": 0}
    p90 = sizes[min(len(sizes) - 1, int(round(0.9 * (len(sizes) - 1))))]
    return {
        "n": len(sizes),
        "mean": round(statistics.fmean(sizes), 2),
        "median": float(statistics.median(sizes)),
        "p90": p90,
        "max": sizes[-1],
    }


def _property_stats(instances: list[dict[str, Any]]) -> list[PropertyStat]:
    total = len(instances)
    seen: dict[str, list[Any]] = defaultdict(list)
    for inst in instances:
        for key, value in inst.items():
            if value is None or value == [] or value == "":
                continue
            seen[key].append(value)

    stats: list[PropertyStat] = []
    for name, values in sorted(seen.items()):
        flat: list[str] = []
        structured = False
        listy = False
        for value in values:
            if isinstance(value, list):
                listy = True
                for item in value:
                    if isinstance(item, (dict, list)):
                        structured = True
                    else:
                        flat.append(str(item))
            elif isinstance(value, dict):
                structured = True
            else:
                flat.append(str(value))

        if structured:
            kind = "structured"
        elif flat and statistics.fmean(len(v) for v in flat) > FREETEXT_MEAN_CHARS:
            kind = "text"
        elif flat and all(v[:2] in _DATEISH and v[:4].isdigit() and "-" in v[:8] for v in flat):
            kind = "date"
        else:
            kind = "list" if listy else "scalar"

        distinct_values = sorted(set(flat)) if kind in {"scalar", "list", "date"} else []
        distinct = len(distinct_values) if distinct_values else None
        enumerable = (
            kind in {"scalar", "list", "date"}
            and distinct is not None
            and distinct <= ENUMERABLE_MAX_DISTINCT
        )
        facet = (
            enumerable
            and kind in {"scalar", "list"}
            and name not in NON_FACET_PROPERTIES
            and distinct is not None
            and 2 <= distinct
            and distinct / max(len(values), 1) <= FACET_MAX_DISTINCT_RATIO
        )
        stats.append(
            PropertyStat(
                name=name,
                kind=kind,
                present=len(values),
                coverage=round(len(values) / total, 4) if total else 0.0,
                distinct=distinct,
                enumerable=enumerable,
                facet=facet,
                values=distinct_values if enumerable else [],
            )
        )
    return stats


def census_nodes(graph: RawGraph) -> list[NodeType]:
    grouped: dict[tuple[str, str], list[rg.Node]] = defaultdict(list)
    for node in graph.nodes.values():
        if graph.is_entity(node):
            grouped[(node.source, node.label)].append(node)

    out: list[NodeType] = []
    for (source, label), members in sorted(grouped.items()):
        out.append(
            NodeType(
                source=source,
                label=label,
                count=len(members),
                unmapped=any(n.unmapped for n in members),
                referenced_only=all(n.placeholder for n in members),
                properties=_property_stats([n.properties for n in members]),
            )
        )
    return out


def census_edges(graph: RawGraph) -> list[EdgeType]:
    grouped: dict[tuple[str, str, str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        subject, obj = graph.nodes.get(edge.subject), graph.nodes.get(edge.object)
        if subject is None or obj is None:
            continue
        key = (edge.source, subject.label, edge.predicate, obj.label, edge.origin)
        grouped[key].append((edge.subject, edge.object))

    out: list[EdgeType] = []
    for (source, subject, predicate, obj, origin), pairs in sorted(grouped.items()):
        uniq = sorted(set(pairs))
        subject_source = {graph.nodes[s].source for s, _ in uniq}
        object_source = {graph.nodes[o].source for _, o in uniq}
        # Cross-source is a property of the *reference*, not of which file it was
        # read from: CAPEC declares an ATT&CK id, so the edge spans stores even
        # though both endpoints were parsed out of the CAPEC XML.
        cross = obj in {"Technique"} and source == "capec"
        out.append(
            EdgeType(
                source=source,
                subject=subject,
                predicate=predicate,
                object=obj,
                count=len(uniq),
                distinct_subjects=len({s for s, _ in uniq}),
                distinct_objects=len({o for _, o in uniq}),
                forward_fanout=_fanout(uniq),
                reverse_fanout=_fanout(uniq, reverse=True),
                origin=f"{origin}/cross-source" if cross else origin,
                cross_source=cross or (subject_source != object_source),
            )
        )
    out.sort(key=lambda e: (-e.count, e.subject, e.predicate, e.object))
    return out


# ---------------------------------------------------------------------------
# COVERAGE — the ONLY architecture-aware section in this file
# ---------------------------------------------------------------------------
#
# Everything above derives from the raw sources and knows nothing about
# Ariadne. This section maps the 16 hand-written author categories from
# `holdout_protocol` onto census triples so we can report how much of the
# census they reach. It reads the census; it never feeds it.

CATEGORY_TRIPLES: dict[str, tuple[str, ...]] = {
    "mitigations": ("Mitigation -[mitigates]-> Technique",),
    "groups": ("Group -[uses]-> Technique",),
    "software": ("Software -[uses]-> Technique",),
    "detection": ("DetectionStrategy -[detects]-> Technique",),
    "tactics": ("Technique -[kill_chain_phase]-> Tactic",),
    "subtechnique": ("Technique -[subtechnique-of]-> Technique",),
    "lookup": (),  # a property read, not an edge
    "mapping": ("AttackPattern -[MAPS_TO[ATTACK]]-> Technique",),
    "weakness": ("AttackPattern -[EXPLOITS_WEAKNESS]-> Weakness",),
    "hierarchy": ("AttackPattern -[ChildOf]-> AttackPattern",),
    "execution": ("AttackPattern -[HAS_EXECUTION_STEP]-> ExecutionStep",),
    "consequence": ("AttackPattern -[HAS_CONSEQUENCE]-> Consequence",),
    "prerequisite": ("AttackPattern -[REQUIRES_SKILL]-> Skill",),
    "pattern-to-mitigation": (
        "AttackPattern -[MAPS_TO[ATTACK]]-> Technique",
        "Mitigation -[mitigates]-> Technique",
    ),
    "reverse-mapping": ("AttackPattern -[MAPS_TO[ATTACK]]-> Technique",),
    "cwe-chain": (
        "AttackPattern -[EXPLOITS_WEAKNESS]-> Weakness",
        "AttackPattern -[MAPS_TO[ATTACK]]-> Technique",
    ),
}

#: The properties any authored category can surface. `lookup` asks for "a plain
#: description of one entity", and the CAPEC sub-element categories surface the
#: step/consequence/skill text. Nothing else in the 16 reads a property at all.
CATEGORY_PROPERTIES: frozenset[str] = frozenset(
    {"description", "Description", "name", "Name", "text"}
)

#: Labels a category can name directly, independent of any edge. Property
#: coverage is restricted to labels a category can actually reach — otherwise
#: `Campaign.description` counts as covered because *some* category reads a
#: description, when no category has ever reached a Campaign.
CATEGORY_ANCHOR_LABELS: frozenset[str] = frozenset({"Technique", "AttackPattern"})


def coverage(edges: list[EdgeType], nodes: list[NodeType] | None = None) -> dict[str, Any]:
    """How much of the census the 16 authored categories can reach."""
    present = {edge.triple for edge in edges}
    reached = {t for triples in CATEGORY_TRIPLES.values() for t in triples}
    hit = sorted(reached & present)
    instances_total = sum(edge.count for edge in edges)
    instances_hit = sum(edge.count for edge in edges if edge.triple in reached)

    reachable = set(CATEGORY_ANCHOR_LABELS)
    for triple in hit:
        subject, _, rest = triple.partition(" -[")
        _, _, obj = rest.partition("]-> ")
        reachable.update({subject, obj})

    props = {(n.label, p.name) for n in (nodes or []) for p in n.properties}
    props_hit = {
        (label, name)
        for label, name in props
        if name in CATEGORY_PROPERTIES and label in reachable
    }
    return {
        "authored_categories": len(CATEGORY_TRIPLES),
        "edge_types_total": len(present),
        "edge_types_reached": len(hit),
        "edge_type_coverage": round(len(hit) / len(present), 4) if present else 0.0,
        "edge_instances_total": instances_total,
        "edge_instances_reached": instances_hit,
        "edge_instance_coverage": (
            round(instances_hit / instances_total, 4) if instances_total else 0.0
        ),
        "labels_reachable": sorted(reachable),
        "properties_total": len(props),
        "properties_reached": len(props_hit),
        "property_coverage": round(len(props_hit) / len(props), 4) if props else 0.0,
        "reached": hit,
        "never_asked": sorted(present - reached),
        "declared_but_absent": sorted(reached - present),
    }


# ---------------------------------------------------------------------------


def _digest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def build_census(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    graph = rg.build(data_dir)
    paths = rg.source_paths(data_dir)
    nodes = census_nodes(graph)
    edges = census_edges(graph)

    askable = [e for e in edges if e.forward_fanout["n"] and e.forward_fanout["p90"] <= ASKABLE_P90]
    reverse_askable = [
        e for e in edges if e.reverse_fanout["n"] and e.reverse_fanout["p90"] <= ASKABLE_P90
    ]
    dangling = graph.dangling()

    return {
        "census_version": CENSUS_VERSION,
        "sources": {
            name: {**graph.stats[name], **_digest(paths[name])} for name in ("attack", "capec")
        },
        "policy": {
            "derivation": "raw files only, via raw_graph; not through utils.kg_builder "
                          "and not from a live store",
            "exclusions": "ATT&CK revoked/deprecated; CAPEC Deprecated/Obsolete; "
                          "dead endpoints pruned",
            "entity_rule": "a referenced-but-undefined node counts toward its label's "
                           "population only when nothing else defines that label",
            "enumerable_max_distinct": ENUMERABLE_MAX_DISTINCT,
            "facet_max_distinct_ratio": FACET_MAX_DISTINCT_RATIO,
            "freetext_mean_chars": FREETEXT_MEAN_CHARS,
            "askable_p90": ASKABLE_P90,
        },
        "totals": {
            "node_types": len(nodes),
            "nodes": sum(n.count for n in nodes),
            "edge_types": len(edges),
            "edge_instances": sum(e.count for e in edges),
            "cross_source_edge_types": sum(1 for e in edges if e.cross_source),
            "enumerable_properties": sum(1 for n in nodes for p in n.properties if p.enumerable),
            "facet_properties": sum(1 for n in nodes for p in n.properties if p.facet),
            "date_properties": sum(1 for n in nodes for p in n.properties if p.kind == "date"),
            "forward_askable_edge_types": len(askable),
            "reverse_askable_edge_types": len(reverse_askable),
            "dangling_cross_source_references": len(dangling),
        },
        "dangling_cross_source_references": sorted(n.id for n in dangling),
        "nodes": [asdict(n) for n in nodes],
        "edges": [asdict(e) | {"triple": e.triple} for e in edges],
        "coverage": coverage(edges, nodes),
    }


def render_markdown(census: dict[str, Any]) -> str:
    cov = census["coverage"]
    tot = census["totals"]
    src = census["sources"]
    lines: list[str] = []
    add = lines.append

    add("# Schema census")
    add("")
    add(
        f"ATT&CK v{src['attack']['version']} + CAPEC v{src['capec']['version']}, "
        "read from the pinned raw snapshot. Regenerate with "
        "`uv run python -m utils.specialists.evalset.schema_census`."
    )
    add("")
    add("## The number this was built to produce")
    add("")
    add(
        f"The banks draw from **{cov['authored_categories']} hand-written question "
        f"categories**. The sources support **{tot['edge_types']} distinct edge types** "
        f"across **{tot['node_types']} node types**."
    )
    add("")
    add(
        f"Those categories reach **{cov['edge_types_reached']} of {cov['edge_types_total']}** "
        f"edge types — **{cov['edge_type_coverage']:.1%}** of the shapes, covering "
        f"**{cov['edge_instance_coverage']:.1%}** of the {cov['edge_instances_total']:,} "
        "edge instances."
    )
    add("")
    add(
        f"On the property side it is narrower still: **{cov['properties_reached']} of "
        f"{cov['properties_total']}** node properties "
        f"(**{cov['property_coverage']:.1%}**), because only the `lookup` category reads "
        "a property at all and it reads the description."
    )
    add("")
    add("| | count |")
    add("|---|---:|")
    for key in (
        "node_types", "nodes", "edge_types", "edge_instances",
        "cross_source_edge_types", "enumerable_properties", "facet_properties",
        "forward_askable_edge_types", "reverse_askable_edge_types",
        "dangling_cross_source_references",
    ):
        add(f"| {key.replace('_', ' ')} | {tot[key]:,} |")
    add("")

    add("## Edge types")
    add("")
    add("`fwd` / `rev` are median and p90 fan-out. *Askable* in a direction means")
    add("p90 answers stay under 50. It is reported, never used to exclude: Q29")
    add("measured judged score against gold width and found no effect.")
    add("")
    add("| triple | n | fwd med/p90 | rev med/p90 | origin | asked? |")
    add("|---|---:|---:|---:|---|---|")
    reached = set(cov["reached"])
    for edge in census["edges"]:
        fwd, rev = edge["forward_fanout"], edge["reverse_fanout"]
        mark = "yes" if edge["triple"] in reached else "**never**"
        add(
            f"| `{edge['triple']}` | {edge['count']:,} | "
            f"{fwd['median']:g}/{fwd['p90']:g} | {rev['median']:g}/{rev['p90']:g} | "
            f"{edge['origin']} | {mark} |"
        )
    add("")

    add("## Never asked")
    add("")
    add(f"{len(cov['never_asked'])} edge types have never carried a question:")
    add("")
    for triple in cov["never_asked"]:
        add(f"- `{triple}`")
    add("")

    add("## Facet properties")
    add("")
    add("Properties whose values are shared across enough nodes to carry a filter —")
    add("the raw material for constrained questions, of which the banks have none.")
    add("Identifiers and bundle metadata are excluded; date properties are listed")
    add("after, because they carry range filters rather than equality filters.")
    add("")
    add("| node type | property | distinct | coverage | values |")
    add("|---|---|---:|---:|---|")
    for node in census["nodes"]:
        for prop in node["properties"]:
            if not prop["facet"]:
                continue
            shown = ", ".join(prop["values"][:6])
            if len(prop["values"]) > 6:
                shown += f", … (+{len(prop['values']) - 6})"
            add(
                f"| {node['label']} | `{prop['name']}` | {prop['distinct']} | "
                f"{prop['coverage']:.0%} | {shown} |"
            )
    add("")

    dates = [
        (n["label"], p["name"])
        for n in census["nodes"]
        for p in n["properties"]
        if p["kind"] == "date"
    ]
    if dates:
        add("Date properties (range filters): " + ", ".join(f"`{l}.{p}`" for l, p in dates))
        add("")

    add("## Dangling cross-source references")
    add("")
    add(
        f"CAPEC declares {tot['dangling_cross_source_references']} ATT&CK technique ids "
        "that the pinned Enterprise bundle has no live object for. They are the "
        "cross-source join's failure surface and must not carry a federated question:"
    )
    add("")
    add("> " + ", ".join(f"`{i}`" for i in census["dangling_cross_source_references"]))
    add("")

    add("## Node types")
    add("")
    add("| source | label | count | referenced only | text properties |")
    add("|---|---|---:|---|---|")
    for node in census["nodes"]:
        text = ", ".join(
            f"`{p['name']}`" for p in node["properties"] if p["kind"] == "text"
        ) or "—"
        ref = "yes" if node["referenced_only"] else "—"
        add(f"| {node['source']} | {node['label']} | {node['count']:,} | {ref} | {text} |")
    add("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    census = build_census(args.data_dir)
    versions = census["sources"]
    stem = f"attack-{versions['attack']['version']}-capec-{versions['capec']['version']}"
    out = args.out_dir / stem
    out.mkdir(parents=True, exist_ok=True)
    (out / "census.json").write_text(json.dumps(census, indent=1, sort_keys=False) + "\n")
    (out / "CENSUS.md").write_text(render_markdown(census))

    cov = census["coverage"]
    print(f"census -> {out}")
    print(
        f"  {census['totals']['edge_types']} edge types, "
        f"{census['totals']['node_types']} node types; "
        f"{cov['edge_types_reached']} edge types reached by the "
        f"{cov['authored_categories']} authored categories "
        f"({cov['edge_type_coverage']:.1%})"
    )


if __name__ == "__main__":
    main()
