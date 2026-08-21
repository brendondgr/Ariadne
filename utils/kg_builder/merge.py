#!/usr/bin/env python3
"""Build the merged-graph counterfactual's dataset (C-015).

The project's pitch is that keeping ATT&CK and CAPEC in separate engines, each
queried in its own language, is worth the complexity. `CLAIMS.md` C-015 has
never been contrasted with the obvious alternative — pour both into one graph
and query that — because the alternative was never built. This module builds it.

**Where the output goes, and why it is not `data/graphs/`.** Everything lands
under ``data/merged/``, mirroring the ordinary layout (``graphs/merged/canonical``,
``source_cards/merged.json``) so the loader, the schema registry and the
specialists all work unchanged when pointed at it with ``ARIADNE_DATA_DIR``.
Putting it in the ordinary place would have made it visible to every arm:
:func:`utils.planner.cards.load_source_cards` globs ``source_cards/*.json``, so a
merged card there becomes a third source the planner can route to, and
:func:`utils.specialists.schema.build.discover_datasets` walks ``graphs/``, so a
merged dataset there gets walked into the schema registry that ``binding.py``
and ``direction.py`` build on the default path. Both would have changed arms
that are already measured and recorded. Isolation is by directory rather than
by a flag, because a directory cannot be left switched on by accident.

**The one substantive transformation.** ATT&CK nodes carry their public
identifier in ``properties.attack_id`` (``T1047``); :func:`node_merge_cypher`
promotes it to ``n.attack_id``, and every schema-driven query anchors on
``coalesce(n.attack_id, n.id)``. CAPEC nodes carry no equivalent — their public
id is *derived* from the node id (``capec:attack-pattern:66`` → ``CAPEC-66``) by
the Gremlin normalizer at read time. A merged store queried in Cypher has no
such read-time step, so a seed of ``CAPEC-66`` would match nothing. This build
therefore writes the public id into the shared property.

That is the federated system's own work moved from code into data, not a favour
to the merged arm: :func:`utils.specialists.gremlin.builder._capec_gremlin_id`
does the same translation on the way in and the normalizer does it on the way
out. The rule is *imported* from the federated path rather than restated, so the
merged store's public-id surface is identical — ``CAPEC-<n>`` and ``CWE-<n>``,
with composite children (``…:mitigation:0``) keeping their raw ids, exactly as
the Gremlin path reports them. Recorded as a design decision in `DECISIONS.md`.

Usage::

    uv run python -m utils.kg_builder.merge          # writes data/merged/
    uv run python -m utils.kg_builder.merge --check  # verify without writing
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from utils.kg_builder.io import ensure_dir, load_json, read_jsonl, write_json
from utils.specialists.gremlin.normalizer import public_member_id

#: The two catalogues, in load order. ATT&CK first so its half of the merged
#: files is a byte-for-byte prefix, which makes the "did the ATT&CK side change"
#: check a comparison rather than a search.
SOURCES = ("attack", "capec")

#: The property every Cypher query anchors on via ``coalesce(n.attack_id, n.id)``.
#: Named for ATT&CK because that is where it came from; in the merged graph it
#: means "this catalogue's public identifier" for both halves.
PUBLIC_ID_PROPERTY = "attack_id"

DEFAULT_DATA_DIR = Path("data")
DEFAULT_OUT_DIR = Path("data") / "merged"


# -- reading the two sources -------------------------------------------------


def canonical_dir(data_dir: Path, dataset: str) -> Path:
    return data_dir / "graphs" / dataset / "canonical"


def _read_source(data_dir: Path, dataset: str) -> dict[str, Any]:
    canon = canonical_dir(data_dir, dataset)
    return {
        "dataset": dataset,
        "nodes": list(read_jsonl(canon / "nodes.jsonl")),
        "relationships": list(read_jsonl(canon / "relationships.jsonl")),
        "schema": load_json(canon / "schema.json"),
        "manifest": load_json(canon / "manifest.json"),
        "card": load_json(data_dir / "source_cards" / f"{dataset}.json"),
        "constraints": (
            data_dir / "graphs" / dataset / "exports" / "neo4j" / "constraints.cypher"
        ).read_text(encoding="utf-8"),
    }


# -- the transformation ------------------------------------------------------


def promote_public_id(node: dict[str, Any]) -> dict[str, Any]:
    """Give a CAPEC node the public identifier its ATT&CK counterpart already has.

    Returns a new node; the input is not mutated. A node that already carries
    the property (every ATT&CK node) is returned unchanged, and so is one whose
    id has no public form (a Category, a View, a composite child) — those are
    reported by their raw id in the federated system too, and inventing a
    public id here would give the merged arm identifiers the federated arms
    never emit.
    """
    props = dict(node.get("properties") or {})
    if props.get(PUBLIC_ID_PROPERTY):
        return node
    public = public_member_id(str(node.get("id") or ""))
    if public == node.get("id"):
        return node
    props[PUBLIC_ID_PROPERTY] = public
    merged = dict(node)
    merged["properties"] = props
    return merged


def _merge_schema(schemas: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Union the two catalogues' declared structure.

    The two schema files do not carry identical key sets — CAPEC declares
    ``allowed_edge_patterns`` and ``required_node_properties`` and ATT&CK does
    not — so keys are unioned rather than assumed.
    """
    labels: set[str] = set()
    rel_types: set[str] = set()
    node_properties: dict[str, set[str]] = {}
    edge_patterns: dict[str, list[list[str]]] = {}
    required: dict[str, set[str]] = {}
    natures: set[str] = set()
    for schema in schemas:
        labels |= set(schema.get("node_labels") or [])
        rel_types |= set(schema.get("relationship_types") or [])
        natures |= set(schema.get("relationship_natures") or [])
        for label, props in (schema.get("node_properties") or {}).items():
            node_properties.setdefault(label, set()).update(props)
        for label, props in (schema.get("required_node_properties") or {}).items():
            required.setdefault(label, set()).update(props)
        for rel, patterns in (schema.get("allowed_edge_patterns") or {}).items():
            existing = edge_patterns.setdefault(rel, [])
            for pattern in patterns:
                pair = list(pattern)
                if pair not in existing:
                    existing.append(pair)

    merged: dict[str, Any] = {
        "dataset": "merged",
        "schema_version": "1.0",
        "node_labels": sorted(labels),
        "relationship_types": sorted(rel_types),
        "node_properties": {k: sorted(v) for k, v in sorted(node_properties.items())},
        "allowed_edge_patterns": {
            k: sorted(v) for k, v in sorted(edge_patterns.items())
        },
    }
    if required:
        merged["required_node_properties"] = {
            k: sorted(v) for k, v in sorted(required.items())
        }
    if natures:
        merged["relationship_natures"] = sorted(natures)
    return merged


def _merge_constraints(sources: list[dict[str, Any]]) -> str:
    """Union both constraint files, dropping statements that say the same thing.

    ``Mitigation`` exists in both catalogues, so both files ask for
    ``FOR (n:Mitigation) REQUIRE n.id IS UNIQUE`` under different constraint
    names. Neo4j's ``IF NOT EXISTS`` would tolerate that, but relying on the
    server to notice is worse than not emitting the duplicate: the dedupe is on
    what the statement *requires*, not on what it is called.
    """
    lines = ["// Merged-graph constraints (generated by utils/kg_builder/merge.py)"]
    seen: set[str] = set()
    for source in sources:
        for raw in source["constraints"].splitlines():
            statement = raw.strip()
            if not statement or statement.startswith("//"):
                continue
            _, _, requirement = statement.partition(" FOR ")
            key = requirement.strip().rstrip(";")
            if key in seen:
                lines.append(f"// (dropped as a duplicate of an earlier rule) {statement}")
                continue
            seen.add(key)
            lines.append(statement)
    return "\n".join(lines) + "\n"


def _merge_card(sources: list[dict[str, Any]], schema: dict[str, Any],
                out_dir: Path) -> dict[str, Any]:
    """One source card describing the union, generated rather than authored."""
    by_name = {s["dataset"]: s for s in sources}
    attack, capec = by_name["attack"]["card"], by_name["capec"]["card"]

    node_glosses: dict[str, str] = {}
    rel_glosses: dict[str, str] = {}
    for card, source_name in ((attack, "ATT&CK"), (capec, "CAPEC")):
        descriptions = card.get("entity_descriptions") or {}
        for label, gloss in (descriptions.get("nodes") or {}).items():
            if label in node_glosses:
                node_glosses[label] = (
                    f"{node_glosses[label]} In this merged graph the label also "
                    f"holds {source_name} entries: {gloss} The two are told apart "
                    f"by the marker labels AttackObject and CapecObject."
                )
            else:
                node_glosses[label] = gloss
        for rel, gloss in (descriptions.get("relationships") or {}).items():
            rel_glosses.setdefault(rel, gloss)

    collisions = {
        label: (
            f"Present in both catalogues. Scope by the marker label "
            f"(AttackObject / CapecObject) or by the relationship walked; the "
            f"identifier spaces do not overlap."
        )
        for label in sorted(
            set(attack.get("node_labels") or []) & set(capec.get("node_labels") or [])
        )
    }

    prefix = out_dir.as_posix()
    return {
        "schema_version": attack.get("schema_version", "1.0"),
        "dataset": "merged",
        "runtime_backend": "neo4j",
        "canonical_dir": f"{prefix}/graphs/merged/canonical",
        "canonical_manifest": f"{prefix}/graphs/merged/canonical/manifest.json",
        "connection": {
            "backend": "neo4j",
            "database": "neo4j",
            "read_only": True,
            "timeout_ms": 5000,
            "uri": "bolt://localhost:5458",
            "auth_env": {"user": "NEO4J_USER", "password": "NEO4J_PASSWORD"},
        },
        "endpoints": {"neo4j": "", "gremlin": ""},
        "exports": {
            "neo4j": {
                "constraints_cypher":
                    f"{prefix}/graphs/merged/exports/neo4j/constraints.cypher",
            }
        },
        "node_labels": schema["node_labels"],
        "relationship_types": schema["relationship_types"],
        "node_properties": schema["node_properties"],
        "entity_descriptions": {
            "nodes": dict(sorted(node_glosses.items())),
            "relationships": dict(sorted(rel_glosses.items())),
        },
        "identity": {
            "constraints": sorted(
                set(attack.get("identity", {}).get("constraints", []))
                | set(capec.get("identity", {}).get("constraints", []))
            ),
            "join_key": ["attack_id"],
            "known_collisions": collisions,
            "not_traversable": {
                **(attack.get("identity", {}).get("not_traversable") or {}),
                **(capec.get("identity", {}).get("not_traversable") or {}),
            },
            "policy": (
                "One store, two catalogues. Identifier spaces are disjoint — ATT&CK "
                "nodes carry a STIX UUID as `id` and a T/S/G/M/TA/DC id as "
                "`attack_id`; CAPEC nodes carry a `capec:*` or `cwe:*` `id` and, in "
                "this merged build only, the derived public id (CAPEC-n, CWE-n) in "
                "the same `attack_id` property so one query predicate anchors both "
                "halves. `Mitigation` is the single label present in both; scope it "
                "by marker label or by the relationship walked. The cross-source "
                "correlation that the federated system performs as a declared join "
                "is, here, an ordinary traversal through CAPEC TaxonomyEntry nodes."
            ),
            "unique_backstop": "id",
        },
        "provenance": {
            "dataset_version": (
                f"attack {attack.get('provenance', {}).get('dataset_version', '?')} + "
                f"capec {capec.get('provenance', {}).get('dataset_version', '?')}"
            ),
            "id_property": "id",
            "id_scheme": "mixed",
            "snapshot_pinned": True,
            "source_name": "MITRE ATT&CK + MITRE CAPEC (merged, C-015 counterfactual)",
            "raw_sha256": {
                "attack": attack.get("provenance", {}).get("raw_sha256"),
                "capec": capec.get("provenance", {}).get("raw_sha256"),
            },
        },
        "safety": attack.get("safety", {}),
    }


# -- the build ---------------------------------------------------------------


def build_merged(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Merge both catalogues into one dataset. Returns a summary of what it built."""
    data_dir, out_dir = Path(data_dir), Path(out_dir)
    sources = [_read_source(data_dir, name) for name in SOURCES]

    nodes: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    promoted = 0
    for source in sources:
        for node in source["nodes"]:
            merged_node = promote_public_id(node)
            promoted += merged_node is not node
            nodes.append(merged_node)
        relationships.extend(source["relationships"])

    ids = [n["id"] for n in nodes]
    duplicates = [i for i, c in Counter(ids).items() if c > 1]
    if duplicates:
        raise ValueError(
            f"{len(duplicates)} node id(s) appear in both catalogues, e.g. "
            f"{duplicates[:3]} — the merge assumes disjoint identifier spaces"
        )

    schema = _merge_schema(s["schema"] for s in sources)
    manifest = {
        "dataset": "merged",
        "build": "utils/kg_builder/merge.py",
        "merged_from": {
            s["dataset"]: {
                "nodes": len(s["nodes"]),
                "relationships": len(s["relationships"]),
                "dataset_version": s["card"].get("provenance", {}).get("dataset_version"),
                "raw_sha256": s["card"].get("provenance", {}).get("raw_sha256"),
            }
            for s in sources
        },
        "canonical": {
            "nodes_jsonl": f"{out_dir.as_posix()}/graphs/merged/canonical/nodes.jsonl",
            "relationships_jsonl":
                f"{out_dir.as_posix()}/graphs/merged/canonical/relationships.jsonl",
            "schema_json": f"{out_dir.as_posix()}/graphs/merged/canonical/schema.json",
        },
        "exports": {
            "neo4j": {
                "constraints_cypher":
                    f"{out_dir.as_posix()}/graphs/merged/exports/neo4j/constraints.cypher",
            }
        },
        "counts": {
            "nodes": len(nodes),
            "nodes_by_label": dict(sorted(Counter(n["label"] for n in nodes).items())),
            "relationships": len(relationships),
            "relationships_by_type": dict(
                sorted(Counter(r["type"] for r in relationships).items())
            ),
        },
        "public_ids_promoted": promoted,
    }

    summary = {
        "nodes": len(nodes),
        "relationships": len(relationships),
        "public_ids_promoted": promoted,
        "labels": len(schema["node_labels"]),
        "relationship_types": len(schema["relationship_types"]),
        "out_dir": str(out_dir),
    }
    if not write:
        return summary

    canon = ensure_dir(out_dir / "graphs" / "merged" / "canonical")
    exports = ensure_dir(out_dir / "graphs" / "merged" / "exports" / "neo4j")
    ensure_dir(out_dir / "source_cards")

    # Written line by line rather than through write_jsonl so a 9k-node file
    # never has to exist twice in memory as a joined string.
    for name, records in (("nodes", nodes), ("relationships", relationships)):
        with open(canon / f"{name}.jsonl", "w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    write_json(canon / "schema.json", schema)
    write_json(canon / "manifest.json", manifest)
    (exports / "constraints.cypher").write_text(
        _merge_constraints(sources), encoding="utf-8"
    )
    write_json(out_dir / "source_cards" / "merged.json",
               _merge_card(sources, schema, out_dir))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--check", action="store_true",
                        help="compute the merge without writing anything")
    args = parser.parse_args(argv)
    summary = build_merged(args.data_dir, args.out_dir, write=not args.check)
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
