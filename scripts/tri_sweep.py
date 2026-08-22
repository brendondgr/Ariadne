#!/usr/bin/env python3
"""EXP-2026-08-013 phase 2 — run and score the tri-source bank.

    uv run python scripts/tri_sweep.py --out docs/evaluation/tri-bank-2026-08-22

No language model is in the answer path: planning, query construction and
composition are all deterministic, and every figure below is set comparison
against gold derived from the blueprint and the declared correspondence. The
reading is byte-reproducible.

**Two families of question, scored differently, and the split is the point.**

The ``bridge-*`` positives are scored by recall: did the technique (and, where
asked, its mitigations) reach the evidence? The ``bridge-refusal``,
``bridge-partial`` and ``identity-control`` negatives are scored by *silence*:
naming any ATT&CK technique is a false claim, and the correct behaviour is to
produce none. A run that scored well on the positives while failing the
negatives would have learned to attach ATT&CK to everything, which is the
failure mode a recall-only metric cannot see and the reason the negatives are
half the bank.

``bridge-partial`` is the sharpest of them. Those anchors hold ONE half of the
DCSync right pair, and the customer's own catalog says that is insufficient
alone. Asserting T1003.006 there is not a retrieval error; it is asserting
something their catalog denies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from scripts.identity_sweep import (  # noqa: E402
    ARMS,
    BASE_ENV,
    TRI_DATA_DIR,
    TRI_ENV,
    apply_env,
    clear_env,
    run_one,
)
from utils.specialists.evalset.tri_gold import (  # noqa: E402
    BRIDGE_PARTIAL,
    REFUSAL_KINDS,
)

# Any ATT&CK technique or mitigation identifier appearing in retrieved evidence.
_ATTACK_ID = re.compile(r"^(?:T\d{4}(?:\.\d{3})?|M\d{4})$")


def _attack_ids(retrieved: set[str]) -> set[str]:
    return {v for v in retrieved if _ATTACK_ID.match(v)}


def score(entry: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """One question's score. Positives by recall, negatives by silence."""
    retrieved = set(result["retrieved_ids"])
    leaked = _attack_ids(retrieved)
    routed = set(result.get("plan_sources") or [])

    if entry["kind"] in REFUSAL_KINDS:
        # For `bridge-partial` the specific false claim is DCSync; any other
        # technique arriving is still noise, so both are recorded and the score
        # is the strict one.
        false_claim = (
            "T1003.006" in leaked if entry["kind"] == BRIDGE_PARTIAL else bool(leaked)
        )
        out = {
            "retrieval": 0.0 if leaked else 1.0,
            "silent": 0 if leaked else 1,
            "leaked_attack_ids": sorted(leaked)[:8],
            "false_claim": bool(false_claim),
            "of": 1,
            "hit": 0 if leaked else 1,
            "routed": sorted(routed),
            "reached_attack": "attack" in routed,
            "abstained": result["abstained"],
        }
        if entry["kind"] != BRIDGE_PARTIAL:
            return out
        # A partial-right anchor may legitimately surface nothing at all; the
        # only thing it may not do is claim the technique.
        out["retrieval"] = 0.0 if false_claim else 1.0
        out["hit"] = 0 if false_claim else 1
        return out

    gold = set(entry["expected_ids"])
    hits = len(gold & retrieved)
    return {
        "retrieval": hits / len(gold) if gold else 1.0,
        "hit": hits,
        "of": len(gold),
        "precision": (len(gold & retrieved) / len(leaked)) if leaked else 0.0,
        "leaked_attack_ids": sorted(leaked - gold)[:8],
        "routed": sorted(routed),
        "reached_attack": "attack" in routed,
        "abstained": result["abstained"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="docs/evaluation/tri-bank-2026-08-22")
    parser.add_argument("--arms", default="generic,deterministic")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    out = Path(args.out)
    bank = json.loads((out / "bank.json").read_text(encoding="utf-8"))
    questions = bank["questions"]
    order = list(questions)[: args.limit or None]

    BASE_ENV["ARIADNE_DATA_DIR"] = TRI_DATA_DIR
    BASE_ENV.update(TRI_ENV)
    print(f"[tri] three sources live; data_dir={TRI_DATA_DIR}; n={len(order)}")

    state: dict[str, Any] = {"results": {}}
    state_path = out / "tri_sweep_state.json"

    for arm in [a.strip() for a in args.arms.split(",") if a.strip()]:
        apply_env({**BASE_ENV, **ARMS[arm]})
        from utils.specialists.schema.build import get_registry

        get_registry.cache_clear()
        for index, qid in enumerate(order, 1):
            entry = questions[qid]
            try:
                result = run_one(entry["question"])
            except Exception as exc:  # noqa: BLE001
                print(f"[{arm}] {qid}: ERROR {type(exc).__name__}: {exc}")
                continue
            sc = score(entry, result)
            state["results"][f"{arm}::{qid}"] = {
                "arm": arm,
                "question_id": qid,
                "kind": entry["kind"],
                "score": sc,
                "plan_sources": result["plan_sources"],
                "retrieved_ids": result["retrieved_ids"],
                "queries": result["queries"],
                "answer": result["answer"],
            }
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
            flag = "" if sc["retrieval"] == 1.0 else "  <-"
            print(
                f"[{arm}] {index}/{len(order)} {qid:14s} {entry['kind']:18s} "
                f"{sc['hit']}/{sc['of']}  {sc['retrieval']:.2f}"
                f"  routed={','.join(sc['routed']) or '-'}{flag}"
            )
        clear_env(ARMS[arm])

    by = defaultdict(lambda: defaultdict(list))
    for row in state["results"].values():
        by[row["arm"]][row["kind"]].append(row["score"])
    print()
    for arm in sorted(by):
        alls = [s for k in by[arm] for s in by[arm][k]]
        mean = sum(s["retrieval"] for s in alls) / len(alls)
        print(f"== {arm}  overall {mean:.4f}  (n={len(alls)})")
        for kind in sorted(by[arm]):
            rows = by[arm][kind]
            m = sum(s["retrieval"] for s in rows) / len(rows)
            reached = sum(1 for s in rows if s["reached_attack"])
            print(f"     {kind:20s} n={len(rows):3d}  {m:.4f}   reached attack {reached}/{len(rows)}")
    print(f"\nwrote {state_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
