#!/usr/bin/env python3
"""What the sources support, against what the loaded graph actually holds.

The census reads the raw files and reports the shapes the *sources* support. The
ingest pipeline then loads a graph, and nothing until now compared the two. The
Step 6 capability probe was supposed to ask "can the builder express these
shapes"; it returned near-zero on shapes the committed banks answer perfectly,
which is a harness fault rather than a capability finding — and chasing it here
is what surfaced the real question:

**the two vocabularies are different, and some of the difference is missing
data, not naming.**

The census names an edge the way the source declares it (`kill_chain_phase`,
`MAPS_TO[WASC]`). The loaded graph names it its own way (`HAS_TECHNIQUE`,
`MAPS_TO`), sometimes reversed, sometimes collapsing several census edge types
into one — and sometimes not loading it at all. A question about a shape in the
last group cannot be answered by any arm, because the rows are not there.

`PREDICATE_MAP` is the reconciliation, hand-written and explicit. Every census
predicate must appear in it, mapped either to a graph relationship (with the
direction it is stored in) or to `None`, which asserts the edge is absent from
the load. A census predicate missing from the map fails the run rather than
defaulting, because a silent default is how "we cannot ask this" turns into
"the system got it wrong".

    uv run python scripts/reconcile_graph.py
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

CANONICAL = Path("data/graphs")
CENSUS = Path("docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json")

#: census predicate -> (graph relationship type, reversed?) or None when the
#: ingest does not load it. `reversed` means the graph stores the edge with the
#: endpoints swapped relative to how the source declares it.
PREDICATE_MAP: dict[str, tuple[str, bool] | None] = {
    # ATT&CK
    "uses": ("USES", False),
    "mitigates": ("MITIGATES", False),
    "detects": ("DETECTS", False),
    "subtechnique-of": ("HAS_SUBTECHNIQUE", True),
    "attributed-to": ("ATTRIBUTED_TO", False),
    "kill_chain_phase": ("HAS_TECHNIQUE", True),
    "x_mitre_analytic_refs": ("HAS_ANALYTIC", False),
    "tactic_refs": ("HAS_TACTIC", False),
    "log_source": ("MONITORS", True),
    # CAPEC — same name, same direction
    "EXPLOITS_WEAKNESS": ("EXPLOITS_WEAKNESS", False),
    "HAS_MITIGATION": ("HAS_MITIGATION", False),
    "HAS_CONSEQUENCE": ("HAS_CONSEQUENCE", False),
    "HAS_EXECUTION_STEP": ("HAS_EXECUTION_STEP", False),
    "REQUIRES_SKILL": ("REQUIRES_SKILL", False),
    "ChildOf": ("ChildOf", False),
    "CanPrecede": ("CanPrecede", False),
    "CanFollow": ("CanFollow", False),
    "CanAlsoBe": ("CanAlsoBe", False),
    "PeerOf": ("PeerOf", False),
    # CAPEC — renamed or reversed
    "HAS_MEMBER": ("MEMBER_OF", True),  # also IN_VIEW for View members
    # CAPEC — three census edge types collapse into one graph relationship, so
    # a question that distinguishes the taxonomies cannot be answered as asked.
    "MAPS_TO[ATTACK]": ("MAPS_TO", False),
    "MAPS_TO[WASC]": ("MAPS_TO", False),
    "MAPS_TO[OWASP Attacks]": ("MAPS_TO", False),
    # CAPEC — declared by the source, absent from the load.
    "HAS_PREREQUISITE": None,
    "HAS_INDICATOR": None,
    "HAS_EXAMPLE": None,
    "REQUIRES_RESOURCE": None,
    "HAS_ALTERNATE_TERM": None,
}


#: census label -> the label the loaded graph uses, or None when the ingest does
#: not load that kind of node at all. Identity mappings are omitted.
#:
#: The distinction this encodes is the one that matters: `CapecMitigation` is
#: present under another name and `Prerequisite` is simply not there. Collapsing
#: both into "absent" would overstate the gap by 1,242 nodes.
LABEL_MAP: dict[str, str | None] = {
    "CapecMitigation": "Mitigation",
    "TaxonomyEntry:WASC": "TaxonomyEntry",
    "TaxonomyEntry:OWASP Attacks": "TaxonomyEntry",
    "DataSource": None,
    "Prerequisite": None,
    "Indicator": None,
    "Example": None,
    "Resource": None,
    "AlternateTerm": None,
}

#: Population differences that are a known modelling choice rather than a gap.
#: Anything not listed here and not equal is an open discrepancy and is reported
#: as one — the point of the reconciliation is that nothing explains itself.
EXPLAINED_COUNTS: dict[str, str] = {
    "Technique": "the graph splits Technique (222) from SubTechnique (475); "
                 "the sum is the census's 697",
    "TaxonomyEntry:WASC": "the graph keeps one TaxonomyEntry label for all three "
                          "taxonomies; the census splits them",
    "TaxonomyEntry:OWASP Attacks": "the graph keeps one TaxonomyEntry label for all "
                                   "three taxonomies; the census splits them",
}

#: census label -> which store holds it. Both catalogues use `Mitigation`, so a
#: combined count would report 1,214 where each store holds 44 and 1,170.
from utils.specialists.evalset.spec_bank import home_store  # noqa: E402


def load_graph(source: str) -> tuple[collections.Counter, collections.Counter]:
    labels: collections.Counter = collections.Counter()
    rels: collections.Counter = collections.Counter()
    for line in (CANONICAL / source / "canonical" / "nodes.jsonl").open():
        node = json.loads(line)
        for label in node.get("labels") or ([node["label"]] if node.get("label") else []):
            labels[label] += 1
    for line in (CANONICAL / source / "canonical" / "relationships.jsonl").open():
        edge = json.loads(line)
        rels[edge.get("type") or edge.get("rel_type")] += 1
    return labels, rels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, default=CENSUS)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evaluation/schema-census/reconciliation.json"))
    args = parser.parse_args()

    census = json.loads(args.census.read_text())
    per_store: dict[str, tuple[collections.Counter, collections.Counter]] = {
        source: load_graph(source) for source in ("attack", "capec")
    }
    rels: collections.Counter = collections.Counter()
    for _labels, source_rels in per_store.values():
        rels.update(source_rels)

    unmapped = sorted(
        {e["predicate"] for e in census["edges"]} - set(PREDICATE_MAP)
    )
    if unmapped:
        raise SystemExit(
            f"census predicates missing from PREDICATE_MAP: {unmapped}\n"
            "Map each to a graph relationship or to None. Defaulting is how "
            '"we cannot ask this" becomes "the system got it wrong".'
        )

    edges: list[dict[str, Any]] = []
    for edge in census["edges"]:
        mapped = PREDICATE_MAP[edge["predicate"]]
        edges.append(
            {
                "triple": edge["triple"],
                "census_count": edge["count"],
                "graph_relationship": mapped[0] if mapped else None,
                "stored_reversed": mapped[1] if mapped else None,
                "graph_count": rels.get(mapped[0]) if mapped else 0,
                "loaded": mapped is not None,
            }
        )

    # Several census edge types can share one graph relationship; report that
    # rather than letting the counts look like a mismatch.
    collapsed: dict[str, list[str]] = collections.defaultdict(list)
    for edge in edges:
        if edge["graph_relationship"]:
            collapsed[edge["graph_relationship"]].append(edge["triple"])
    collapsed = {k: v for k, v in collapsed.items() if len(v) > 1}

    node_rows = []
    for node in census["nodes"]:
        label = node["label"]
        store = home_store(label)
        graph_labels = per_store[store][0]
        mapped = LABEL_MAP.get(label, label)
        node_rows.append(
            {
                "label": label,
                "store": store,
                "graph_label": mapped,
                "renamed": mapped is not None and mapped != label,
                "census_count": node["count"],
                "graph_count": graph_labels.get(mapped) if mapped else 0,
                "loaded": mapped is not None and mapped in graph_labels,
            }
        )

    absent_edges = [e for e in edges if not e["loaded"]]
    absent_labels = [n for n in node_rows if not n["loaded"]]
    never = set(census["coverage"]["never_asked"])

    report = {
        "census_edge_types": len(edges),
        "edge_types_loaded": sum(1 for e in edges if e["loaded"]),
        "edge_types_absent": len(absent_edges),
        "edge_instances_absent": sum(e["census_count"] for e in absent_edges),
        "census_node_types": len(node_rows),
        "node_types_absent": len(absent_labels),
        "collapsed_relationships": collapsed,
        "absent_edge_types": [
            {"triple": e["triple"], "instances": e["census_count"],
             "never_asked": e["triple"] in never}
            for e in sorted(absent_edges, key=lambda x: -x["census_count"])
        ],
        "absent_node_types": [
            {"label": n["label"], "instances": n["census_count"], "store": n["store"]}
            for n in absent_labels
        ],
        "renamed_node_types": [
            {"label": n["label"], "graph_label": n["graph_label"],
             "census_count": n["census_count"], "graph_count": n["graph_count"]}
            for n in node_rows
            if n["renamed"] and n["loaded"]
        ],
        "count_mismatches": [
            {"label": n["label"], "census": n["census_count"], "graph": n["graph_count"],
             "explained": EXPLAINED_COUNTS.get(n["label"])}
            for n in node_rows
            if n["loaded"] and n["graph_count"] != n["census_count"]
        ],
        "edges": edges,
        "nodes": node_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")

    print(f"reconciliation -> {args.out}")
    print(f"  census edge types: {report['census_edge_types']}; "
          f"loaded: {report['edge_types_loaded']}; "
          f"absent: {report['edge_types_absent']} "
          f"({report['edge_instances_absent']:,} instances)")
    print(f"  census node types: {report['census_node_types']}; "
          f"absent: {report['node_types_absent']}")
    print("\n  edge types the sources declare and the load does not hold:")
    for row in report["absent_edge_types"]:
        mark = " [never asked]" if row["never_asked"] else ""
        print(f"    - {row['triple']}  ({row['instances']:,}){mark}")
    print("\n  node types absent from the load:")
    for row in report["absent_node_types"]:
        print(f"    - {row['label']}  ({row['instances']:,})  [{row['store']}]")
    print("\n  node types present under another name:")
    for row in report["renamed_node_types"]:
        print(f"    - {row['label']} -> {row['graph_label']}  "
              f"(census {row['census_count']:,} / graph {row['graph_count']:,})")
    unexplained = [r for r in report["count_mismatches"] if not r["explained"]]
    print("\n  loaded but with a different population:")
    for row in report["count_mismatches"]:
        delta = row["graph"] - row["census"]
        note = f"  — {row['explained']}" if row["explained"] else "  ** UNEXPLAINED **"
        print(f"    - {row['label']}: census {row['census']:,}, graph {row['graph']:,} "
              f"({delta:+,}){note}")
    print(f"\n  unexplained population differences: {len(unexplained)}")
    print("\n  census edge types collapsed into one graph relationship:")
    for rel, triples in sorted(collapsed.items()):
        print(f"    {rel}: {len(triples)}")
        for triple in triples:
            print(f"      - {triple}")


if __name__ == "__main__":
    main()
