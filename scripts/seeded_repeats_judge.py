#!/usr/bin/env python3
"""Grade the three seeded runs under both grader families, counterbalanced.

Protocol: ``docs/research/experiments/EXP-2026-09-009-llm-query-seeded-repeats/PROTOCOL.md``.

Generation alone answers none of the hypotheses. H1, H2 and H3 are all about
*judged* correctness, so every run has to be graded under both families before
anything can be said.

**Why the order is counterbalanced rather than fixed.** EXP-2026-08-022 graded
byte-identical answers in two positions and they came back 0.0088 apart,
consistently negative: the condition graded second scores about 0.01 lower,
whichever it is. H2's falsification threshold is an across-seed SD of 0.03. A
fixed grading order would put a third of that threshold into the seed axis as
pure artifact, so the seeds are counterbalanced across the two families using
``utils.evaluation.grading_order`` and each cell records its position.

    uv run python scripts/seeded_repeats_judge.py --dry-run
    uv run python scripts/seeded_repeats_judge.py --workers 8
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.evaluation.grading_order import counterbalanced, position_of  # noqa: E402

EXP = REPO / "docs/research/experiments/EXP-2026-09-009-llm-query-seeded-repeats"
ROOT = REPO / "docs/evaluation/experiments/seeded-repeats-2026-09-06"
STATE = EXP / "data" / "judge-state.json"
ARM = "llm_query"
N_EXPECT = 284
BASE = "http://localhost:9090/v1"

SEEDS = ("1729", "20260906", "424242")

#: Each family is one grading block. ``served`` is asserted per pass, not
#: trusted from the alias -- the endpoint reported "gemma4-31B" for
#: "gemma4-31B-mtp" during a startup window on 2026-09-06.
#: **gemma grades first, deliberately.** It is ~14x faster (measured
#: 2026-09-06: 284 judgments in 3-4 min against qwen's ~54) and the operator
#: needs its vLLM slot back. Front-loading it releases the GPU after ~12 min
#: instead of at hour three.
#:
#: This does NOT weaken the counterbalancing. `counterbalanced()` keys on the
#: block index, so swapping which family is block 0 swaps the position
#: assignment with it: every seed still occupies position sum 2 across the two
#: families, and the ~0.01 position effect still cancels in the balanced
#: estimate. Only the labels move.
FAMILIES = [
    {"key": "gemma31", "alias": "default-model-2", "expect": "gemma4-31B-mtp", "suffix": ".g31"},
    {"key": "qwen",    "alias": "default-model",   "expect": "qwen38-27B-v2",  "suffix": ".q"},
]


def probe(alias: str, expect: str) -> str:
    import urllib.request

    body = json.dumps({
        "model": alias,
        "messages": [{"role": "user", "content": "Reply with only the word OK."}],
        "max_tokens": 2048,
    }).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as fh:
        payload = json.load(fh)
    if "error" in payload:
        raise RuntimeError(f"{alias}: {payload['error']}")
    served = payload.get("model")
    if served != expect:
        raise RuntimeError(
            f"{alias} serves {served!r}, record contains {expect!r} — refusing. "
            "Reconciling this silently is how an alias comes to stand for three "
            "different models."
        )
    return served


def answers_present() -> dict[str, int]:
    out = {}
    for s in SEEDS:
        d = ROOT / f"seed-{s}" / ARM / "answers"
        out[s] = len(list(d.glob("*.json"))) if d.is_dir() else 0
    return out


def score(seed: str, suffix: str) -> dict:
    """Mean judged correctness over a graded pass, read from the sidecars."""
    d = ROOT / f"seed-{seed}" / ARM / "answers"
    vals, failures = [], 0
    for p in d.glob(f"*.judgment{suffix}.json"):
        try:
            j = json.loads(p.read_text())
        except Exception:
            failures += 1
            continue
        v = j.get("correctness", j.get("score"))
        if isinstance(v, (int, float)):
            vals.append(float(v))
        else:
            failures += 1
    return {
        "n": len(vals),
        "mean": round(statistics.fmean(vals), 4) if vals else None,
        "unparsed": failures,
        "errors": len(list(d.glob(f"*.judgment{suffix}.error.txt"))),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8,
                    help="operator cap for the qwen endpoint on this task")
    ap.add_argument("--gemma-workers", type=int, default=24)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    present = answers_present()
    print("answers per seed:", present, flush=True)
    short = {s: n for s, n in present.items() if n < N_EXPECT}
    if short:
        raise SystemExit(f"refusing to grade: seeds short of {N_EXPECT}: {short}")

    served = {f["key"]: probe(f["alias"], f["expect"]) for f in FAMILIES}
    print("served:", json.dumps(served), flush=True)

    plan = []
    for block, fam in enumerate(FAMILIES):
        order = counterbalanced(SEEDS, block)
        for seed in order:
            plan.append({
                "family": fam["key"], "seed": seed,
                "position": position_of(seed, SEEDS, block),
                "suffix": fam["suffix"],
            })
    print("grading plan (counterbalanced):", flush=True)
    for row in plan:
        print(f"  {row['family']:8} seed {row['seed']:9} position {row['position']}",
              flush=True)
    if args.dry_run:
        print("dry run: nothing graded")
        return 0

    from utils.evaluation.judge_answers import JudgeConfig, run

    st = {"served": served, "plan": plan, "passes": {}, "scores": {}}
    STATE.parent.mkdir(parents=True, exist_ok=True)

    for row in plan:
        fam = next(f for f in FAMILIES if f["key"] == row["family"])
        key = f"{row['family']}-{row['seed']}"
        workers = args.workers if fam["key"] == "qwen" else args.gemma_workers
        print(f"\n== {key} (position {row['position']}, {workers} workers) ==",
              flush=True)
        summary = run(
            ROOT / f"seed-{row['seed']}", ARM,
            JudgeConfig(
                base_url=BASE, model=fam["alias"],
                # EXP-2026-08-021: ~7-8% of the largest answers fail to grade at
                # smaller budgets, and the failures land on the thorough answers.
                max_tokens=32768, timeout_s=900.0,
                position=row["position"],
            ),
            workers=workers, suffix=fam["suffix"],
        )
        st["passes"][key] = {"summary": str(summary)[:400],
                             "finished": datetime.now().isoformat(timespec="seconds")}
        st["scores"][key] = score(row["seed"], fam["suffix"])
        STATE.write_text(json.dumps(st, indent=1) + "\n")
        print(json.dumps(st["scores"][key], indent=1), flush=True)

    print("\n== across-seed spread (H2 threshold: SD < 0.03) ==", flush=True)
    per_family = {}
    for fam in FAMILIES:
        means = [st["scores"][f"{fam['key']}-{s}"]["mean"] for s in SEEDS]
        if any(m is None for m in means):
            print(f"  {fam['key']:8} incomplete: {means}", flush=True)
            continue
        per_family[fam["key"]] = means
        sd = statistics.pstdev(means)
        st.setdefault("spread", {})[fam["key"]] = {
            "means": means, "sd": round(sd, 4), "h2_holds": sd < 0.03,
            "caveat": "within one family, position is confounded with seed; "
                      "use the balanced estimate below for H2",
        }
        print(f"  {fam['key']:8} means {means}  SD {sd:.4f}  (position-confounded)",
              flush=True)

    # Every seed occupies position sum 2 across the two families, so averaging a
    # seed's two family means cancels the ~0.01 position effect exactly. This is
    # the estimate H2 is adjudicated on; the per-family SDs above are not.
    if len(per_family) == len(FAMILIES):
        balanced = [statistics.fmean([per_family[f["key"]][i] for f in FAMILIES])
                    for i in range(len(SEEDS))]
        sd = statistics.pstdev(balanced)
        st.setdefault("spread", {})["balanced"] = {
            "means": [round(m, 4) for m in balanced],
            "sd": round(sd, 4),
            "h2_holds": sd < 0.03,
            "method": "per-seed mean of the two families; counterbalancing gives "
                      "every seed position sum 2, so the position effect cancels",
        }
        print(f"\n  balanced {[round(m, 4) for m in balanced]}  SD {sd:.4f}  "
              f"H2 {'holds' if sd < 0.03 else 'FALSIFIED'}", flush=True)
    STATE.write_text(json.dumps(st, indent=1) + "\n")
    print("judging complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
