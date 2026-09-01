#!/usr/bin/env python3
"""Judged effect of a builder change, against a null control built from its own data.

Two conditions differ only in the code that produced the answers. Neither answer
path contains a language model, so both are byte-reproducible and the only
variable is the builder.

**The design turns on a control that costs nothing.** A builder change does not
touch every answer. The ones it leaves *byte-identical* must score identically up
to grader noise — so their measured old-versus-new difference **is** the noise
floor, taken in the same sessions, on the same instrument, on this exact
comparison. Importing a floor from another experiment would be weaker: it would
come from different cells and a different question mix.

Every conclusion is therefore the changed-set difference **against that floor**. A
movement in the changed set no larger than the movement in the unchanged set is
not evidence of anything, and this script prints them side by side so the
comparison cannot be skipped.

Usage:

    uv run python scripts/builder_change_judged.py \
        --old docs/evaluation/experiments/bank20260819 \
        --new docs/evaluation/experiments/builderiso-b19-newbuilder \
        --arm deterministic --suffixes .bld1 .bld2 .bld3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, pstdev

#: Keys that move on every run and mean nothing. Same list the recorded-answer
#: regression uses, so "changed" means the same thing here as it does there.
CLOCK = {
    "timestamp", "elapsed_s", "wall_s", "timing_ms", "run_meta",
    "generated_at", "duration_s", "started_at", "finished_at",
}


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in CLOCK}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


def partition(old: Path, new: Path, arm: str) -> tuple[list[str], list[str]]:
    """Split case ids into (unchanged, changed) by comparing the answers."""
    od, nd = old / arm / "answers", new / arm / "answers"
    unchanged, changed = [], []
    for path in sorted(od.glob("*.json")):
        if ".judgment" in path.name:
            continue
        case = path.stem
        other = nd / f"{case}.json"
        if not other.is_file():
            continue
        a, b = _strip(json.loads(path.read_text())), _strip(json.loads(other.read_text()))
        (unchanged if a == b else changed).append(case)
    return unchanged, changed


def _scores(root: Path, arm: str, suffix: str) -> dict[str, float]:
    out = {}
    for path in (root / arm / "answers").glob(f"*.judgment{suffix}.json"):
        if path.name.count(".judgment") != 1:
            continue
        try:
            out[path.name.split(".judgment")[0]] = float(json.loads(path.read_text())["correctness"])
        except (ValueError, OSError, KeyError):
            continue
    return out


def analyse(old: Path, new: Path, arm: str, suffixes: list[str]) -> dict:
    unchanged, changed = partition(old, new, arm)
    per_session = []
    for suffix in suffixes:
        o, n = _scores(old, arm, suffix), _scores(new, arm, suffix)
        row: dict = {"suffix": suffix}
        for label, cases in (("unchanged", unchanged), ("changed", changed)):
            # Only cases graded on BOTH sides in THIS session. A case graded on
            # one side only would compare a score against nothing.
            paired = [c for c in cases if c in o and c in n]
            deltas = [n[c] - o[c] for c in paired]
            row[label] = {
                "n": len(paired),
                "old_mean": round(mean(o[c] for c in paired), 4) if paired else None,
                "new_mean": round(mean(n[c] for c in paired), 4) if paired else None,
                "signed": round(mean(deltas), 4) if paired else None,
                "abs": round(mean(abs(d) for d in deltas), 4) if paired else None,
                "improved": sum(1 for d in deltas if d > 0),
                "regressed": sum(1 for d in deltas if d < 0),
                "identical": sum(1 for d in deltas if d == 0),
                "dropped": len(cases) - len(paired),
            }
        per_session.append(row)

    def pooled(label: str, key: str) -> float | None:
        vals = [r[label][key] for r in per_session if r[label][key] is not None]
        return round(mean(vals), 4) if vals else None

    def spread(label: str, key: str) -> float | None:
        vals = [r[label][key] for r in per_session if r[label][key] is not None]
        return round(pstdev(vals), 4) if len(vals) > 1 else None

    # Difference-in-differences, per session, then summarised.
    #
    # The null control is not only a noise floor: it is an estimate of whatever
    # bias applies equally to both conditions in that session. A reversed-order
    # session proved one exists -- grading order. The condition graded SECOND
    # scores lower whichever it is, by about 0.01, so the control's signed
    # difference flips with the order while the builder does not change. The
    # per-session difference-in-differences subtracts that out; a single order
    # alone cannot.
    did = []
    for row in per_session:
        c, u = row["changed"]["signed"], row["unchanged"]["signed"]
        if c is not None and u is not None:
            row["did"] = round(c - u, 4)
            did.append(row["did"])
    floor = pooled("unchanged", "abs")
    effect = pooled("changed", "signed")
    return {
        "old": str(old), "new": str(new), "arm": arm, "suffixes": suffixes,
        "n_unchanged": len(unchanged), "n_changed": len(changed),
        "changed_cases": changed,
        "per_session": per_session,
        "pooled": {
            "unchanged_signed": pooled("unchanged", "signed"),
            "unchanged_abs": floor,
            "changed_signed": effect,
            "changed_abs": pooled("changed", "abs"),
            "unchanged_signed_sd": spread("unchanged", "signed"),
            "changed_signed_sd": spread("changed", "signed"),
        },
        # The whole point, computed rather than left to the reader.
        "difference_in_differences": {
            "per_session": did,
            "mean": round(mean(did), 4) if did else None,
            "sd": round(pstdev(did), 4) if len(did) > 1 else None,
            "sign_stable": (all(d > 0 for d in did) or all(d < 0 for d in did)) if did else None,
        },
        "effect_exceeds_null_floor": (
            None if floor is None or effect is None else abs(effect) > floor
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--arm", default="deterministic")
    parser.add_argument("--suffixes", nargs="+", required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    r = analyse(args.old, args.new, args.arm, args.suffixes)
    if args.out:
        args.out.write_text(json.dumps(r, indent=1) + "\n")

    print(f"{args.old.name}  ->  {args.new.name}   ({args.arm})")
    print(f"  {r['n_unchanged']} byte-identical answers (null control), {r['n_changed']} changed\n")
    print(f"  {'session':<9} {'set':<10} {'n':>3} {'old':>8} {'new':>8} {'signed':>8} {'|d|':>7}  imp/reg/same")
    for row in r["per_session"]:
        for label in ("unchanged", "changed"):
            c = row[label]
            if not c["n"]:
                continue
            print(f"  {row['suffix']:<9} {label:<10} {c['n']:>3} {c['old_mean']:>8.4f} {c['new_mean']:>8.4f} "
                  f"{c['signed']:>+8.4f} {c['abs']:>7.4f}  {c['improved']}/{c['regressed']}/{c['identical']}"
                  + (f"   [{c['dropped']} dropped]" if c["dropped"] else ""))
    p = r["pooled"]
    if p["unchanged_abs"] is None or p["changed_signed"] is None:
        print("\n  not enough graded cases yet on one or both sides — no verdict")
        return 0
    print(f"\n  NULL FLOOR   unchanged answers: signed {p['unchanged_signed']:+.4f}, |d| {p['unchanged_abs']:.4f}")
    print(f"  EFFECT       changed answers:   signed {p['changed_signed']:+.4f}, |d| {p['changed_abs']:.4f}")
    d = r["difference_in_differences"]
    if d["mean"] is not None:
        print(f"  DiD          changed minus null, per session: {d['per_session']}")
        print(f"               mean {d['mean']:+.4f}"
              + (f", sd {d['sd']:.4f}" if d["sd"] is not None else "")
              + f", sign stable: {d['sign_stable']}")
    verdict = ("EXCEEDS the null floor — a real judged difference"
               if r["effect_exceeds_null_floor"]
               else "INSIDE the null floor — invisible to the judge on this set")
    print(f"  VERDICT      {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
