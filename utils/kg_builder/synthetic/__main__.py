#!/usr/bin/env python3
"""Write the synthetic tenant and its blueprint as canonical artifacts.

    uv run python -m utils.kg_builder.synthetic --seed 20260821 --out data-identity

Produces the same shapes the ATT&CK and CAPEC builds produce -- ``nodes.jsonl``,
``relationships.jsonl``, ``schema.json``, ``manifest.json`` -- plus ``spec.json``,
which no other dataset has because no other dataset needed an independent source
of truth manufactured for it. See :mod:`utils.kg_builder.synthetic.spec`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ..catalog.declared import DECLARED
from ..catalog.reader import read_catalog
from ..catalog.inferred import apply_inferred
from ..catalog.declared import DeclaredCatalog
from .generator import generate

_TYPE_MAP = {
    "STRING": "string",
    "BOOLEAN": "boolean",
    "INTEGER": "integer",
    "LIST_STRING": "array",
}


def _write_jsonl(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _schema_json(catalog: DeclaredCatalog, nodes: list[dict]) -> dict:
    """The canonical schema file, built from the catalog and an example value.

    Examples come from generated nodes rather than being invented, so the source
    card shows a reader what an identifier on this source actually looks like.
    """
    example: dict[str, dict] = {}
    for node in nodes:
        example.setdefault(node["label"], node["properties"])
    node_properties: dict[str, dict] = {}
    for label, attrs in sorted(catalog.node_attributes.items()):
        sample = example.get(label, {})
        node_properties[label] = {
            attr.name: {
                "type": _TYPE_MAP.get(attr.value_type, "string"),
                "optional": attr.name not in sample,
                "example": sample.get(attr.name),
                "declared_type": attr.value_type,
            }
            for attr in sorted(attrs.values())
        }
    return {
        "dataset": catalog.name,
        "node_labels": sorted(catalog.node_attributes),
        "node_properties": node_properties,
        "relationship_types": sorted({t.edge for t in catalog.triples}),
        "relationship_endpoints": [
            {
                "source": t.source,
                "type": t.edge,
                "target": t.target,
                "origin": t.origin,
                "homogeneous": t.is_homogeneous,
            }
            for t in sorted(catalog.triples)
        ],
        "provenance": "declared",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=20260821)
    parser.add_argument("--out", default="data-identity")
    parser.add_argument("--catalog-dir", default=None)
    parser.add_argument("--dataset", default="identity")
    args = parser.parse_args(argv)

    catalog = apply_inferred(read_catalog(args.catalog_dir, name=args.dataset))
    nodes, edges, spec = generate(catalog, seed=args.seed)

    base = Path(args.out) / "graphs" / args.dataset / "canonical"
    nodes_hash = _write_jsonl(base / "nodes.jsonl", nodes)
    edges_hash = _write_jsonl(base / "relationships.jsonl", edges)
    (base / "schema.json").write_text(
        json.dumps(_schema_json(catalog, nodes), indent=2) + "\n", encoding="utf-8"
    )
    spec_path = spec.write(base / "spec.json")

    counts = spec.counts()
    manifest = {
        "dataset": args.dataset,
        "schema_version": "1.0",
        "seed": args.seed,
        "counts": counts,
        "catalog": {
            "source_files": catalog.source_files,
            "counts": catalog.counts(),
            "truncated": bool(catalog.truncation and catalog.truncation.suspected),
        },
        "canonical": {
            "nodes_jsonl": str(base / "nodes.jsonl"),
            "relationships_jsonl": str(base / "relationships.jsonl"),
            "schema_json": str(base / "schema.json"),
            "spec_json": str(spec_path),
        },
        "hashes": {"nodes_jsonl": nodes_hash, "relationships_jsonl": edges_hash},
        "metadata": {
            "instances": "synthetic",
            "schema": "real — ReliaQuest customer catalog",
            "note": (
                "Instances are generated, not observed. The schema they conform "
                "to is real. Any claim from this dataset is about schema "
                "navigation, never about detection quality."
            ),
        },
    }
    (base / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"wrote {base}")
    print(f"  nodes                    {counts['nodes']}")
    print(f"  edges                    {counts['edges']}")
    print(f"    declared               {counts['edges_declared']}")
    print(f"    inferred               {counts['edges_inferred']}")
    print(f"  planted paths            {counts['planted_paths']}")
    print(f"  labels populated         {len(counts['nodes_by_label'])}")
    print(f"  edge kinds populated     {len(counts['edges_by_label'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
