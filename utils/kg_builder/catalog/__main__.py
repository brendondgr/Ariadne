#!/usr/bin/env python3
"""Turn the delivered CSVs into ``declared.json``.

    uv run python -m utils.kg_builder.catalog --out data-identity/catalog/declared.json

Everything downstream reads that one artifact rather than re-parsing CSV, so the
inferred-edge decision and the truncation finding are made once and travel with
the data.
"""

from __future__ import annotations

import argparse
import sys

from .inferred import apply_inferred
from .reader import CATALOG_DIR_ENV, read_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--catalog-dir",
        default=None,
        help=f"directory holding the delivered CSVs (default: ${CATALOG_DIR_ENV})",
    )
    parser.add_argument(
        "--out",
        default="data-identity/catalog/declared.json",
        help="where to write the declared-schema artifact",
    )
    parser.add_argument(
        "--no-inferred",
        action="store_true",
        help="write the delivery alone, without this project's inferred edges",
    )
    parser.add_argument("--name", default="identity")
    parser.add_argument(
        "--card",
        default=None,
        help="also write a source card here, merging the overlay named by --overlay",
    )
    parser.add_argument(
        "--overlay",
        default="data-identity/source_cards/overlays/identity.overlay.json",
    )
    parser.add_argument(
        "--nodes",
        default="data-identity/graphs/identity/canonical/nodes.jsonl",
        help="generated nodes, read only to fill the card's property examples",
    )
    args = parser.parse_args(argv)

    catalog = read_catalog(args.catalog_dir, name=args.name)
    if not args.no_inferred:
        apply_inferred(catalog)

    path = catalog.write(args.out)
    counts = catalog.counts()

    if args.card:
        import json as _json
        from pathlib import Path as _Path

        from .card import build_card, examples_from_nodes, load_overlay, write_card

        examples: dict = {}
        nodes_path = _Path(args.nodes)
        if nodes_path.is_file():
            rows = [
                _json.loads(line)
                for line in nodes_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            examples = examples_from_nodes(rows)
        card = build_card(
            catalog,
            load_overlay(args.overlay),
            out_dir=_Path(args.card).parent.parent,
            examples=examples,
            dataset=args.name,
        )
        print(f"wrote {write_card(card, args.card)}")

    print(f"wrote {path}")
    for key, value in counts.items():
        print(f"  {key:24s} {value}")
    if catalog.truncation and catalog.truncation.suspected:
        print("\n  TRUNCATED DELIVERY — the export could not contain every edge type:")
        for line in catalog.truncation.evidence:
            print(f"    - {line}")
        print(f"    corrected query: {catalog.truncation.corrected_query}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
