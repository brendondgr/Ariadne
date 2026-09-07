#!/usr/bin/env python3
"""Three seeded runs of the query-writing arm, then grade under both families.

Protocol: ``docs/research/experiments/EXP-2026-09-009-llm-query-seeded-repeats/PROTOCOL.md``.

Everything before the first request is a guard. This project has already driven
288 cases into a dead endpoint that a healthy-looking relay was still listing,
producing ~1,968 HTTP 502s, so a listed model is never taken as a live one.

    uv run python scripts/seeded_repeats.py --dry-run
    uv run python scripts/seeded_repeats.py --workers 32
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

EXP = REPO / "docs/research/experiments/EXP-2026-09-009-llm-query-seeded-repeats"
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"
ROOT = REPO / "docs/evaluation/experiments/seeded-repeats-2026-09-06"
#: EXP-2026-09-009 ran this with the default. Passing --arm changes the
#: output root so a second arm cannot land on top of a recorded run.
DEFAULT_ARM = "llm_query"

#: Which experiment owns each arm's seeded repeats. Writing a generic run
#: into EXP-2026-09-009 would silently overwrite a recorded result.
ARM_EXPERIMENT = {
    "llm_query": EXP,
    "generic": REPO / "docs/research/experiments/EXP-2026-09-011-generic-seeded-repeats",
}
LOGS = REPO / "logs/seeded-repeats-2026-09-06"
STATE = EXP / "data" / "run-state.json"

N_EXPECT = 284
BANK_SHA = "a4ca6702029cae77"          # 16-char prefix; full value recorded at run
SEEDS = (1729, 20260906, 424242)        # pre-registered, chosen before any run
BASE = "http://localhost:9090/v1"

# served_model strings the record contains. A pass that reports anything else is
# discarded rather than reconciled -- the endpoint briefly reported "gemma4-31B"
# for "gemma4-31B-mtp" during a startup window on 2026-09-06.
GRADERS = {
    "qwen": {"alias": "default-model", "expect": "qwen38-27B-v2"},
    "gemma31": {"alias": "default-model-2", "expect": "gemma4-31B-mtp"},
}
GEN_MODEL = {"alias": "default-model", "expect": "qwen38-27B-v2"}

NEO4J_EXPECT = {"nodes": 4369, "edges": 27669}
GREMLIN_EXPECT = {"vertices": 6374, "edges": 8582}


# ---------------------------------------------------------------- guards
def probe(alias: str, expect: str) -> str:
    """Return the served_model, or raise. A listed model is not a live one."""
    import urllib.request

    body = json.dumps({
        "model": alias,
        "messages": [{"role": "user", "content": "Reply with only the word OK."}],
        "max_tokens": 2048,       # a reasoning model truncates to empty below ~2048
    }).encode()
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as fh:
        payload = json.load(fh)
    if "error" in payload:
        raise RuntimeError(f"{alias}: {payload['error']}")
    served = payload.get("model")
    if served != expect:
        raise RuntimeError(
            f"{alias} serves {served!r}, record contains {expect!r} — "
            "refusing to run. Reconciling this silently is how an alias "
            "comes to stand for three different models."
        )
    return served


def assert_stores() -> dict:
    """Reuse the holdout run's store guard rather than restating its config.

    It carries the right Gremlin default (port 6455, env ``GREMLIN_URI``) and
    the same pinned counts. Duplicating those constants here is how the two
    drift apart.
    """
    from scripts.holdout_run import assert_stores as _assert

    return _assert()


def preflight() -> dict:
    bank = json.loads(BANK.read_text())
    n = len(bank["questions"])
    if n != N_EXPECT:
        raise RuntimeError(f"bank has {n} questions, expected {N_EXPECT}")
    full_sha = hashlib.sha256(BANK.read_bytes()).hexdigest()
    if not full_sha.startswith(BANK_SHA):
        raise RuntimeError(f"bank sha {full_sha[:16]} != pinned {BANK_SHA}")

    checks = {
        "bank_questions": n,
        "bank_sha256": full_sha,
        "stores": assert_stores(),
        "served": {},
    }
    checks["served"]["generation"] = probe(GEN_MODEL["alias"], GEN_MODEL["expect"])
    for key, cfg in GRADERS.items():
        checks["served"][key] = probe(cfg["alias"], cfg["expect"])
    return checks


# ---------------------------------------------------------------- state
def read_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"runs": {}, "judged": {}}


def write_state(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1) + "\n")


# ---------------------------------------------------------------- run
def run_seed(seed: int, workers: int, arm: str = DEFAULT_ARM,
             root_base: Path | None = None) -> dict:
    root = (root_base or ROOT) / f"seed-{seed}"
    root.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / f"run-seed-{seed}.log"

    env = {
        **os.environ,
        "LLM_SEED": str(seed),
        "ORCH_MAX_HOPS": "5",          # local .env pins 1, which starves the arm
        "LLM_BASE_URL": BASE,
    }
    cmd = [
        "uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
        "--arm", arm, "--bank", str(BANK), "--root", str(root),
        "--workers", str(workers),
        "--llm-model", GEN_MODEL["alias"],
        "--llm-max-tokens", "32768",
    ]
    t0 = time.time()
    with log.open("w") as fh:
        rc = subprocess.call(cmd, cwd=REPO, env=env, stdout=fh, stderr=subprocess.STDOUT)
    written = len(list(root.rglob("*.json")))
    return {
        "seed": seed,
        "arm": arm,
        "rc": rc,
        "elapsed_s": round(time.time() - t0, 1),
        "answers_written": written,
        # a partially answered run is not a draw
        "status": "done" if (rc == 0 and written >= N_EXPECT) else "not_run",
        "root": str(root),
        "finished": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--arm", default=DEFAULT_ARM,
                    choices=["llm_query", "generic", "deterministic"])
    ap.add_argument("--root", default=None,
                    help="output root; defaults to the arm's own directory")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("== pre-flight ==", flush=True)
    checks = preflight()
    print(json.dumps(checks, indent=1), flush=True)
    if args.dry_run:
        print("dry run: guards pass, nothing launched")
        return 0

    root_base = Path(args.root) if args.root else (
        ROOT if args.arm == DEFAULT_ARM else ROOT.with_name(
            f"seeded-repeats-{args.arm}-2026-09-06"))
    # A non-default arm must not write into EXP-2026-09-009's data dir.
    global STATE
    if args.arm != DEFAULT_ARM:
        # Each arm writes into its OWN experiment's data dir.
        STATE = ARM_EXPERIMENT[args.arm] / "data" / "run-state.json"
    st = read_state()
    st["arm"] = args.arm
    st["root"] = str(root_base)
    st["preflight"] = checks
    write_state(st)

    for seed in SEEDS:
        key = str(seed)
        if st["runs"].get(key, {}).get("status") == "done":
            print(f"seed {seed}: already done, skipping", flush=True)
            continue
        print(f"== seed {seed} ==", flush=True)
        st["runs"][key] = run_seed(seed, args.workers, args.arm, root_base)
        write_state(st)
        print(json.dumps(st["runs"][key], indent=1), flush=True)

    done = sum(1 for v in st["runs"].values() if v.get("status") == "done")
    print(f"\ngeneration complete: {done}/{len(SEEDS)} runs", flush=True)
    return 0 if done == len(SEEDS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
