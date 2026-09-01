#!/usr/bin/env python3
r"""Enumerate every question shape the pinned raw snapshot actually supports.

The census answers one question that nothing else in the repository answers:
**how much of the graph have we ever asked about?**

`holdout_protocol.ATTACK_CATEGORIES` and friends are a hand-written list of 16
question shapes. They were written from memory, not derived from the data, and
every bank we have ever built draws from them. This module walks the raw ATT&CK
STIX bundle and the raw CAPEC XML and reports the shapes the *sources* support:
node types, their properties (with the cardinality that decides whether a
property can carry a filter), and every typed edge with its fan-out in both
directions.

Three properties are deliberate and load-bearing:

* **It parses raw files, not the loaded graph and not `utils.kg_builder`.**
  Same discipline as `gold_bank`: an independent derivation. A census taken
  through the ingest pipeline could only ever report what the pipeline chose to
  keep, which is the opposite of what it is for.
* **It is architecture-blind.** Nothing above `COVERAGE` knows that Ariadne has
  templates, primitives, or a composer. The one architecture-aware section is
  the coverage layer at the bottom, isolated on purpose and clearly marked, and
  it only *reads* the census — it cannot change what the census finds.
* **It mirrors the load-time exclusion policy** (revoked/deprecated ATT&CK
  objects, Deprecated/Obsolete CAPEC patterns) so the shapes it reports are
  shapes a question could actually be answered from. Exclusions are counted and
  reported rather than silently applied.

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
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
OUT_DIR = REPO_ROOT / "docs" / "evaluation" / "schema-census"

CAPEC_NS = {"c": "http://capec.mitre.org/capec-3"}

CENSUS_VERSION = 1

# STIX object type -> the label the census reports it under. Unlisted types are
# NOT dropped: they are reported under their raw STIX type and flagged
# `unmapped`, because a type nobody mapped is exactly the kind of thing this
# census exists to surface.
STIX_TYPE_TO_LABEL: dict[str, str] = {
    "x-mitre-tactic": "Tactic",
    "attack-pattern": "Technique",
    "intrusion-set": "Group",
    "malware": "Software",
    "tool": "Software",
    "course-of-action": "Mitigation",
    "campaign": "Campaign",
    "x-mitre-data-component": "DataComponent",
    "x-mitre-data-source": "DataSource",
    "x-mitre-detection-strategy": "DetectionStrategy",
    "x-mitre-analytic": "Analytic",
    "x-mitre-matrix": "Matrix",
}

#: STIX bookkeeping that describes the *bundle*, never the security domain.
#: These are not question material and are excluded from the property census.
STIX_PLUMBING = frozenset({
    "id", "type", "spec_version", "created", "modified",
    "created_by_ref", "object_marking_refs", "x_mitre_modified_by_ref",
    "x_mitre_attack_spec_version", "external_references",
    "revoked", "x_mitre_deprecated",
})

#: Ref-bearing properties that carry a real domain edge, and the label they
#: point at. `created_by_ref` / `object_marking_refs` are plumbing (above).
STIX_EMBEDDED_REFS: dict[tuple[str, str], str] = {
    ("x-mitre-detection-strategy", "x_mitre_analytic_refs"): "Analytic",
    ("x-mitre-matrix", "tactic_refs"): "Tactic",
}

#: Objects excluded from the census because the loaded graph excludes them.
#: Mirrors `gold_bank`'s exclude-at-load policy (policy contract, not code).
CAPEC_RETIRED_STATUSES = frozenset({"Deprecated", "Obsolete"})

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

#: ISO-8601-ish leading value; date properties carry range filters, not
#: equality filters, so they are reported apart from the facets.
_DATEISH = ("19", "20")


# ---------------------------------------------------------------------------
# record types
# ---------------------------------------------------------------------------


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
    """Distribution of out-degree (or in-degree) over the nodes that have one.

    Nodes with zero edges are excluded on purpose: the question "how big is the
    answer when there *is* one" is the one that decides whether a shape is
    askable.
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


def _property_stats(instances: list[dict[str, Any]], skip: frozenset[str]) -> list[PropertyStat]:
    total = len(instances)
    seen: dict[str, list[Any]] = defaultdict(list)
    for inst in instances:
        for key, value in inst.items():
            if key in skip or value is None or value == [] or value == "":
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
            elif isinstance(value, (dict,)):
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

        distinct_values = sorted(set(flat)) if kind in {"scalar", "list"} else []
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
            and distinct >= 2
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


def _edges_from_pairs(
    source: str,
    grouped: dict[tuple[str, str, str], list[tuple[str, str]]],
    origin: str,
    *,
    source_of: dict[str, str] | None = None,
) -> list[EdgeType]:
    edges: list[EdgeType] = []
    for (subj, pred, obj), pairs in sorted(grouped.items()):
        uniq = sorted(set(pairs))
        cross = False
        if source_of is not None:
            cross = source_of.get(subj, source) != source_of.get(obj, source)
        edges.append(
            EdgeType(
                source=source,
                subject=subj,
                predicate=pred,
                object=obj,
                count=len(uniq),
                distinct_subjects=len({s for s, _ in uniq}),
                distinct_objects=len({o for _, o in uniq}),
                forward_fanout=_fanout(uniq),
                reverse_fanout=_fanout(uniq, reverse=True),
                origin=origin,
                cross_source=cross,
            )
        )
    return edges


# ---------------------------------------------------------------------------
# ATT&CK
# ---------------------------------------------------------------------------


def _attack_external_id(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") in {"mitre-attack", "mitre-mobile-attack", "mitre-ics-attack"}:
            return ref.get("external_id")
    return None


def _attack_alive(obj: dict[str, Any]) -> bool:
    return not (obj.get("revoked") or obj.get("x_mitre_deprecated"))


def census_attack(bundle: dict[str, Any]) -> tuple[list[NodeType], list[EdgeType], dict[str, Any]]:
    """Node types, typed edges and exclusion counts, from the STIX bundle alone."""
    objects = bundle["objects"]
    excluded = {"objects": 0, "relationships_dead_endpoint": 0, "relationships_self": 0}

    alive: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if obj["type"] in {"relationship", "identity", "marking-definition", "x-mitre-collection"}:
            continue
        if not _attack_alive(obj):
            excluded["objects"] += 1
            continue
        alive[obj["id"]] = obj

    label_of = {
        oid: STIX_TYPE_TO_LABEL.get(obj["type"], obj["type"]) for oid, obj in alive.items()
    }

    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for obj in alive.values():
        by_label[STIX_TYPE_TO_LABEL.get(obj["type"], obj["type"])].append(obj)

    nodes = [
        NodeType(
            source="attack",
            label=label,
            count=len(instances),
            unmapped=label not in STIX_TYPE_TO_LABEL.values(),
            properties=_property_stats(instances, STIX_PLUMBING),
        )
        for label, instances in sorted(by_label.items())
    ]

    # --- edges carried by `relationship` objects -----------------------------
    grouped: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for obj in objects:
        if obj["type"] != "relationship":
            continue
        if not _attack_alive(obj):
            excluded["objects"] += 1
            continue
        src, dst = obj.get("source_ref"), obj.get("target_ref")
        if src not in alive or dst not in alive:
            excluded["relationships_dead_endpoint"] += 1
            continue
        grouped[(label_of[src], obj["relationship_type"], label_of[dst])].append((src, dst))
    edges = _edges_from_pairs("attack", grouped, "relationship-object")

    # --- edges carried by ref properties on the object itself ----------------
    embedded: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for obj in alive.values():
        for (otype, prop), target_label in STIX_EMBEDDED_REFS.items():
            if obj["type"] != otype:
                continue
            for ref in obj.get(prop, []):
                if ref in alive:
                    embedded[(label_of[obj["id"]], prop, target_label)].append((obj["id"], ref))
    edges += _edges_from_pairs("attack", embedded, "embedded-ref")

    # --- kill_chain_phases resolves to Tactic by shortname --------------------
    shortname_to_tactic = {
        obj["x_mitre_shortname"]: obj["id"]
        for obj in alive.values()
        if obj["type"] == "x-mitre-tactic" and obj.get("x_mitre_shortname")
    }
    phases: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    unresolved_phases = 0
    for obj in alive.values():
        for phase in obj.get("kill_chain_phases", []):
            tactic = shortname_to_tactic.get(phase.get("phase_name"))
            if tactic is None:
                unresolved_phases += 1
                continue
            phases[(label_of[obj["id"]], "kill_chain_phase", "Tactic")].append((obj["id"], tactic))
    edges += _edges_from_pairs("attack", phases, "embedded-ref")
    excluded["kill_chain_phases_unresolved"] = unresolved_phases

    # --- refs nested one level inside a list of dicts -------------------------
    nested: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for obj in alive.values():
        for entry in obj.get("x_mitre_log_source_references", []) or []:
            ref = entry.get("x_mitre_data_component_ref")
            if ref in alive:
                nested[(label_of[obj["id"]], "log_source", "DataComponent")].append((obj["id"], ref))
    edges += _edges_from_pairs("attack", nested, "nested-ref")

    identified = sum(1 for obj in alive.values() if _attack_external_id(obj))
    stats = {
        "objects_in_bundle": len(objects),
        "nodes_after_exclusions": len(alive),
        "nodes_with_external_id": identified,
        "excluded": excluded,
    }
    return nodes, edges, stats


# ---------------------------------------------------------------------------
# CAPEC
# ---------------------------------------------------------------------------

#: CAPEC child element -> (predicate, object label). Sub-elements become nodes
#: because that is what they are in the loaded graph and what a question about
#: "the execution steps of CAPEC-66" has to return.
CAPEC_SUBELEMENTS: dict[str, tuple[str, str, str]] = {
    "Execution_Flow": ("Attack_Step", "HAS_EXECUTION_STEP", "ExecutionStep"),
    "Consequences": ("Consequence", "HAS_CONSEQUENCE", "Consequence"),
    "Skills_Required": ("Skill", "REQUIRES_SKILL", "Skill"),
    "Mitigations": ("Mitigation", "HAS_MITIGATION", "CapecMitigation"),
    "Prerequisites": ("Prerequisite", "HAS_PREREQUISITE", "Prerequisite"),
    "Indicators": ("Indicator", "HAS_INDICATOR", "Indicator"),
    "Example_Instances": ("Example", "HAS_EXAMPLE", "Example"),
    "Resources_Required": ("Resource", "REQUIRES_RESOURCE", "Resource"),
    "Alternate_Terms": ("Alternate_Term", "HAS_ALTERNATE_TERM", "AlternateTerm"),
}


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def census_capec(root: ET.Element) -> tuple[list[NodeType], list[EdgeType], dict[str, Any]]:
    """Node types, typed edges and exclusion counts, from the CAPEC XML alone."""
    patterns_el = root.find("c:Attack_Patterns", CAPEC_NS)
    all_patterns = patterns_el.findall("c:Attack_Pattern", CAPEC_NS) if patterns_el is not None else []

    live: dict[str, ET.Element] = {}
    excluded = {"patterns_retired": 0, "edges_dead_endpoint": 0}
    for pattern in all_patterns:
        if pattern.get("Status") in CAPEC_RETIRED_STATUSES:
            excluded["patterns_retired"] += 1
            continue
        live[f"CAPEC-{pattern.get('ID')}"] = pattern

    # --- node property census ------------------------------------------------
    pattern_props: list[dict[str, Any]] = []
    for cid, pattern in live.items():
        record: dict[str, Any] = {
            "Abstraction": pattern.get("Abstraction"),
            "Status": pattern.get("Status"),
            "Name": pattern.get("Name"),
            "Typical_Severity": _text(pattern.find("c:Typical_Severity", CAPEC_NS)) or None,
            "Likelihood_Of_Attack": _text(pattern.find("c:Likelihood_Of_Attack", CAPEC_NS)) or None,
            "Description": _text(pattern.find("c:Description", CAPEC_NS)) or None,
            "Extended_Description": _text(pattern.find("c:Extended_Description", CAPEC_NS)) or None,
        }
        pattern_props.append({k: v for k, v in record.items() if v})

    nodes = [
        NodeType(
            source="capec",
            label="AttackPattern",
            count=len(live),
            properties=_property_stats(pattern_props, frozenset()),
        )
    ]

    grouped: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    sub_counts: dict[str, int] = defaultdict(int)

    for cid, pattern in live.items():
        # pattern -> pattern, one predicate per declared nature
        rap = pattern.find("c:Related_Attack_Patterns", CAPEC_NS)
        for rel in (rap.findall("c:Related_Attack_Pattern", CAPEC_NS) if rap is not None else []):
            target = f"CAPEC-{rel.get('CAPEC_ID')}"
            if target not in live:
                excluded["edges_dead_endpoint"] += 1
                continue
            grouped[("AttackPattern", rel.get("Nature") or "Related", "AttackPattern")].append(
                (cid, target)
            )

        # pattern -> CWE
        rw = pattern.find("c:Related_Weaknesses", CAPEC_NS)
        for weakness in (rw.findall("c:Related_Weakness", CAPEC_NS) if rw is not None else []):
            grouped[("AttackPattern", "EXPLOITS_WEAKNESS", "Weakness")].append(
                (cid, f"CWE-{weakness.get('CWE_ID')}")
            )

        # pattern -> taxonomy entry, one predicate per taxonomy
        tmaps = pattern.find("c:Taxonomy_Mappings", CAPEC_NS)
        for mapping in (tmaps.findall("c:Taxonomy_Mapping", CAPEC_NS) if tmaps is not None else []):
            taxonomy = mapping.get("Taxonomy_Name") or "UNKNOWN"
            # OWASP Attacks entries carry only `Entry_Name`; keying on
            # `Entry_ID` alone silently drops the whole taxonomy.
            entry = _text(mapping.find("c:Entry_ID", CAPEC_NS)) or _text(
                mapping.find("c:Entry_Name", CAPEC_NS)
            )
            if not entry:
                continue
            label = "Technique" if taxonomy == "ATTACK" else f"TaxonomyEntry:{taxonomy}"
            grouped[("AttackPattern", f"MAPS_TO[{taxonomy}]", label)].append(
                (cid, f"T{entry}" if taxonomy == "ATTACK" else f"{taxonomy}:{entry}")
            )

        # pattern -> its own sub-elements
        for parent_tag, (child_tag, predicate, label) in CAPEC_SUBELEMENTS.items():
            parent = pattern.find(f"c:{parent_tag}", CAPEC_NS)
            if parent is None:
                continue
            for index, _child in enumerate(parent.findall(f"c:{child_tag}", CAPEC_NS), start=1):
                grouped[("AttackPattern", predicate, label)].append((cid, f"{cid}#{predicate}-{index}"))
                sub_counts[label] += 1

    # --- Categories and Views: real containers, never once asked about --------
    for container, child_label in (("Categories", "Category"), ("Views", "View")):
        holder = root.find(f"c:{container}", CAPEC_NS)
        if holder is None:
            continue
        members: list[dict[str, Any]] = []
        singular = child_label
        for element in holder.findall(f"c:{singular}", CAPEC_NS):
            members.append(
                {k: v for k, v in element.attrib.items() if k in {"Name", "Status", "Type"}}
            )
            holder_id = f"{singular.upper()}-{element.get('ID')}"
            rels = element.find("c:Relationships", CAPEC_NS)
            if rels is None:
                rels = element.find("c:Members", CAPEC_NS)
            for member in list(rels) if rels is not None else []:
                target = member.get("CAPEC_ID")
                if target is None:
                    continue
                grouped[(singular, "HAS_MEMBER", "AttackPattern")].append(
                    (holder_id, f"CAPEC-{target}")
                )
        nodes.append(
            NodeType(
                source="capec",
                label=singular,
                count=len(members),
                properties=_property_stats(members, frozenset()),
            )
        )

    edges = _edges_from_pairs("capec", grouped, "xml-element")
    for edge in edges:
        if edge.object == "Technique":
            edge.cross_source = True
            edge.origin = "xml-element/cross-source"

    for label, count in sorted(sub_counts.items()):
        nodes.append(NodeType(source="capec", label=label, count=count))
    nodes.append(
        NodeType(
            source="capec",
            label="Weakness",
            count=len({o for e in grouped.get(("AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"), []) for o in [e[1]]}),
        )
    )

    stats = {
        "patterns_in_file": len(all_patterns),
        "patterns_after_exclusions": len(live),
        "excluded": excluded,
    }
    return nodes, edges, stats


# ---------------------------------------------------------------------------
# COVERAGE — the ONLY architecture-aware section in this file
# ---------------------------------------------------------------------------
#
# Everything above derives from the raw sources and knows nothing about
# Ariadne. This section maps the 16 hand-written author categories from
# `holdout_protocol` onto census triples so we can report how much of the
# census they reach. It reads the census; it never feeds it.

#: category name -> the census triples that category can produce a question for.
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
#: description of one entity"; nothing else in the 16 reads a property at all.
CATEGORY_PROPERTIES: frozenset[str] = frozenset({"description", "Description", "name", "Name"})


def coverage(edges: list[EdgeType], nodes: list[NodeType] | None = None) -> dict[str, Any]:
    """How much of the census the 16 authored categories can reach."""
    present = {edge.triple for edge in edges}
    reached = {t for triples in CATEGORY_TRIPLES.values() for t in triples}
    unknown = sorted(reached - present)
    hit = sorted(reached & present)
    missed = sorted(present - reached)
    instances_total = sum(edge.count for edge in edges)
    instances_hit = sum(edge.count for edge in edges if edge.triple in reached)

    props = {(n.label, p.name) for n in (nodes or []) for p in n.properties}
    props_hit = {pair for pair in props if pair[1] in CATEGORY_PROPERTIES}
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
        "properties_total": len(props),
        "properties_reached": len(props_hit),
        "property_coverage": round(len(props_hit) / len(props), 4) if props else 0.0,
        "reached": hit,
        "never_asked": missed,
        "declared_but_absent": unknown,
    }


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------


def _digest(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size_bytes": len(data),
    }


def build_census(data_dir: Path = DATA_DIR) -> dict[str, Any]:
    versions = json.loads((data_dir / "versions.json").read_text())
    attack_version = versions["attack_version"]
    capec_version = versions["capec_version"]
    attack_path = data_dir / "raw" / "attack" / f"v{attack_version}" / "enterprise-attack.json"
    capec_path = data_dir / "raw" / "capec" / f"v{capec_version}" / "capec_latest.xml"

    attack_nodes, attack_edges, attack_stats = census_attack(json.loads(attack_path.read_text()))
    capec_nodes, capec_edges, capec_stats = census_capec(ET.parse(capec_path).getroot())

    nodes = attack_nodes + capec_nodes
    edges = attack_edges + capec_edges
    edges.sort(key=lambda e: (-e.count, e.subject, e.predicate, e.object))

    askable = [e for e in edges if e.forward_fanout["median"] and e.forward_fanout["p90"] <= 50]
    reverse_askable = [e for e in edges if e.reverse_fanout["n"] and e.reverse_fanout["p90"] <= 50]

    return {
        "census_version": CENSUS_VERSION,
        "sources": {
            "attack": {"version": attack_version, **_digest(attack_path), **attack_stats},
            "capec": {"version": capec_version, **_digest(capec_path), **capec_stats},
        },
        "policy": {
            "derivation": "raw files only; not through utils.kg_builder and not from a live store",
            "exclusions": "ATT&CK revoked/deprecated; CAPEC Deprecated/Obsolete; dead endpoints pruned",
            "enumerable_max_distinct": ENUMERABLE_MAX_DISTINCT,
            "freetext_mean_chars": FREETEXT_MEAN_CHARS,
        },
        "totals": {
            "node_types": len(nodes),
            "nodes": sum(n.count for n in nodes),
            "edge_types": len(edges),
            "edge_instances": sum(e.count for e in edges),
            "cross_source_edge_types": sum(1 for e in edges if e.cross_source),
            "enumerable_properties": sum(
                1 for n in nodes for p in n.properties if p.enumerable
            ),
            "facet_properties": sum(1 for n in nodes for p in n.properties if p.facet),
            "date_properties": sum(
                1 for n in nodes for p in n.properties if p.kind == "date"
            ),
            "forward_askable_edge_types": len(askable),
            "reverse_askable_edge_types": len(reverse_askable),
        },
        "nodes": [asdict(n) for n in nodes],
        "edges": [asdict(e) | {"triple": e.triple} for e in edges],
        "coverage": coverage(edges, nodes),
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


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
        f"**{cov['edge_instance_coverage']:.1%}** of the {cov['edge_instances_total']:,} edge instances."
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
    ):
        add(f"| {key.replace('_', ' ')} | {tot[key]:,} |")
    add("")

    add("## Edge types")
    add("")
    add("`fwd` / `rev` are median and p90 fan-out. An edge is *askable* in a")
    add("direction when p90 answers stay under 50 — larger than that and the")
    add("question has no reasonable answer to grade.")
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

    add("## Node types")
    add("")
    add("| source | label | count | text properties |")
    add("|---|---|---:|---|")
    for node in census["nodes"]:
        text = ", ".join(
            f"`{p['name']}`" for p in node["properties"] if p["kind"] == "text"
        ) or "—"
        add(f"| {node['source']} | {node['label']} | {node['count']:,} | {text} |")
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
