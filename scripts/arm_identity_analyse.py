#!/usr/bin/env python3
"""Report EXP-2026-09-010 at two exclusion levels, without changing the run.

Protocol amendment A-1 requires the results to carry three things together, in
this order: the raw identity figure under the *pre-registered* exclusion list,
the key paths that actually differ, and the content-identity figure once every
clock-derived key found by the run is excluded.

This script computes all three by re-reading the captures on disk. It does not
re-run anything and does not modify ``arm_identity_check.py``'s ``VOLATILE``
tuple -- the pre-registered figure has to stay reproducible from the same code
that produced it.

    uv run python scripts/arm_identity_analyse.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.arm_identity_check import (  # noqa: E402
    ARMS, ROOT, SCORED_MARKERS, diff_paths, strip_volatile,
)

EXP = REPO / "docs/research/experiments/EXP-2026-09-010-model-free-arm-identity"
OUT = EXP / "data" / "identity-analysis.json"

#: Pre-registered, in PROTOCOL.md before any run.
PREREGISTERED = ("timing_ms",)

#: Every clock-derived key the run itself surfaced. ``wall_s`` was found by
#: amendment A-1 -- by the run failing, which is what the protocol asked for.
#: Anything added here must have been *observed* to move, never predicted.
DISCOVERED = ("timing_ms", "wall_s")


def strip_keys(obj, keys: tuple[str, ...]):
    if isinstance(obj, dict):
        return {k: strip_keys(v, keys) for k, v in obj.items() if k not in keys}
    if isinstance(obj, list):
        return [strip_keys(v, keys) for v in obj]
    return obj


def analyse(arm: str) -> dict:
    a_dir, b_dir = ROOT / "a" / arm / "answers", ROOT / "b" / arm / "answers"
    if not (a_dir.is_dir() and b_dir.is_dir()):
        return {"arm": arm, "status": "captures missing"}

    names = sorted({p.name for p in a_dir.glob("*.json")}
                   & {p.name for p in b_dir.glob("*.json")})
    pre_same = disc_same = 0
    paths_pre: dict[str, int] = {}
    paths_disc: dict[str, int] = {}

    for n in names:
        a = json.loads((a_dir / n).read_text())
        b = json.loads((b_dir / n).read_text())

        pa, pb = strip_keys(a, PREREGISTERED), strip_keys(b, PREREGISTERED)
        if pa == pb:
            pre_same += 1
        else:
            for p in diff_paths(pa, pb):
                paths_pre[p] = paths_pre.get(p, 0) + 1

        da, db = strip_keys(a, DISCOVERED), strip_keys(b, DISCOVERED)
        if da == db:
            disc_same += 1
        else:
            for p in diff_paths(da, db):
                paths_disc[p] = paths_disc.get(p, 0) + 1

    n = len(names)
    scored = sorted(p for p in paths_disc
                    if any(m in p.lower() for m in SCORED_MARKERS))
    return {
        "arm": arm,
        "compared": n,
        "preregistered_exclusions": list(PREREGISTERED),
        "identical_preregistered": pre_same,
        "identity_rate_preregistered": round(pre_same / n, 4) if n else None,
        "differing_paths_preregistered": dict(
            sorted(paths_pre.items(), key=lambda kv: -kv[1])[:25]),
        "clock_exclusions_after_discovery": list(DISCOVERED),
        "identical_content": disc_same,
        "identity_rate_content": round(disc_same / n, 4) if n else None,
        "differing_paths_content": dict(
            sorted(paths_disc.items(), key=lambda kv: -kv[1])[:25]),
        "paths_in_scored_fields": scored,
        "h3_holds": not scored,
        "verdict": (
            "content-identical" if disc_same == n
            else ("non-scored jitter beyond the clock" if not scored
                  else "DIFFERS IN A SCORED FIELD")
        ),
    }


def main() -> int:
    out = {"experiment": "EXP-2026-09-010", "arms": {}}
    for arm in ARMS:
        out["arms"][arm] = analyse(arm)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")

    print(f"{'arm':16} {'pre-reg':>12} {'content':>12}  verdict")
    print("-" * 72)
    for arm, r in out["arms"].items():
        if r.get("status"):
            print(f"{arm:16} {r['status']}")
            continue
        print(f"{arm:16} "
              f"{r['identical_preregistered']:>5}/{r['compared']:<6} "
              f"{r['identical_content']:>5}/{r['compared']:<6}  {r['verdict']}")
    print(f"\nwritten -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
