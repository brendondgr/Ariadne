#!/usr/bin/env python3
"""Does direction matter? Paired, so the answer is not confounded by shape.

The project holds two contradictory readings. EXP-2026-09-001 A-4 compared the
*same* shape asked from each end and found the forward side answered and the
reverse side not. A-5's aggregate over 511 questions says the opposite —
reverse 0.5165, forward 0.4302.

They are not measuring the same thing. The aggregate compares *different*
shapes that happen to be forward or reverse, so it is confounded by which
shapes fall on which side: if the reverse questions happen to sit on easier
edges, reverse wins for a reason that has nothing to do with direction.

This pairs on `(shape, anchor)`. Only a spec that has a genuine opposite in the
bank enters the contrast, and each pair contributes one signed difference. That
is the design that can answer the question; the aggregate is not.

Sign convention: **positive means forward scored higher**. Fixed here so nobody
has to infer it from a table later.

    uv run python scripts/direction_contrast.py
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

BANK = Path("docs/evaluation/composition/bank/bank.json")
SCORE = Path("docs/evaluation/composition/bank/score.json")


def _usable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in rows
        if r.get("recall") is not None
        and r.get("d_tier") not in (None, "D0")
        and len(r.get("shapes") or []) == 1  # multi-hop has no single direction
    ]


def contrast(rows: list[dict[str, Any]], *, by_anchor: bool = False) -> dict[str, Any]:
    """Forward vs reverse, controlled for shape.

    `by_anchor=False` (the default) pairs on the **shape**: within one edge
    type, the mean of its forward questions against the mean of its reverse
    questions. That removes the confound A-5 actually has — its aggregate mixed
    easy and hard *shapes* across the two directions — while keeping enough
    pairs to say anything.

    `by_anchor=True` is the stricter design, pairing on `(shape, anchor)` so the
    two sides are literally the same entity asked both ways. It is reported
    alongside because it is the cleaner comparison, but this bank yields only a
    couple of such pairs: the draw sampled directions independently and never
    set out to ask one entity from both ends. That is a finding about the draw,
    and it is recorded rather than worked around.
    """
    usable = _usable(rows)
    groups: dict[tuple[str, str] | str, dict[bool, list[float]]] = defaultdict(
        lambda: {True: [], False: []}
    )
    for row in usable:
        shape = row["shapes"][0]
        key = (shape, row.get("anchor_key") or "?") if by_anchor else shape
        groups[key][bool(row["reverse"])].append(row["recall"])

    deltas: list[dict[str, Any]] = []
    paired_rows = 0
    for key, sides in sorted(groups.items(), key=lambda kv: str(kv[0])):
        if not sides[True] or not sides[False]:
            continue
        paired_rows += len(sides[True]) + len(sides[False])
        forward = statistics.fmean(sides[False])
        reverse = statistics.fmean(sides[True])
        deltas.append(
            {
                "key": key if isinstance(key, str) else list(key),
                "shape": key if isinstance(key, str) else key[0],
                "n_forward": len(sides[False]),
                "n_reverse": len(sides[True]),
                "forward": round(forward, 4),
                "reverse": round(reverse, 4),
                "delta": round(forward - reverse, 4),
            }
        )

    values = [d["delta"] for d in deltas]
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "paired_on": "shape+anchor" if by_anchor else "shape",
        "pairs": len(deltas),
        "questions_in_pairs": paired_rows,
        "questions_excluded": len(usable) - paired_rows,
        "mean_delta": round(statistics.fmean(values), 4) if values else None,
        "sd": round(sd, 4),
        "se": round(sd / math.sqrt(len(values)), 4) if values else None,
        "forward_higher": sum(1 for v in values if v > 0),
        "reverse_higher": sum(1 for v in values if v < 0),
        "tied": sum(1 for v in values if v == 0),
        "sign_convention": "positive means the forward direction scored higher",
        "pairs_detail": deltas,
    }


def unpaired_aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The confounded comparison, reported so the difference is visible."""
    usable = _usable(rows)
    forward = [r["recall"] for r in usable if not r["reverse"]]
    reverse = [r["recall"] for r in usable if r["reverse"]]
    return {
        "forward": round(statistics.fmean(forward), 4) if forward else None,
        "reverse": round(statistics.fmean(reverse), 4) if reverse else None,
        "n_forward": len(forward),
        "n_reverse": len(reverse),
        "delta": round(statistics.fmean(forward) - statistics.fmean(reverse), 4)
        if forward and reverse
        else None,
        "caveat": "confounded by shape composition; the paired contrast is the "
                  "one that answers the question",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", type=Path, default=SCORE)
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--out", type=Path,
                        default=Path("docs/evaluation/composition/bank/direction.json"))
    args = parser.parse_args()

    rows = json.loads(args.score.read_text())["rows"]
    bank = {q["id"]: q for q in json.loads(args.bank.read_text())["questions"]}
    for row in rows:
        entry = bank.get(row["id"])
        if entry:
            row["anchor_key"] = entry["assertions"]["must_include_ids"][0]

    by_shape = contrast(rows)
    by_anchor = contrast(rows, by_anchor=True)
    aggregate = unpaired_aggregate(rows)
    result = {
        "primary": by_shape,
        "strict": by_anchor,
        "confounded_aggregate": aggregate,
    }
    args.out.write_text(json.dumps(result, indent=1) + "\n")

    print(f"direction contrast -> {args.out}")
    print(f"\n  confounded aggregate (what A-5 reported):")
    print(f"    forward {aggregate['forward']} (n={aggregate['n_forward']}), "
          f"reverse {aggregate['reverse']} (n={aggregate['n_reverse']}), "
          f"delta {aggregate['delta']:+.4f}")
    for label, res in (("paired on shape", by_shape), ("paired on shape+anchor", by_anchor)):
        print(f"\n  {label}: {res['pairs']} pairs covering "
              f"{res['questions_in_pairs']} questions "
              f"({res['questions_excluded']} excluded — no opposite in the bank)")
        if res["mean_delta"] is None:
            print("    no pairs")
            continue
        print(f"    mean delta {res['mean_delta']:+.4f} ± {res['se']:.4f} (se); "
              f"{res['sign_convention']}")
        print(f"    forward higher in {res['forward_higher']}, "
              f"reverse higher in {res['reverse_higher']}, tied {res['tied']}")
    print("\n  per shape (paired on shape):")
    for entry in sorted(by_shape["pairs_detail"], key=lambda d: d["delta"]):
        print(f"    {entry['delta']:+.3f}  (fwd n={entry['n_forward']}, "
              f"rev n={entry['n_reverse']})  {entry['shape']}")


if __name__ == "__main__":
    main()
