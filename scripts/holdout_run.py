#!/usr/bin/env python3
"""Answer the sealed 288, once, under the configuration the paper describes.

Protocol: ``docs/research/experiments/EXP-2026-09-007-holdout-spend/PROTOCOL.md``.

Everything here is a guard. The holdout is the one measurement in this project
that cannot be repeated, so the run refuses to start rather than produce
something not comparable to the dev half:

* **The seal is re-asserted at launch**, not trusted from this morning.
* **The stores are counted** -- 4,369/27,669 in Neo4j and 6,374/8,582 in
  Gremlin. A holdout answered against a different graph is not comparable to
  ``EXP-2026-09-005`` and there is no second holdout to redo it with.
* **``llm_query`` runs the settled configuration**: budget 32,768, timeout
  4,096 s, ``ORCH_MAX_HOPS=5``, and *no* thinking cap. ``LLM_THINKING_BUDGET``
  is wired but has never been verified against a live endpoint; enabling it
  here would test a configuration the paper does not describe.
* **An arm that writes fewer than 288 answers is recorded ``not_run``.** A
  partially answered holdout is not a result.

    uv run python scripts/holdout_run.py --arm deterministic generic
    uv run python scripts/holdout_run.py --arm llm_query
"""

from __future__ import annotations

import argparse
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

BANK = REPO / "docs/evaluation/composition/bank/bank-holdout.json"
ROOT = REPO / "docs/evaluation/experiments/holdout-spend-2026-09-05"
EXP = REPO / "docs/research/experiments/EXP-2026-09-007-holdout-spend"
STATE = EXP / "data" / "run-state.json"
LOGS = REPO / "logs/holdout-2026-09-05"

N_HOLDOUT = 288
HOLDOUT_SHA = "812ab787aaaed69addfd65f2c4bf9cc8d2f5f3c6a25c9ee3e2728dc3c812f6ed"
NEO4J_EXPECT = {"nodes": 4369, "edges": 27669}
GREMLIN_EXPECT = {"vertices": 6374, "edges": 8582}


def assert_stores() -> dict:
    from utils.config import settings
    from neo4j import GraphDatabase
    from gremlin_python.driver.client import Client
    from gremlin_python.driver.serializer import GraphSONSerializersV3d0

    out: dict = {}
    drv = GraphDatabase.driver(settings.neo4j_uri,
                               auth=(settings.neo4j_user, settings.neo4j_password))
    try:
        with drv.session() as s:
            out["neo4j"] = {
                "nodes": s.run("MATCH (n) RETURN count(n) AS c").single()["c"],
                "edges": s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]}
    finally:
        drv.close()
    gc = Client(settings.gremlin_url, "g",
                message_serializer=GraphSONSerializersV3d0())
    try:
        out["gremlin"] = {"vertices": gc.submit("g.V().count()").all().result()[0],
                          "edges": gc.submit("g.E().count()").all().result()[0]}
    finally:
        gc.close()
    if out["neo4j"] != NEO4J_EXPECT:
        raise SystemExit(f"neo4j counts moved: {out['neo4j']} != {NEO4J_EXPECT}")
    if out["gremlin"] != GREMLIN_EXPECT:
        raise SystemExit(f"gremlin counts moved: {out['gremlin']} != {GREMLIN_EXPECT}")
    return out


def assert_sealed() -> None:
    r = subprocess.run([sys.executable, str(REPO / "scripts/holdout_seal.py")],
                       cwd=REPO, capture_output=True, text=True)
    if r.returncode != 0 or "SEALED" not in r.stdout:
        raise SystemExit(f"seal check failed:\n{r.stdout[-800:]}\n{r.stderr[-400:]}")
    bank = json.loads(BANK.read_text())
    if bank["meta"].get("holdout_questions_sha256") != HOLDOUT_SHA:
        raise SystemExit("bank-holdout.json is not the set sealed on 2026-09-05")
    if len(bank["questions"]) != N_HOLDOUT:
        raise SystemExit(f"expected {N_HOLDOUT} questions, found {len(bank['questions'])}")


def answers_written(arm: str) -> int:
    adir = ROOT / arm / "answers"
    if not adir.is_dir():
        return 0
    return sum(1 for p in adir.glob("*.json") if ".judgment" not in p.name)


def run_arm(arm: str, *, workers: int, llm_model: str | None) -> dict:
    LOGS.mkdir(parents=True, exist_ok=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    cmd = ["uv", "run", "python", "-m", "utils.evaluation.experiment_untruncated",
           "--arm", arm, "--bank", str(BANK), "--root", str(ROOT),
           "--workers", str(workers)]
    env = {**os.environ, "ORCH_MAX_HOPS": "5"}
    if arm == "llm_query":
        cmd += ["--llm-max-tokens", "32768"]
        if llm_model:
            cmd += ["--llm-model", llm_model]
        env["SPECIALIST_LLM_TIMEOUT_S"] = "4096"
        # Deliberately absent: LLM_THINKING_BUDGET. See the protocol.
        env.pop("LLM_THINKING_BUDGET", None)
    log = LOGS / f"{arm}.log"
    t0 = time.time()
    with log.open("w") as fh:
        proc = subprocess.run(cmd, cwd=REPO, env=env, stdout=fh,
                              stderr=subprocess.STDOUT, check=False)
    n = answers_written(arm)
    return {"arm": arm, "returncode": proc.returncode, "answers": n,
            "complete": n == N_HOLDOUT, "wall_s": round(time.time() - t0, 1),
            "log": str(log)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", nargs="+", required=True,
                    choices=["deterministic", "generic", "llm_query"])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--llm-model", default=None)
    ap.add_argument("--skip-store-check", action="store_true")
    args = ap.parse_args()

    assert_sealed()
    stores = {} if args.skip_store_check else assert_stores()
    print(f"seal OK; stores {json.dumps(stores)}", flush=True)

    STATE.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.is_file() else {"arms": {}}
    state["stores"] = stores or state.get("stores")
    state["holdout_sha256"] = HOLDOUT_SHA

    for arm in args.arm:
        if state["arms"].get(arm, {}).get("complete"):
            print(f"{arm}: already complete, skipping", flush=True)
            continue
        workers = 16 if arm == "llm_query" else args.workers
        print(f"{arm}: start ({workers} workers) {datetime.now():%H:%M:%S}", flush=True)
        rec = run_arm(arm, workers=workers, llm_model=args.llm_model)
        if not rec["complete"]:
            rec["status"] = "not_run"
            rec["reason"] = (f"{rec['answers']}/{N_HOLDOUT} answers — a partially "
                             "answered holdout is not a result")
        else:
            rec["status"] = "done"
        state["arms"][arm] = rec
        STATE.write_text(json.dumps(state, indent=1, default=str) + "\n")
        print(f"{arm}: {rec['status']} {rec['answers']}/{N_HOLDOUT} "
              f"in {rec['wall_s']}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
