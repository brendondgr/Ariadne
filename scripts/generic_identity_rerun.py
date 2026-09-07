#!/usr/bin/env python3
"""Repeat EXP-2026-09-010 for ``generic`` alone, with the narrator guarded.

Protocol amendment A-2: the first attempt was invalid because the LLM narrator
at ``:4000`` timed out on 60 of 284 answers in run B, and nothing noticed. The
harness returned rc 0 and a full set of well-formed, silently degraded answers.

Three guards exist here that did not exist there:

1. **The narrator endpoint is probed in pre-flight.** The first attempt asserted
   three aliases on ``:9090`` and never touched the endpoint the arm actually
   narrates through.
2. **``fallback_reason`` is read, and classified.** A *transient* failure
   (timeout, refused connection) differs between runs and corrupts the
   comparison, so the capture is discarded. A *deterministic* one -- a
   context-length overflow at a fixed prompt is arithmetic, not weather --
   appears identically in both captures and is kept. The first version of this
   guard did not draw that line and would have failed all three attempts on one
   question that is over the context limit by a single token.
3. **A corrupted capture is retried**, up to ``--attempts`` times, and every
   attempt is recorded. A run that never produces a clean capture is ``not_run``.

    uv run python scripts/generic_identity_rerun.py --dry-run
    uv run python scripts/generic_identity_rerun.py
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from scripts.arm_identity_check import (  # noqa: E402
    N_EXPECT, SCORED_MARKERS, assert_stores, diff_paths, preflight,
)

EXP = REPO / "docs/research/experiments/EXP-2026-09-010-model-free-arm-identity"
BANK = REPO / "docs/evaluation/composition/bank/bank-dev.json"
ROOT = REPO / "docs/evaluation/experiments/arm-identity-rerun-2026-09-06"
LOGS = REPO / "logs/arm-identity-rerun-2026-09-06"
STATE = EXP / "data" / "generic-rerun-state.json"
ARM = "generic"

#: The narrator is pinned to the route that is verified healthy rather than to
#: ``.env``'s ``:4000/skynet``, which is the route that failed. The operator has
#: confirmed the two are the same backend, and ``utils/synthesis/config.py``
#: already carries :9090/default-model as its in-code default. This is a
#: deliberate deviation from the recorded runs' route and is recorded as one:
#: an identity check measures whether the arm varies, not a published figure.
NARRATOR = {"base_url": "http://localhost:9090/v1",
            "model": "default-model", "expect": "qwen38-27B-v2"}

#: Both clock keys: the pre-registered one and the one amendment A-1 found by
#: failing. Nothing enters this tuple that was not OBSERVED to move.
CLOCK = ("timing_ms", "wall_s")


def probe(base_url: str, model: str, expect: str) -> str:
    import urllib.request

    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with only the word OK."}],
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(f"{base_url}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as fh:
        payload = json.load(fh)
    if "error" in payload:
        raise RuntimeError(f"{base_url} {model}: {payload['error']}")
    served = payload.get("model")
    if served != expect:
        raise RuntimeError(f"{model} serves {served!r}, expected {expect!r}")
    return served


def strip_clock(obj):
    if isinstance(obj, dict):
        return {k: strip_clock(v) for k, v in obj.items() if k not in CLOCK}
    if isinstance(obj, list):
        return [strip_clock(v) for v in obj]
    return obj


#: Failures that differ between runs and therefore CORRUPT an identity
#: comparison. A capture containing any of these is discarded and retried.
TRANSIENT = ("Read timed out", "ConnectError", "Connection refused",
             "HTTPConnectionPool", "Max retries")

#: How many transient/unknown failures a capture may carry and still be used.
#: Those answers are EXCLUDED from the comparison rather than the whole capture
#: being thrown away. Above this the capture is genuinely degraded (A-2 saw 60)
#: and is discarded and retried.
MAX_CORRUPT = 14          # 5% of 284


#: Failures that are a reproducible property of the question and the model, and
#: so appear IDENTICALLY in both captures. A context-length overflow at a fixed
#: prompt is arithmetic, not weather. Discarding captures for these would mean
#: never obtaining one: observed 2026-09-06, one question at 67,617 input +
#: 16,384 output against an 84,000 limit -- over by a single token, every time.
#: They are tolerated here and must MATCH across captures; if one appears in
#: only one capture, the comparison catches it as a difference, which is
#: exactly right.
DETERMINISTIC = ("maximum context length",)


def classify(reason: str) -> str:
    if any(t in reason for t in TRANSIENT):
        return "transient"
    if any(d in reason for d in DETERMINISTIC):
        return "deterministic"
    return "unknown"


def degraded(root: Path) -> dict:
    """A capture corrupted by TRANSIENT failure. Deterministic ones are kept."""
    d = root / ARM / "answers"
    files = sorted(d.glob("*.json"))
    reasons, kinds = {}, {"transient": 0, "deterministic": 0, "unknown": 0}
    for p in files:
        try:
            r = (json.loads(p.read_text()).get("answer") or {}).get("fallback_reason")
        except Exception:
            r = "<unparseable artifact>"
        if r:
            reasons[str(r)[:70]] = reasons.get(str(r)[:70], 0) + 1
            kinds[classify(str(r))] += 1
    # "unknown" counts as corrupting: an unclassified failure is not something
    # to assume is reproducible.
    blocking = kinds["transient"] + kinds["unknown"]
    # A capture is USABLE if corruption is rare enough to exclude case-by-case.
    # Demanding zero was wrong: at the observed ~0.7% per-answer transient rate,
    # P(a capture has none) is 0.13, so requiring two perfect captures inside
    # three attempts each succeeds about 12% of the time. The comparison does
    # not need perfect captures -- it needs to know WHICH answers to exclude.
    return {"answers": len(files), "fallback_non_null": sum(kinds.values()),
            "by_kind": kinds, "reasons": reasons,
            "corrupt_rate": round(blocking / max(len(files), 1), 4),
            "clean": blocking == 0 and len(files) >= N_EXPECT,
            "usable": blocking <= MAX_CORRUPT and len(files) >= N_EXPECT}


def run_once(tag: str, attempt: int, workers: int) -> dict:
    root = ROOT / f"{tag}-try{attempt}"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "ORCH_MAX_HOPS": "5",
        "SYNTHESIS_LLM_BASE_URL": NARRATOR["base_url"],
        "SYNTHESIS_LLM_MODEL": NARRATOR["model"],
        # The failures were read timeouts at the default 120 s. Doubling it
        # removes the cheapest cause without changing what the arm computes.
        "SYNTHESIS_LLM_TIMEOUT_S": "600.0",
    }
    cmd = ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
           "--arm", ARM, "--bank", str(BANK), "--root", str(root),
           "--workers", str(workers), "--llm-model", NARRATOR["model"]]
    t0 = time.time()
    with (LOGS / f"{tag}-try{attempt}.log").open("w") as fh:
        rc = subprocess.call(cmd, cwd=REPO, env=env, stdout=fh,
                             stderr=subprocess.STDOUT)
    health = degraded(root)
    return {"tag": tag, "attempt": attempt, "rc": rc, "root": str(root),
            "elapsed_s": round(time.time() - t0, 1), **health,
            "finished": datetime.now().isoformat(timespec="seconds")}


def capture(tag: str, attempts: int, workers: int, st: dict) -> Path | None:
    for i in range(1, attempts + 1):
        print(f"-- {tag}, attempt {i}/{attempts} --", flush=True)
        r = run_once(tag, i, workers)
        st.setdefault("attempts", []).append(r)
        STATE.write_text(json.dumps(st, indent=1) + "\n")
        print(f"   answers {r['answers']}, fallback_non_null "
              f"{r['fallback_non_null']} {r['by_kind']}, "
              f"clean={r['clean']}", flush=True)
        if r["clean"]:
            return Path(r["root"])
        if r["usable"]:
            print(f"   usable with exclusions: {r['by_kind']['transient']} "
                  f"transient + {r['by_kind']['unknown']} unknown answers will be "
                  f"dropped from the comparison", flush=True)
            return Path(r["root"])
        print(f"   DEGRADED, discarding: {json.dumps(r['reasons'])[:200]}",
              flush=True)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=32,
                    help="operator-set. 32 previously gave 25 read timeouts "
                         "at a 300 s narrator timeout; that timeout is now "
                         "600 s, which addresses the measured failure.")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print("== pre-flight ==", flush=True)
    checks = preflight()
    checks["narrator"] = probe(NARRATOR["base_url"], NARRATOR["model"],
                               NARRATOR["expect"])
    # Recorded for the record, not required: this is the route that failed.
    try:
        checks["env_narrator_route"] = probe(
            os.environ.get("SYNTHESIS_LLM_BASE_URL", "http://localhost:4000/v1"),
            os.environ.get("SYNTHESIS_LLM_MODEL", "skynet"), checks["narrator"])
    except Exception as exc:
        checks["env_narrator_route"] = f"UNAVAILABLE: {type(exc).__name__}"
    print(json.dumps(checks, indent=1), flush=True)
    if args.dry_run:
        print("dry run: guards pass, nothing launched")
        return 0

    STATE.parent.mkdir(parents=True, exist_ok=True)
    st = {"preflight": checks, "narrator": NARRATOR, "attempts": []}

    a = capture("a", args.attempts, args.workers, st)
    b = capture("b", args.attempts, args.workers, st) if a else None

    if not (a and b):
        st["verdict"] = "not_run"
        st["why"] = ("no clean capture: the arm reported it could not narrate. "
                     "A degraded capture is not a draw.")
        STATE.write_text(json.dumps(st, indent=1) + "\n")
        print("\nnot_run — no clean capture pair", flush=True)
        print("generic rerun complete", flush=True)
        return 1

    names = sorted({p.name for p in (a / ARM / "answers").glob("*.json")}
                   & {p.name for p in (b / ARM / "answers").glob("*.json")})
    same, paths, excluded = 0, {}, []
    for n in names:
        ja = json.loads((a / ARM / "answers" / n).read_text())
        jb = json.loads((b / ARM / "answers" / n).read_text())
        # An answer whose narration failed transiently in EITHER capture cannot
        # speak to whether the arm is deterministic; it speaks to the endpoint.
        ra = str((ja.get("answer") or {}).get("fallback_reason") or "")
        rb = str((jb.get("answer") or {}).get("fallback_reason") or "")
        if any(r and classify(r) in ("transient", "unknown") for r in (ra, rb)):
            excluded.append(n)
            continue
        x, y = strip_clock(ja), strip_clock(jb)
        if x == y:
            same += 1
        else:
            for p in diff_paths(x, y):
                paths[p] = paths.get(p, 0) + 1

    scored = sorted(p for p in paths
                    if any(m in p.lower() for m in SCORED_MARKERS))
    compared = len(names) - len(excluded)
    st["comparison"] = {
        "answers_seen": len(names),
        "excluded_transient": len(excluded),
        "excluded_cases": excluded[:20],
        "compared": compared, "identical": same,
        "identity_rate": round(same / compared, 4) if compared else None,
        "differing_paths": dict(sorted(paths.items(), key=lambda kv: -kv[1])[:25]),
        "paths_in_scored_fields": scored,
        "h3_holds": not scored,
        "verdict": ("content-identical" if same == compared
                    else ("non-scored jitter" if not scored
                          else "DIFFERS IN A SCORED FIELD")),
    }
    STATE.write_text(json.dumps(st, indent=1) + "\n")
    c = st["comparison"]
    print(f"\ngeneric: {c['identical']}/{c['compared']} identical "
          f"({c['excluded_transient']} excluded for transient narration failure), "
          f"verdict {c['verdict']}", flush=True)
    if paths:
        print("differing paths:", json.dumps(c["differing_paths"], indent=1),
              flush=True)
    print("generic rerun complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
