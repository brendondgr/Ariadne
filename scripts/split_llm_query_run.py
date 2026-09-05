#!/usr/bin/env python3
"""Split the llm_query re-run across two GPUs, and record why an empty is empty.

Plan: ``docs/plans/2026-09-05-split-llm-query-rerun.md``.

Two vLLM instances, ``default-model-2`` and ``default-model-3`` on ``:9090``,
16 concurrent each. The question set is split **stratified by ``d_tier``**: D4,
D5 and D6 are where the previous run failed, so an unstratified split would hand
one GPU the easy half and make the two incomparable.

The probe exists because two causes of an empty answer look identical
downstream — a clock that cuts the model off, and a token budget it spends
entirely on reasoning. The 2026-09-04 run could not tell them apart, and the
budget it used (8,192) was justified from a single easy question that needed
4,134 tokens while the same probe produced 10,493 when given room. This records
``finish_reason`` and ``completion_tokens`` per call so the artifacts decide.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from utils.config import load_env  # noqa: E402

load_env()

BASE_URL = "http://localhost:9090/v1"
MODELS = ("default-model-2", "default-model-3")
WORKERS = 16
BUDGET = 32768
DEV = REPO / "docs/evaluation/composition/bank/bank-dev.json"
ROOT = REPO / "docs/evaluation/experiments/llm-query-split-2026-09-05"
LOGS = REPO / "logs/2026-09-05"
PROBE_OUT = REPO / "docs/evaluation/composition/bank/split-probe-2026-09-05.json"


def stratified_split() -> tuple[list[str], list[str]]:
    """Alternate within each tier, so both halves carry the same difficulty mix."""
    qs = json.loads(DEV.read_text())["questions"]
    by_tier: dict[str, list[str]] = defaultdict(list)
    for q in sorted(qs, key=lambda q: q["id"]):
        by_tier[q["d_tier"]].append(q["id"])
    a: list[str] = []
    b: list[str] = []
    for tier in sorted(by_tier):
        for i, qid in enumerate(by_tier[tier]):
            (a if i % 2 == 0 else b).append(qid)
    return a, b


def probe(ids: list[str], n: int = 10) -> dict:
    """Ten real builder calls at full concurrency, recording why each ends.

    Weighted to the tiers that failed: D4/D5/D6 are the ones whose median wall
    sat exactly on the previous ceiling.
    """
    import requests
    from utils.evaluation.judge_answers import _prompt_for  # noqa: F401  (shape only)

    qs = {q["id"]: q for q in json.loads(DEV.read_text())["questions"]}
    hard = [i for i in ids if qs[i]["d_tier"] in ("D4", "D5", "D6")][:n]
    sample = hard or ids[:n]
    out: dict = {"base_url": BASE_URL, "budget": BUDGET, "workers": WORKERS, "calls": []}
    lock = threading.Lock()

    def one(qid: str, model: str) -> None:
        prompt = (f"Write a single read-only Cypher query answering: "
                  f"{qs[qid]['question']}\nReturn only the query.")
        t0 = time.time()
        try:
            r = requests.post(f"{BASE_URL}/chat/completions",
                              json={"model": model,
                                    "messages": [{"role": "user", "content": prompt}],
                                    "max_tokens": BUDGET, "temperature": 0.0},
                              timeout=3600)
            body = r.json()
            ch = body["choices"][0]
            rec = {
                "id": qid, "model": model, "served": body.get("model"),
                "wall_s": round(time.time() - t0, 1),
                "finish_reason": ch.get("finish_reason"),
                "completion_tokens": (body.get("usage") or {}).get("completion_tokens"),
                "content_chars": len(ch["message"].get("content") or ""),
                "reasoning_chars": len(ch["message"].get("reasoning") or ""),
            }
        except Exception as exc:                                   # noqa: BLE001
            rec = {"id": qid, "model": model, "error": f"{type(exc).__name__}: {exc}",
                   "wall_s": round(time.time() - t0, 1)}
        with lock:
            out["calls"].append(rec)
            print(f"  probe {qid[:40]:42s} {json.dumps(rec)[:150]}", flush=True)

    threads = [threading.Thread(target=one, args=(q, MODELS[i % 2]))
               for i, q in enumerate(sample)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ok = [c for c in out["calls"] if c.get("content_chars", 0) > 0]
    cut = [c for c in out["calls"] if c.get("finish_reason") == "length"]
    out["verdict"] = {
        "emitted_content": len(ok), "of": len(out["calls"]),
        "hit_the_token_ceiling": len(cut),
        # This is the question the run exists to settle.
        "cause": ("budget — the model spends the whole allowance reasoning"
                  if len(cut) > len(out["calls"]) / 2 else
                  "not the budget at this size" if ok else "no content at all — investigate"),
        "max_completion_tokens": max((c.get("completion_tokens") or 0) for c in out["calls"]),
    }
    return out


def launch(model: str, ids: list[str], tag: str) -> subprocess.Popen:
    root = ROOT / tag
    root.mkdir(parents=True, exist_ok=True)
    idfile = LOGS / f"split-{tag}.txt"
    idfile.write_text(",".join(ids))
    env = {
        **os.environ,
        "ORCH_MAX_HOPS": "5",
        # untruncated_env sets the model, budget and (since a1e20f6) the timeout;
        # it does not set the endpoint, so it is passed here.
        "SPECIALIST_LLM_BASE_URL": BASE_URL,
    }
    log = (LOGS / f"run-{tag}.log").open("w")
    return subprocess.Popen(
        ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
         "--arm", "llm_query", "--bank", str(DEV), "--root", str(root),
         "--llm-model", model, "--llm-max-tokens", str(BUDGET),
         "--workers", str(WORKERS), "--only", ",".join(ids)],
        cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe-only", action="store_true")
    args = ap.parse_args()

    a, b = stratified_split()
    print(f"split: {len(a)} + {len(b)} = {len(a) + len(b)}", flush=True)

    print("probing at full concurrency, weighted to the tiers that failed…", flush=True)
    rec = probe(a + b)
    PROBE_OUT.write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(rec["verdict"], indent=1), flush=True)
    if args.probe_only:
        return 0

    procs = {tag: launch(model, ids, tag)
             for tag, model, ids in (("a", MODELS[0], a), ("b", MODELS[1], b))}
    for tag, p in procs.items():
        print(f"launched {tag} on {MODELS[0] if tag == 'a' else MODELS[1]} pid={p.pid}",
              flush=True)
    (LOGS / "pids.json").write_text(
        json.dumps({t: p.pid for t, p in procs.items()}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
