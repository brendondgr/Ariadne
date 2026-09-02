r"""An in-memory graph built from the pinned raw files, and nothing else.

`schema_census` counts shapes; `composition` needs the instances behind them.
Both need the same parse, and neither may take it through `utils.kg_builder` or
a live store — the whole point of this line of work is that the question set is
derived independently of the system it grades.

So the parse lives here, once, and both consume it:

    raw_graph.build()  ->  RawGraph      (instances)
      |                        |
      v                        v
    schema_census            composition
      (statistics)             (question specs + gold)

Everything in this module is architecture-blind. It knows STIX, it knows the
CAPEC schema, and it knows the load-time exclusion policy. It does not know that
Ariadne exists.

Two design points worth stating because they are easy to get wrong later:

* **Sub-technique is not a separate label.** STIX gives both `attack-pattern`,
  and the graph distinguishes them by a property, so this module does too. A
  census that split them would disagree with `gold_bank`'s totals for a reason
  that has nothing to do with the data.
* **CAPEC sub-elements get synthesised ids.** Execution steps, consequences and
  skills carry no identifier in the XML. Their ids here are derived exactly the
  way the loaded graph derives them, so gold computed from this module lines up
  with what a specialist would return. They are instances, not entities: 815
  execution steps means 815 step *rows* across 239 patterns.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
CAPEC_NS = {"c": "http://capec.mitre.org/capec-3"}

#: STIX object type -> census label. Unlisted types keep their raw STIX type and
#: are flagged `unmapped` rather than dropped: a type nobody mapped is exactly
#: what this line of work exists to surface.
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

#: STIX types that describe the bundle rather than the domain.
STIX_NON_DOMAIN_TYPES = frozenset(
    {"relationship", "identity", "marking-definition", "x-mitre-collection"}
)

#: STIX bookkeeping — never question material, excluded from the property census.
STIX_PLUMBING = frozenset({
    "id", "type", "spec_version", "created", "modified",
    "created_by_ref", "object_marking_refs", "x_mitre_modified_by_ref",
    "x_mitre_attack_spec_version", "external_references",
    "revoked", "x_mitre_deprecated",
})

#: Ref-bearing properties carrying a real domain edge, and the label they hit.
STIX_EMBEDDED_REFS: dict[tuple[str, str], str] = {
    ("x-mitre-detection-strategy", "x_mitre_analytic_refs"): "Analytic",
    ("x-mitre-matrix", "tactic_refs"): "Tactic",
}

CAPEC_RETIRED_STATUSES = frozenset({"Deprecated", "Obsolete"})

#: CAPEC parent element -> (child element, predicate, label).
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

_ATTACK_ID_SOURCES = frozenset({"mitre-attack", "mitre-mobile-attack", "mitre-ics-attack"})


@dataclass(frozen=True)
class Node:
    """One entity. `key` is what a question can name it by, when it has one.

    `placeholder` marks a node that exists only because something referenced it.
    CAPEC declares `Entry_ID 1055` under the ATTACK taxonomy, so `T1055` becomes
    a node here — but the real T1055 is a STIX object in the other source, and
    counting both would double the Technique population and break agreement with
    every independent derivation. `resolves_to` carries the real node's id when
    one exists, so a consumer can count populations correctly and still traverse
    the reference. When it does not resolve (CWE-89, WASC entries — those
    catalogues are not loaded), the placeholder *is* the entity.
    """

    id: str
    source: str
    label: str
    name: str | None = None
    key: str | None = None  # T1055, CAPEC-66, CWE-89 — None for derived nodes
    properties: dict[str, Any] = field(default_factory=dict)
    unmapped: bool = False
    placeholder: bool = False
    resolves_to: str | None = None


@dataclass(frozen=True)
class Edge:
    subject: str
    predicate: str
    object: str
    source: str
    origin: str  # relationship-object | embedded-ref | nested-ref | xml-element


@dataclass
class RawGraph:
    nodes: dict[str, Node]
    edges: list[Edge]
    stats: dict[str, Any] = field(default_factory=dict)

    _out: dict[tuple[str, str], list[str]] = field(default_factory=dict, repr=False)
    _in: dict[tuple[str, str], list[str]] = field(default_factory=dict, repr=False)
    _defined_labels: frozenset[str] = field(default_factory=frozenset, repr=False)
    _coreferent: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._defined_labels = frozenset(
            n.label for n in self.nodes.values() if not n.placeholder
        )
        coreferent: dict[str, list[str]] = defaultdict(list)
        for node in self.nodes.values():
            if node.resolves_to:
                coreferent[node.resolves_to].append(node.id)
        self._coreferent = {k: sorted(v) for k, v in coreferent.items()}
        out: dict[tuple[str, str], list[str]] = defaultdict(list)
        into: dict[tuple[str, str], list[str]] = defaultdict(list)
        for edge in self.edges:
            out[(edge.subject, edge.predicate)].append(edge.object)
            into[(edge.object, edge.predicate)].append(edge.subject)
        self._out = {k: sorted(set(v)) for k, v in out.items()}
        self._in = {k: sorted(set(v)) for k, v in into.items()}

    # --- traversal ---------------------------------------------------------

    def out(self, node_id: str, predicate: str) -> list[str]:
        return self._out.get((node_id, predicate), [])

    def into(self, node_id: str, predicate: str) -> list[str]:
        return self._in.get((node_id, predicate), [])

    def step(self, node_id: str, predicate: str, *, reverse: bool = False) -> list[str]:
        return self.into(node_id, predicate) if reverse else self.out(node_id, predicate)

    def label(self, node_id: str) -> str | None:
        node = self.nodes.get(node_id)
        return node.label if node else None

    def is_entity(self, node: Node) -> bool:
        """Whether this node counts toward its label's population.

        A referenced-but-not-defined node counts only when nothing else in the
        graph defines that label. `CWE-89` counts, because the CWE catalogue is
        not loaded and the reference is the only record of it. `T1055` declared
        by CAPEC does not, because ATT&CK defines Techniques — and neither does
        a CAPEC-declared technique id that ATT&CK has no object for, which is
        not a Technique at all but a dangling reference.
        """
        return not (node.placeholder and node.label in self._defined_labels)

    def by_label(self, label: str, *, entities_only: bool = True) -> list[Node]:
        """Nodes of a label; by default only those that count as entities."""
        return [
            n
            for n in self.nodes.values()
            if n.label == label and (not entities_only or self.is_entity(n))
        ]

    def is_dangling(self, node_id: str) -> bool:
        """A referenced id whose defining source has no live object for it."""
        node = self.nodes.get(node_id)
        return bool(
            node
            and node.placeholder
            and node.label in self._defined_labels
            and not node.resolves_to
        )

    def dangling(self) -> list[Node]:
        """Referenced ids that the defining source has no object for."""
        return [
            n
            for n in self.nodes.values()
            if n.placeholder and n.label in self._defined_labels and not n.resolves_to
        ]

    def resolve(self, node_id: str) -> str:
        """A placeholder's real node id, or the id itself."""
        node = self.nodes.get(node_id)
        return node.resolves_to if node and node.resolves_to else node_id

    def aliases(self, node_id: str) -> list[str]:
        """Every id that denotes the same entity — the federation join, explicit.

        `T1055` reached through CAPEC's taxonomy mapping and
        `attack-pattern--<uuid>` reached through STIX are the same technique, and
        each carries different edges: the placeholder holds the inbound mapping,
        the STIX object holds everything else. A path that crosses stores has to
        traverse both, so this is where the join happens — deliberately in the
        gold computer, because the gold *is* the joined answer and the system
        under test has to reproduce it.
        """
        found = {node_id}
        node = self.nodes.get(node_id)
        if node and node.resolves_to:
            found.add(node.resolves_to)
        found.update(self._coreferent.get(node_id, ()))
        return sorted(found)

    def triples(self) -> Iterator[tuple[str, str, str, str, str]]:
        """(subject label, predicate, object label, source, origin) per edge."""
        for edge in self.edges:
            subject = self.nodes.get(edge.subject)
            obj = self.nodes.get(edge.object)
            if subject and obj:
                yield subject.label, edge.predicate, obj.label, edge.source, edge.origin


# ---------------------------------------------------------------------------
# ATT&CK
# ---------------------------------------------------------------------------


def _attack_key(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") in _ATTACK_ID_SOURCES:
            return ref.get("external_id")
    return None


def _alive(obj: dict[str, Any]) -> bool:
    return not (obj.get("revoked") or obj.get("x_mitre_deprecated"))


def _parse_attack(bundle: dict[str, Any]) -> tuple[dict[str, Node], list[Edge], dict[str, Any]]:
    objects = bundle["objects"]
    excluded = {"objects": 0, "relationships_dead_endpoint": 0}

    raw: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if obj["type"] in STIX_NON_DOMAIN_TYPES:
            continue
        if not _alive(obj):
            excluded["objects"] += 1
            continue
        raw[obj["id"]] = obj

    nodes: dict[str, Node] = {}
    for oid, obj in raw.items():
        label = STIX_TYPE_TO_LABEL.get(obj["type"], obj["type"])
        nodes[oid] = Node(
            id=oid,
            source="attack",
            label=label,
            name=obj.get("name"),
            key=_attack_key(obj),
            properties={k: v for k, v in obj.items() if k not in STIX_PLUMBING},
            unmapped=obj["type"] not in STIX_TYPE_TO_LABEL,
        )

    edges: list[Edge] = []

    for obj in objects:
        if obj["type"] != "relationship":
            continue
        if not _alive(obj):
            excluded["objects"] += 1
            continue
        src, dst = obj.get("source_ref"), obj.get("target_ref")
        if src not in raw or dst not in raw:
            excluded["relationships_dead_endpoint"] += 1
            continue
        edges.append(Edge(src, obj["relationship_type"], dst, "attack", "relationship-object"))

    for oid, obj in raw.items():
        for (otype, prop), _label in STIX_EMBEDDED_REFS.items():
            if obj["type"] != otype:
                continue
            for ref in obj.get(prop, []):
                if ref in raw:
                    edges.append(Edge(oid, prop, ref, "attack", "embedded-ref"))

    shortname_to_tactic = {
        obj["x_mitre_shortname"]: oid
        for oid, obj in raw.items()
        if obj["type"] == "x-mitre-tactic" and obj.get("x_mitre_shortname")
    }
    unresolved = 0
    for oid, obj in raw.items():
        for phase in obj.get("kill_chain_phases", []):
            tactic = shortname_to_tactic.get(phase.get("phase_name"))
            if tactic is None:
                unresolved += 1
                continue
            edges.append(Edge(oid, "kill_chain_phase", tactic, "attack", "embedded-ref"))
    excluded["kill_chain_phases_unresolved"] = unresolved

    for oid, obj in raw.items():
        for entry in obj.get("x_mitre_log_source_references", []) or []:
            ref = entry.get("x_mitre_data_component_ref")
            if ref in raw:
                edges.append(Edge(oid, "log_source", ref, "attack", "nested-ref"))

    stats = {
        "objects_in_bundle": len(objects),
        "nodes_after_exclusions": len(nodes),
        "nodes_with_external_id": sum(1 for n in nodes.values() if n.key),
        "excluded": excluded,
    }
    return nodes, edges, stats


# ---------------------------------------------------------------------------
# CAPEC
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _slug(value: str) -> str:
    return _SLUG_RE.sub("_", value.strip())


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def _parse_capec(root: ET.Element) -> tuple[dict[str, Node], list[Edge], dict[str, Any]]:
    holder = root.find("c:Attack_Patterns", CAPEC_NS)
    all_patterns = holder.findall("c:Attack_Pattern", CAPEC_NS) if holder is not None else []

    excluded = {"patterns_retired": 0, "edges_dead_endpoint": 0}
    live: dict[str, ET.Element] = {}
    for pattern in all_patterns:
        if pattern.get("Status") in CAPEC_RETIRED_STATUSES:
            excluded["patterns_retired"] += 1
            continue
        live[f"CAPEC-{pattern.get('ID')}"] = pattern

    nodes: dict[str, Node] = {}
    edges: list[Edge] = []

    for cid, pattern in live.items():
        properties = {
            "Abstraction": pattern.get("Abstraction"),
            "Status": pattern.get("Status"),
            "Name": pattern.get("Name"),
            "Typical_Severity": _text(pattern.find("c:Typical_Severity", CAPEC_NS)) or None,
            "Likelihood_Of_Attack": _text(pattern.find("c:Likelihood_Of_Attack", CAPEC_NS)) or None,
            "Description": _text(pattern.find("c:Description", CAPEC_NS)) or None,
            "Extended_Description": _text(pattern.find("c:Extended_Description", CAPEC_NS)) or None,
        }
        nodes[cid] = Node(
            id=cid,
            source="capec",
            label="AttackPattern",
            name=pattern.get("Name"),
            key=cid,
            properties={k: v for k, v in properties.items() if v},
        )

    for cid, pattern in live.items():
        rap = pattern.find("c:Related_Attack_Patterns", CAPEC_NS)
        for rel in (rap.findall("c:Related_Attack_Pattern", CAPEC_NS) if rap is not None else []):
            target = f"CAPEC-{rel.get('CAPEC_ID')}"
            if target not in live:
                excluded["edges_dead_endpoint"] += 1
                continue
            edges.append(Edge(cid, rel.get("Nature") or "Related", target, "capec", "xml-element"))

        rw = pattern.find("c:Related_Weaknesses", CAPEC_NS)
        for weakness in (rw.findall("c:Related_Weakness", CAPEC_NS) if rw is not None else []):
            cwe = f"CWE-{weakness.get('CWE_ID')}"
            nodes.setdefault(
                cwe,
                Node(id=cwe, source="capec", label="Weakness", key=cwe, placeholder=True),
            )
            edges.append(Edge(cid, "EXPLOITS_WEAKNESS", cwe, "capec", "xml-element"))

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
            if taxonomy == "ATTACK":
                target, label = f"T{entry}", "Technique"
            else:
                target, label = f"{taxonomy}:{entry}", f"TaxonomyEntry:{taxonomy}"
            nodes.setdefault(
                target,
                Node(id=target, source="capec", label=label, key=target, placeholder=True),
            )
            edges.append(Edge(cid, f"MAPS_TO[{taxonomy}]", target, "capec", "xml-element"))

        for parent_tag, (child_tag, predicate, label) in CAPEC_SUBELEMENTS.items():
            parent = pattern.find(f"c:{parent_tag}", CAPEC_NS)
            if parent is None:
                continue
            for index, child in enumerate(parent.findall(f"c:{child_tag}", CAPEC_NS), start=1):
                child_id = f"{cid}#{_slug(predicate)}-{index}"
                nodes[child_id] = Node(
                    id=child_id,
                    source="capec",
                    label=label,
                    name=_text(child)[:160] or None,
                    properties={"text": _text(child)} if _text(child) else {},
                )
                edges.append(Edge(cid, predicate, child_id, "capec", "xml-element"))

    # Categories, views and attack patterns are allocated from one CAPEC number
    # space, so `CAPEC-118` names a category unambiguously and is how CAPEC's
    # own site addresses it. Inventing `CATEGORY-118` instead gave the renderer
    # an identifier no question could plausibly contain, and 30 of 42 rejections
    # in the first render pilot were the model sensibly refusing to use it.
    for container, singular in (("Categories", "Category"), ("Views", "View")):
        holder = root.find(f"c:{container}", CAPEC_NS)
        if holder is None:
            continue
        for element in holder.findall(f"c:{singular}", CAPEC_NS):
            # The exclusion policy applies here too. It was written for patterns
            # and quietly not applied to categories, so the census counted 78
            # where the load holds 21 — 57 of them Deprecated. The graph/census
            # reconciliation is what surfaced it.
            if element.get("Status") in CAPEC_RETIRED_STATUSES:
                excluded[f"{singular.lower()}s_retired"] = (
                    excluded.get(f"{singular.lower()}s_retired", 0) + 1
                )
                continue
            holder_id = f"CAPEC-{element.get('ID')}"
            if holder_id in nodes:
                raise ValueError(
                    f"{singular} {holder_id} collides with an existing node — the CAPEC "
                    "number space is no longer shared, and ids must be re-scoped"
                )
            nodes[holder_id] = Node(
                id=holder_id,
                source="capec",
                label=singular,
                name=element.get("Name"),
                key=holder_id,
                properties={
                    k: v for k, v in element.attrib.items() if k in {"Name", "Status", "Type"}
                },
            )
            rels = element.find("c:Relationships", CAPEC_NS)
            if rels is None:
                rels = element.find("c:Members", CAPEC_NS)
            for member in list(rels) if rels is not None else []:
                target = member.get("CAPEC_ID")
                if target is None:
                    continue
                edges.append(
                    Edge(holder_id, "HAS_MEMBER", f"CAPEC-{target}", "capec", "xml-element")
                )

    stats = {
        "patterns_in_file": len(all_patterns),
        "patterns_after_exclusions": len(live),
        "excluded": excluded,
    }
    return nodes, edges, stats


# ---------------------------------------------------------------------------


def source_paths(data_dir: Path = DATA_DIR) -> dict[str, Path]:
    versions = json.loads((data_dir / "versions.json").read_text())
    return {
        "attack": data_dir / "raw" / "attack" / f"v{versions['attack_version']}" / "enterprise-attack.json",
        "capec": data_dir / "raw" / "capec" / f"v{versions['capec_version']}" / "capec_latest.xml",
    }


def build(data_dir: Path = DATA_DIR) -> RawGraph:
    """Parse both pinned sources into one graph, with the load policy applied."""
    versions = json.loads((data_dir / "versions.json").read_text())
    paths = source_paths(data_dir)

    attack_nodes, attack_edges, attack_stats = _parse_attack(
        json.loads(paths["attack"].read_text())
    )
    capec_nodes, capec_edges, capec_stats = _parse_capec(ET.parse(paths["capec"]).getroot())

    # CAPEC declares ATT&CK technique ids. Those stay separate placeholder nodes
    # rather than being merged onto the STIX objects: merging would make the one
    # cross-source edge type read as an internal one, and would hide the join
    # the system under test is supposed to perform. They are *linked* instead —
    # `resolves_to` points at the real object where one exists — so a population
    # count can skip them without losing the reference.
    nodes = dict(attack_nodes)
    nodes.update(capec_nodes)

    by_key = {n.key: n.id for n in attack_nodes.values() if n.key}
    for node_id, node in list(nodes.items()):
        if node.placeholder and node.key in by_key:
            nodes[node_id] = replace(node, resolves_to=by_key[node.key])

    return RawGraph(
        nodes=nodes,
        edges=attack_edges + capec_edges,
        stats={
            "attack": {"version": versions["attack_version"], **attack_stats},
            "capec": {"version": versions["capec_version"], **capec_stats},
        },
    )
