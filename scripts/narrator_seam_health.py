#!/usr/bin/env python3
"""Is the small model safe on the narrator seam? Three counts and a clock.

The narrator rewrites prose over claims that were already composed
deterministically and already verified, so a weak model there should produce
worse *writing* and not worse *facts*. This checks that it actually does, by
comparing an arm with the narrator on against the identical arm with it off.

Four things, each of which can fail independently:

* **Fallback rate**, counted over ANSWERS and never over files. The 2026-09-10
  audit divided by the file count of a directory that also held judgment
  sidecars and reported 0.04 where the truth was 0.43 (`EXP-2026-09-016` A-8).
  The denominator is the finding.
* **Claim identity.** Every claim must be byte-identical to the control's. The
  model is not allowed to add, drop or edit one; if it can, the arms are no
  longer comparable and the verifier's guarantees are not what they look like.
* **New unsupported verdicts.** The verifier runs unconditionally over both
  sides, so a claim that it accepts in the control and rejects here is the seam
  doing damage.
* **Wall clock per answer**, which is the whole point of asking whether a 2B
  model can do this job.

    uv run python scripts/narrator_seam_health.py --narrator <root/arm> --control <root/arm>
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

#: `EXP-2026-09-016`: the rate at which the shipped narrator was called healthy.
HEALTHY_FALLBACK_RATE = 0.14


def load(directory: Path) -> dict[str, dict]:
    """Case id -> artifact, excluding judgment sidecars."""
    out: dict[str, dict] = {}
    for path in sorted(directory.glob("*.json")):
        if ".judgment" in path.name or path.name == "manifest.json":
            continue
        artifact = json.loads(path.read_text())
        out[artifact["id"]] = artifact
    return out


def _claims(artifact: dict) -> list:
    return ((artifact.get("answer") or {}).get("claims")) or []


def _unsupported(artifact: dict) -> set[int]:
    return {i for i, c in enumerate(_claims(artifact))
            if (c or {}).get("verdict") == "unsupported"}


def _wall(artifact: dict) -> float | None:
    value = (artifact.get("run_meta") or {}).get("wall_s")
    return float(value) if value is not None else None


def health(narrator: dict[str, dict], control: dict[str, dict]) -> dict[str, Any]:
    fallbacks: dict[str, int] = {}
    for artifact in narrator.values():
        reason = (artifact.get("answer") or {}).get("fallback_reason")
        if reason:
            fallbacks[str(reason).split("(")[0].strip()] = (
                fallbacks.get(str(reason).split("(")[0].strip(), 0) + 1
            )
    total_fallbacks = sum(fallbacks.values())
    n = len(narrator)
    rate = round(total_fallbacks / n, 4) if n else 0.0

    shared = sorted(set(narrator) & set(control))
    changed = [
        case for case in shared
        if json.dumps(_claims(narrator[case]), sort_keys=True)
        != json.dumps(_claims(control[case]), sort_keys=True)
    ]
    new_unsupported = [
        case for case in shared
        if _unsupported(narrator[case]) - _unsupported(control[case])
    ]

    def clock(source: dict[str, dict]) -> dict[str, Any]:
        values = [w for w in (_wall(a) for a in source.values()) if w is not None]
        if not values:
            return {"n": 0, "mean_s": None, "median_s": None}
        return {
            "n": len(values),
            "mean_s": round(statistics.fmean(values), 3),
            "median_s": round(statistics.median(values), 3),
            "max_s": round(max(values), 3),
        }

    return {
        "answers": n,
        "fallbacks": total_fallbacks,
        "fallback_rate": rate,
        "fallback_reasons": fallbacks,
        "fallback_healthy": bool(n) and rate <= HEALTHY_FALLBACK_RATE,
        "claims_compared": len(shared),
        "claims_identical": len(shared) - len(changed),
        "claims_changed_case_ids": changed,
        "new_unsupported_case_ids": new_unsupported,
        "wall_clock": {"narrator": clock(narrator), "control": clock(control)},
        # Every gate at once, so a caller cannot read one and miss another.
        "passes": bool(n) and rate <= HEALTHY_FALLBACK_RATE
        and not changed and not new_unsupported,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--narrator", required=True, help="path to the narrator arm's answers/")
    parser.add_argument("--control", required=True, help="path to the control arm's answers/")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    result = health(load(Path(args.narrator)), load(Path(args.control)))
    result["narrator_path"] = args.narrator
    result["control_path"] = args.control

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
        print(f"written: {args.out}")
    print(f"answers            {result['answers']}")
    print(f"fallback rate      {result['fallback_rate']} "
          f"(healthy <= {HEALTHY_FALLBACK_RATE}: {result['fallback_healthy']})")
    print(f"claims identical   {result['claims_identical']}/{result['claims_compared']}")
    print(f"new unsupported    {len(result['new_unsupported_case_ids'])}")
    print(f"wall/answer        narrator {result['wall_clock']['narrator']['mean_s']}s  "
          f"control {result['wall_clock']['control']['mean_s']}s")
    print(f"PASSES             {result['passes']}")
    return 0 if result["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
