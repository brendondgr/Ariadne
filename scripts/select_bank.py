#!/usr/bin/env python3
"""Draw the expansion bank: stratified, deliberately skewed, and honest about it.

The plan's decision 2 is to over-sample the under-represented corners of the
graph. That is the right call for finding defects and the wrong shape for a
headline number, so this script does three things rather than one:

1. **Draws with a floor per shape**, so a shape carrying 27 instances is
   represented as well as one carrying 11,213. Every one of the census's edge
   types appears, including the 22 no bank has ever asked and the five that
   were not even loaded until today.
2. **Spans the axes that matter** — difficulty tier, direction, gold width, and
   source — inside each shape, so a low score can be attributed to one of them
   rather than to the bank as a whole.
3. **Writes the weights it drew with**, next to the census's natural instance
   distribution. Without that pair, the pooled accuracy of a skewed bank is not
   comparable to anything, and somebody will quote it anyway.

Abstention gets its own quota. D0 specs have no shape to stratify on — they are
defined by the absence of one — so a shape-first draw would exclude them
entirely, which is how the capability probe ended up unable to say anything
about abstention.

    uv run python scripts/select_bank.py --target 440 --paraphrase 40
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from scripts.render_questions import DEFAULT_SPECS, load_specs
from utils.specialists.evalset import render as rd
from utils.specialists.evalset import spec_bank
from utils.specialists.evalset.composition import Spec
from utils.specialists.evalset.schema_census import OUT_DIR as CENSUS_DIR

CENSUS = CENSUS_DIR / "attack-19.0-capec-3.9" / "census.json"

#: Every shape gets at least this many questions, however rare it is.
FLOOR_PER_SHAPE = 6

#: A shape no bank has ever asked is worth this many of one that has. The
#: expansion exists to reach them; a proportional draw would bury them.
NEVER_ASKED_WEIGHT = 2.0

#: Gold-width bands. Q29 found width does not predict score, on a corpus with 6
#: questions above width 20 — too narrow to have detected an effect. Width is
#: therefore spanned deliberately here so the question can be answered properly.
WIDTH_BANDS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "1"),
    (2, 5, "2-5"),
    (6, 20, "6-20"),
    (21, 10**9, "21+"),
)


def band_of(width: int) -> str:
    for low, high, label in WIDTH_BANDS:
        if low <= width <= high:
            return label
    return "1"


def _spread(pool: Sequence[Spec], take: int, rng: random.Random) -> list[Spec]:
    """Take `take` specs from `pool`, spreading over tier, direction and width.

    Round-robin across cells rather than sampling the pool flat: a flat sample
    of a shape whose specs are 90% one tier returns 90% that tier, and the point
    of stratifying is to not do that.
    """
    cells: dict[tuple[str, bool, str], list[Spec]] = defaultdict(list)
    for spec in pool:
        reverse = bool(spec.steps and spec.steps[-1].reverse)
        cells[(spec.tier, reverse, band_of(spec.gold_width))].append(spec)
    for members in cells.values():
        rng.shuffle(members)
        # A spec nobody has ever been asked is taken before one that merely has
        # an unasked register left. `_spread` pops from the END, so the never-
        # asked ones go last; sorting them first would hand the draw exactly the
        # specs it is trying to avoid. Stable after the shuffle, so this orders
        # within a cell without undoing the stratification.
        members.sort(key=lambda s: not bool(getattr(s, "_already_asked", False)))

    order = sorted(cells)
    chosen: list[Spec] = []
    index = 0
    while len(chosen) < take and any(cells[key] for key in order):
        key = order[index % len(order)]
        if cells[key]:
            chosen.append(cells[key].pop())
        index += 1
    return chosen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--census", type=Path, default=CENSUS)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evaluation/composition/bank/selection.json"))
    parser.add_argument("--d1", type=int, default=60, help="property reads")
    parser.add_argument("--single", type=int, default=150,
                        help="single hop, split evenly forward (D2) and reverse (D3) — "
                             "direction is the axis Step 6 found the system fails on")
    parser.add_argument("--two-hop", type=int, default=90)
    parser.add_argument("--constrained", type=int, default=80)
    parser.add_argument("--cross-source", type=int, default=60)
    parser.add_argument("--abstention", type=int, default=60)
    parser.add_argument("--paraphrase", type=int, default=40,
                        help="specs also rendered in the other two registers")
    parser.add_argument("--seed", type=int, default=20260901)
    # -- a FRESH draw: everything below is off by default, so the committed
    #    selection this script already produced is unaffected.
    parser.add_argument(
        "--exclude-bank", action="append", default=[], type=Path,
        help="a bank whose (spec, register) pairs have already been asked. "
             "Repeatable. A spec with no unasked register left is dropped "
             "entirely; a spec that has never been asked at all is preferred "
             "over one that has, and the split is reported.",
    )
    parser.add_argument(
        "--tier-quota", default=None,
        help="explicit per-tier counts, e.g. 'D0=25,D1=28,D2=37,D3=45,D4=62,"
             "D5=58,D6=33'. Overrides the shape arguments, which force D2 and "
             "D3 to be equal halves of --single and so cannot reproduce an "
             "existing bank's mix.",
    )
    args = parser.parse_args()

    census = json.loads(args.census.read_text())
    never = set(census["coverage"]["never_asked"])
    instances = {e["triple"]: e["count"] for e in census["edges"]}

    specs = [s for s in load_specs(args.specs) if rd.renderable(s)]
    specs = [s for s in specs if spec_bank.answerable(s)]

    # A spec whose own brief names its own answer cannot be asked blind. Exactly
    # one exists in the pool, and dropping it at the draw beats failing the
    # brief guard after the selection is written.
    from scripts.prepare_briefs import self_leaks

    leaking = [s.id for s in specs if self_leaks(s)]
    if leaking:
        specs = [s for s in specs if s.id not in set(leaking)]
        print(f"dropped {len(leaking)} spec(s) whose brief names their own gold: "
              f"{', '.join(sorted(leaking))}")

    # Which (spec, register) pairs are already spent. A question is fresh when
    # nobody has ever been asked THAT spec in THAT register; a spec nobody has
    # ever been asked at all is fresher still and is preferred.
    asked: dict[str, set[str]] = defaultdict(set)
    for path in args.exclude_bank:
        doc = json.loads(Path(path).read_text())
        for q in (doc["questions"] if isinstance(doc, dict) else doc):
            asked[str(q["spec_id"])].add(str(q["register"]))
    all_registers = set(rd.REGISTERS)
    if args.exclude_bank:
        before = len(specs)
        specs = [s for s in specs if asked.get(s.id, set()) != all_registers]
        print(f"excluded {before - len(specs)} specs with no unasked register "
              f"left, from {len(args.exclude_bank)} bank(s); {len(specs)} remain")

    # Allocate by tier first, then spread across shapes inside each tier.
    #
    # A shape-first allocation put 112 questions into D1 and 19 into D6: every
    # distinct `Label.property` reads as its own "shape" and collected an
    # edge-type floor, while the two tiers the expansion exists to create got
    # whatever was left. Tier quotas are the thing being controlled, so they are
    # what the draw controls.
    by_tier: dict[str, list[Spec]] = defaultdict(list)
    for spec in specs:
        by_tier[spec.tier].append(spec)
    d0 = by_tier.pop("D0", [])

    quota_by_tier = {
        "D1": args.d1,
        "D2": args.single // 2,
        "D3": args.single - args.single // 2,
        "D4": args.two_hop,
        "D5": args.constrained,
        "D6": args.cross_source,
    }
    abstention_quota = args.abstention
    if args.tier_quota:
        wanted = dict(
            (k.strip(), int(v)) for k, v in
            (part.split("=") for part in args.tier_quota.split(",") if part.strip())
        )
        abstention_quota = wanted.pop("D0", abstention_quota)
        quota_by_tier = wanted

    for spec in specs:
        object.__setattr__(spec, "_already_asked", bool(asked.get(spec.id)))

    rng = random.Random(args.seed)
    chosen: list[Spec] = []
    quota: dict[str, int] = {}
    for tier, want in quota_by_tier.items():
        pool = by_tier.get(tier, [])
        if not pool:
            continue
        # Inside a tier, group by the rarest edge shape the spec touches, so a
        # two-hop question counts toward the corner it reaches rather than the
        # busy edge it starts from. D1 has no edge shape; group by property.
        groups: dict[str, list[Spec]] = defaultdict(list)
        for spec in pool:
            edge_shapes = [sh for sh in spec.shapes if sh in instances]
            key = (
                min(edge_shapes, key=lambda sh: instances[sh])
                if edge_shapes
                else (spec.shapes[0] if spec.shapes else spec.return_field)
            )
            groups[key].append(spec)

        keys = sorted(groups)
        weights = {k: (NEVER_ASKED_WEIGHT if k in never else 1.0) for k in keys}
        floors = {k: min(FLOOR_PER_SHAPE, len(groups[k])) for k in keys}
        # A floor that already exceeds the tier's quota means the tier has more
        # shapes than questions; fall back to an even spread over shapes.
        if sum(floors.values()) >= want:
            floors = {k: max(1, want // max(1, len(keys))) for k in keys}
        left = max(0, want - sum(min(floors[k], len(groups[k])) for k in keys))
        weight_total = sum(weights.values()) or 1.0
        for key in keys:
            take = min(
                len(groups[key]),
                min(floors[key], len(groups[key])) + int(left * weights[key] / weight_total),
            )
            quota[f"{tier}:{key}"] = take
            chosen.extend(_spread(groups[key], take, rng))

    target = sum(quota_by_tier.values())
    if len(chosen) < target:
        taken = {s.id for s in chosen}
        spares = [s for s in specs if s.id not in taken and s.tier != "D0"]
        rng.shuffle(spares)
        chosen.extend(spares[: target - len(chosen)])

    abstention = _spread(d0, min(abstention_quota, len(d0)), rng)
    chosen.extend(abstention)
    chosen.sort(key=lambda s: (s.tier, s.id))

    registers = list(rd.REGISTERS)
    # Round-robin, but never onto a (spec, register) pair somebody has already
    # been asked. Without this, a recycled spec is handed back the very wording
    # register it was spent in and the "fresh" question is the old question.
    assignment: dict[str, list[str]] = {}
    for i, spec in enumerate(chosen):
        spent = asked.get(spec.id, set())
        order = [registers[(i + k) % len(registers)] for k in range(len(registers))]
        free = [r for r in order if r not in spent]
        assignment[spec.id] = [free[0] if free else order[0]]
    paraphrase = rng.sample(chosen, min(args.paraphrase, len(chosen)))
    for spec in paraphrase:
        assignment[spec.id] = list(registers)

    questions = sum(len(v) for v in assignment.values())
    per_shape = {
        sh: sum(1 for s in chosen if sh in s.shapes) for sh in sorted(instances)
    }
    drawn_instances = sum(instances.get(sh, 0) for sh in per_shape if per_shape[sh])

    recycled = sorted(s.id for s in chosen if asked.get(s.id))
    collisions = sorted(
        f"{sid}::{r}" for sid, rs in assignment.items()
        for r in rs if r in asked.get(sid, set())
    )
    payload = {
        "seed": args.seed,
        "tier_quota": {**quota_by_tier, "D0": abstention_quota},
        # Honest freshness. `recycled_specs` have been asked before in ANOTHER
        # register — the question is new, the anchor and its gold are not — and
        # they exist because a tier can be exhausted: on 2026-09-12 every one of
        # D3's 73 specs was already spent, so a wholly unused D3 draw was not
        # available at any size.
        "excluded_banks": [str(p) for p in args.exclude_bank],
        "recycled_specs": recycled,
        # Pairs that could NOT be made fresh. Must be empty: a non-empty list
        # means a question in this set has been asked, word for word, before.
        "already_asked_pairs": collisions,
        "recycled_by_tier": {
            t: sum(1 for s in chosen if asked.get(s.id) and s.tier == t)
            for t in sorted({s.tier for s in chosen})
        },
        "specs": len(chosen),
        "questions": questions,
        "paraphrase_specs": sorted(s.id for s in paraphrase),
        "abstention_specs": sorted(s.id for s in abstention),
        "by_tier": {
            t: sum(1 for s in chosen if s.tier == t) for t in sorted({s.tier for s in chosen})
        },
        "by_source": {
            src: sum(1 for s in chosen if s.source == src)
            for src in sorted({s.source for s in chosen})
        },
        "by_width_band": {
            band: sum(1 for s in chosen if s.tier != "D0" and band_of(s.gold_width) == band)
            for _l, _h, band in WIDTH_BANDS
        },
        "by_direction": {
            "forward": sum(1 for s in chosen if s.steps and not s.steps[-1].reverse),
            "reverse": sum(1 for s in chosen if s.steps and s.steps[-1].reverse),
            "no_hop": sum(1 for s in chosen if not s.steps),
        },
        # The pair that makes a skewed bank quotable. `drawn` is how the bank is
        # weighted; `census_instances` is how the graph is actually shaped. Any
        # pooled figure must be reported alongside a reweighting of per-shape
        # scores to the second, or it is not comparable to anything.
        "reweighting": {
            "drawn": per_shape,
            "census_instances": instances,
            "note": "pooled accuracy over this bank is NOT a natural-distribution "
                    "estimate; reweight per-shape scores by census_instances",
        },
        "shapes_covered": sum(1 for v in per_shape.values() if v),
        "shapes_total": len(instances),
        "never_asked_covered": sum(1 for sh in never if per_shape.get(sh)),
        "never_asked_total": len(never),
        "instances_represented": drawn_instances,
        "spec_ids": [s.id for s in chosen],
        "registers": assignment,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=1) + "\n")

    print(f"bank draw -> {args.out}")
    print(f"  {payload['specs']} specs -> {payload['questions']} questions "
          f"({len(paraphrase)} rendered in all three registers)")
    print(f"  shapes {payload['shapes_covered']}/{payload['shapes_total']}; "
          f"never-asked {payload['never_asked_covered']}/{payload['never_asked_total']}")
    print(f"  by tier: {payload['by_tier']}")
    print(f"  by source: {payload['by_source']}")
    print(f"  by width band: {payload['by_width_band']}")
    print(f"  by direction: {payload['by_direction']}")


if __name__ == "__main__":
    main()
