#!/usr/bin/env python3
"""Draw the Step 6 capability probe: specs covering the never-asked shapes.

Step 6 asks one question — **can the builder express these shapes at all?** —
and it must be answered before authoring at scale, so that a low score on new
shapes has a cause already on file rather than being attributed to the system by
default.

The draw is shape-first, not tier-first. Every edge type the census marks as
never asked gets `--per-shape` specs, and a handful of already-asked shapes come
along as a control: without them a low probe score could be the new shapes or
could be the harness, and there would be no way to tell.

Usage:
    uv run python scripts/select_probe.py --per-shape 3
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from scripts.render_questions import DEFAULT_SPECS, load_specs
from utils.specialists.evalset import render as rd
from utils.specialists.evalset.schema_census import OUT_DIR as CENSUS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--census", type=Path,
                        default=CENSUS_DIR / "attack-19.0-capec-3.9" / "census.json")
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evaluation/composition/probe/selection.json"))
    parser.add_argument("--per-shape", type=int, default=3)
    parser.add_argument("--controls", type=int, default=12,
                        help="specs on already-asked shapes, so a low score is attributable")
    parser.add_argument("--seed", type=int, default=20260901)
    args = parser.parse_args()

    census = json.loads(args.census.read_text())
    never = set(census["coverage"]["never_asked"])
    asked = set(census["coverage"]["reached"])
    specs = [s for s in load_specs(args.specs) if rd.renderable(s)]

    by_shape: dict[str, list] = defaultdict(list)
    for spec in specs:
        for shape in spec.shapes:
            if shape in never:
                by_shape[shape].append(spec)

    rng = random.Random(args.seed)
    chosen: dict[str, object] = {}
    for shape in sorted(by_shape):
        pool = sorted(by_shape[shape], key=lambda s: s.id)
        for spec in rng.sample(pool, min(args.per_shape, len(pool))):
            chosen[spec.id] = spec

    control_pool = sorted(
        (s for s in specs if s.shapes and all(sh in asked for sh in s.shapes)),
        key=lambda s: s.id,
    )
    controls = rng.sample(control_pool, min(args.controls, len(control_pool)))
    for spec in controls:
        chosen.setdefault(spec.id, spec)

    control_ids = {s.id for s in controls}
    picked = sorted(chosen.values(), key=lambda s: (s.tier, s.id))
    covered = {sh for s in picked for sh in s.shapes if sh in never}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "seed": args.seed,
                "per_shape": args.per_shape,
                "never_asked_total": len(never),
                "never_asked_covered": len(covered),
                "uncovered": sorted(never - covered),
                "controls": sorted(control_ids),
                "spec_ids": [s.id for s in picked],
            },
            indent=1,
        )
        + "\n"
    )

    print(f"probe: {len(picked)} specs -> {args.out}")
    print(f"  never-asked shapes covered: {len(covered)}/{len(never)}")
    print(f"  controls on already-asked shapes: {len(control_ids)}")
    tiers: dict[str, int] = defaultdict(int)
    for spec in picked:
        tiers[spec.tier] += 1
    print(f"  by tier: {dict(sorted(tiers.items()))}")
    if never - covered:
        print("  NOT covered:")
        for shape in sorted(never - covered):
            print(f"    - {shape}")


if __name__ == "__main__":
    main()
