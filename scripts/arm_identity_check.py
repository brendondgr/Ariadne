#!/usr/bin/env python3
"""Do the model-free arms actually repeat? Run each twice, compare exactly.

Protocol: ``docs/research/experiments/EXP-2026-09-010-model-free-arm-identity/PROTOCOL.md``.

The paper runs ``deterministic`` and ``generic`` once each and justifies it by
asserting they are model-free on the query path. That assumption has never been
measured, and it is the reason those single draws are considered publishable.

    uv run python scripts/arm_identity_check.py --dry-run
    uv run python scripts/arm_identity_check.py --workers 32
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

EXP = REPO / "docs/research/experiments/EXP-2026-09-010-model-free-arm-identity"
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"
ROOT = REPO / "docs/evaluation/experiments/arm-identity-2026-09-06"
LOGS = REPO / "logs/arm-identity-2026-09-06"
STATE = EXP / "data" / "run-state.json"

N_EXPECT = 284
BANK_SHA = "a4ca6702029cae77"
ARMS = ("deterministic", "generic")

#: The only key path excluded from comparison. Found by walking all 100 key
#: paths of a real artifact and testing for wall-clock-derived names -- not
#: guessed. If a second volatile key exists, this run must DISCOVER it by
#: failing. Do not extend this tuple to make a run pass.
VOLATILE = ("timing_ms",)


# ---------------------------------------------------------------- guards
def assert_stores() -> dict:
    """Delegate to the holdout run's guard; it carries the right config."""
    from scripts.holdout_run import assert_stores as _assert

    return _assert()


def preflight() -> dict:
    bank = json.loads(BANK.read_text())
    n = len(bank["questions"])
    if n != N_EXPECT:
        raise RuntimeError(f"bank has {n} questions, expected {N_EXPECT}")
    sha = hashlib.sha256(BANK.read_bytes()).hexdigest()
    if not sha.startswith(BANK_SHA):
        raise RuntimeError(f"bank sha {sha[:16]} != pinned {BANK_SHA}")
    return {"bank_questions": n, "bank_sha256": sha, "stores": assert_stores()}


# ---------------------------------------------------------------- compare
def strip_volatile(obj):
    """Remove exactly the volatile keys, recursively, preserving all else."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def diff_paths(a, b, prefix: str = "") -> list[str]:
    """Every key path at which two artifacts disagree."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{prefix}{k}<missing>")
            else:
                out.extend(diff_paths(a[k], b[k], f"{prefix}{k}."))
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{prefix}[]<len {len(a)}!={len(b)}>"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out.extend(diff_paths(x, y, f"{prefix}[]."))
        return out
    return [] if a == b else [prefix.rstrip(".")]


#: Fields the scorer actually reads. H3 asks whether any difference lands here.
SCORED_MARKERS = ("answer", "claims", "records", "evidence", "ex_gold", "citation")


def is_scored(path: str) -> bool:
    return any(m in path.lower() for m in SCORED_MARKERS)


def compare(arm: str, root_a: Path, root_b: Path) -> dict:
    ans_a = {p.name: p for p in (root_a / arm / "answers").glob("*.json")}
    ans_b = {p.name: p for p in (root_b / arm / "answers").glob("*.json")}
    common = sorted(set(ans_a) & set(ans_b))

    identical, differing, path_counts = 0, [], {}
    for name in common:
        a = strip_volatile(json.loads(ans_a[name].read_text()))
        b = strip_volatile(json.loads(ans_b[name].read_text()))
        if a == b:
            identical += 1
            continue
        paths = diff_paths(a, b)
        differing.append({"answer": name, "paths": paths[:20]})
        for p in paths:
            path_counts[p] = path_counts.get(p, 0) + 1

    scored_hits = sorted(p for p in path_counts if is_scored(p))
    return {
        "arm": arm,
        "run_a_answers": len(ans_a),
        "run_b_answers": len(ans_b),
        "compared": len(common),
        "only_in_a": sorted(set(ans_a) - set(ans_b))[:10],
        "only_in_b": sorted(set(ans_b) - set(ans_a))[:10],
        "identical": identical,
        "differing": len(differing),
        "identity_rate": round(identical / len(common), 4) if common else None,
        "differing_paths": dict(sorted(path_counts.items(),
                                       key=lambda kv: -kv[1])[:25]),
        "paths_in_scored_fields": scored_hits,
        "h3_holds": not scored_hits,
        "examples": differing[:5],
    }


# ---------------------------------------------------------------- run
def run_arm(arm: str, tag: str, workers: int) -> dict:
    root = ROOT / tag
    root.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "ORCH_MAX_HOPS": "5"}
    cmd = [
        "uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
        "--arm", arm, "--bank", str(BANK), "--root", str(root),
        "--workers", str(workers),
    ]
    t0 = time.time()
    with (LOGS / f"{arm}-{tag}.log").open("w") as fh:
        rc = subprocess.call(cmd, cwd=REPO, env=env, stdout=fh,
                             stderr=subprocess.STDOUT)
    written = len(list((root / arm / "answers").glob("*.json")))
    return {
        "arm": arm, "tag": tag, "rc": rc,
        "elapsed_s": round(time.time() - t0, 1),
        "answers_written": written,
        "status": "done" if (rc == 0 and written >= N_EXPECT) else "not_run",
        "finished": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("== pre-flight ==", flush=True)
    checks = preflight()
    print(json.dumps(checks, indent=1), flush=True)
    if args.dry_run:
        print("dry run: guards pass, nothing launched")
        return 0

    STATE.parent.mkdir(parents=True, exist_ok=True)
    st = {"preflight": checks, "runs": {}, "comparisons": {}}

    for arm in ARMS:
        # Back to back, no reload between, so a store change cannot be
        # mistaken for arm non-determinism.
        for tag in ("a", "b"):
            key = f"{arm}-{tag}"
            print(f"== {key} ==", flush=True)
            st["runs"][key] = run_arm(arm, tag, args.workers)
            STATE.write_text(json.dumps(st, indent=1) + "\n")
            print(json.dumps(st["runs"][key], indent=1), flush=True)

        st["comparisons"][arm] = compare(arm, ROOT / "a", ROOT / "b")
        STATE.write_text(json.dumps(st, indent=1) + "\n")
        c = st["comparisons"][arm]
        print(f"\n{arm}: {c['identical']}/{c['compared']} identical "
              f"(rate {c['identity_rate']}), H3 holds: {c['h3_holds']}", flush=True)
        if c["differing"]:
            print("  differing paths:", json.dumps(c["differing_paths"], indent=1),
                  flush=True)

    print("\n== summary ==", flush=True)
    for arm, c in st["comparisons"].items():
        verdict = ("BYTE-IDENTICAL" if c["identity_rate"] == 1.0
                   else ("non-scored jitter" if c["h3_holds"]
                         else "DIFFERS IN A SCORED FIELD"))
        print(f"  {arm:14} {c['identical']}/{c['compared']}  {verdict}", flush=True)
    print("identity check complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
