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
    args = parser.parse_args(argv)

    catalog = read_catalog(args.catalog_dir, name=args.name)
    if not args.no_inferred:
        apply_inferred(catalog)

    path = catalog.write(args.out)
    counts = catalog.counts()

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
