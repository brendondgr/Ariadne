#!/usr/bin/env python3
"""Enumerate question specifications from the pinned snapshot (Step 1).

Deterministic, LLM-free. Writes the spec pool the renderer draws from, plus a
summary that shows how much of the census each tier reaches.

Usage:
    uv run python scripts/enumerate_compositions.py
    uv run python scripts/enumerate_compositions.py --per-shape 8 --seed 20260901
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from utils.specialists.evalset import composition as comp
from utils.specialists.evalset import raw_graph as rg
from utils.specialists.evalset.schema_census import OUT_DIR as CENSUS_DIR
from utils.specialists.evalset.schema_census import build_census

DEFAULT_OUT = Path("docs/evaluation/composition")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-shape", type=int, default=4,
                        help="anchors per shape; bounds rare and common shapes alike")
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    graph = rg.build()
    census = build_census()
    specs = comp.enumerate_specs(
        graph, census, per_shape_limit=args.per_shape, seed=args.seed
    )
    summary = comp.summarise(specs)

    version = f"attack-{census['sources']['attack']['version']}-capec-{census['sources']['capec']['version']}"
    out = args.out / version
    comp.write(specs, out / "specs.json")

    # How much of the census the pool reaches — the number Step 1 exists for.
    census_shapes = {e["triple"] for e in census["edges"]}
    pool_shapes = {s for spec in specs for s in spec.shapes if s in census_shapes}
    never = set(census["coverage"]["never_asked"])

    report = {
        "seed": args.seed,
        "per_shape_limit": args.per_shape,
        "census": version,
        **summary,
        "census_edge_types": len(census_shapes),
        "census_edge_types_reached": len(pool_shapes),
        "census_edge_type_coverage": round(len(pool_shapes) / len(census_shapes), 4),
        "never_asked_edge_types_reached": len(pool_shapes & never),
        "never_asked_edge_types_total": len(never),
        "unreached_edge_types": sorted(census_shapes - pool_shapes),
        "specs_with_dangling": sum(1 for s in specs if s.dangling),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n")

    print(f"specs -> {out}")
    print(f"  {summary['specs']:,} specs, {summary['distinct_shapes']} distinct path shapes")
    print(f"  by tier: {summary['by_tier']}")
    print(f"  by source: {summary['by_source']}")
    print(
        f"  census coverage: {report['census_edge_types_reached']}/"
        f"{report['census_edge_types']} edge types "
        f"({report['census_edge_type_coverage']:.1%}); "
        f"{report['never_asked_edge_types_reached']}/"
        f"{report['never_asked_edge_types_total']} previously never asked"
    )
    width = summary["gold_width"]
    print(f"  gold width: median {width['median']}, p90 {width['p90']}, max {width['max']}")
    if report["unreached_edge_types"]:
        print(f"  NOT reached ({len(report['unreached_edge_types'])}):")
        for triple in report["unreached_edge_types"]:
            print(f"    - {triple}")


if __name__ == "__main__":
    main()
