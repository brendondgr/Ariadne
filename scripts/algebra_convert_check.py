#!/usr/bin/env python3
"""Phase C check: every recorded typed step converts to the internal form and back.

Reads the typed steps of a run (by default EXP-2026-11-018's outputs):
- the variant rows (``planner.plan[].step``) of the T-lazy, T-full and T-lazy-G arms;
- the dev answers (``run_meta.observed_plan[].step``).

For each step it checks four things:
1. ``from_typed_step`` succeeds;
2. the JSON round trip returns the same tree;
3. ``to_typed_step`` gives back the step as the builder reads it (``normalise``);
4. ``check`` against the step's card passes. A step whose anchors are resolved at
   run time is counted apart: it is refused until its ids are filled in.

    uv run python scripts/algebra_convert_check.py [run_dir] [--out report.json]
"""

from __future__ import annotations

import argparse
import collections
import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
RUN = REPO / "docs/evaluation/experiments/typed-engine-fixes-2026-11-20"


def recorded_steps(run: Path) -> list[dict]:
    out = []
    for arm in ("T-lazy", "T-full", "T-lazy-G"):
        p = run / "variants" / f"{arm}.json"
        if not p.exists():
            continue
        for r in json.loads(p.read_text()):
            for i, sq in enumerate((r.get("planner") or {}).get("plan") or []):
                if sq.get("step"):
                    out.append({"where": f"variants/{arm}/{r['case_id']}/{r['tier']}/{i}",
                                "source": sq.get("source") or r.get("bank"), "step": sq["step"]})
    for f in sorted(glob.glob(str(run / "dev*" / "planned_llm_typed_*" / "answers" / "*.json"))):
        d = json.loads(Path(f).read_text())
        for i, sq in enumerate((d.get("run_meta") or {}).get("observed_plan") or []):
            if sq.get("step"):
                out.append({"where": f"{Path(f).relative_to(run)}/{i}", "source": sq.get("source"), "step": sq["step"]})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default=str(RUN))
    ap.add_argument("--out")
    a = ap.parse_args(argv)

    from utils.agent.catalog import load_all
    from utils.specialists.algebra import InvalidOp, check, from_dict, to_dict
    from utils.specialists.algebra.from_typed_step import from_typed_step, normalise, to_typed_step
    from utils.specialists.signals import TypedStep

    cats, _ = load_all(REPO / "data", live=False)
    cards = {k: c.model if hasattr(c, "model") else c.card for k, c in cats.items()}
    steps = recorded_steps(Path(a.run))
    tally = collections.Counter()
    refusals = collections.Counter()
    failures = []
    failures_invalid = []
    for s in steps:
        ts = TypedStep.from_dict(s["step"])
        card = cards.get(s["source"])
        try:
            ir = from_typed_step(ts, card)
        except Exception as exc:  # noqa: BLE001 - every failure is reported
            failures.append({**s, "stage": "convert", "error": str(exc)})
            continue
        tally["converted"] += 1
        if from_dict(json.loads(json.dumps(to_dict(ir)))) != ir:
            failures.append({**s, "stage": "json"})
            continue
        tally["json_round_trip"] += 1
        if to_typed_step(ir) != normalise(ts):
            failures.append({**s, "stage": "inverse", "got": to_typed_step(ir), "want": normalise(ts)})
            continue
        tally["inverse_round_trip"] += 1
        if card is None:
            tally["no_card"] += 1
            continue
        try:
            check(ir, card)
            tally["valid"] += 1
        except InvalidOp as exc:
            key = "refused_runtime_anchor" if not s["step"].get("anchor_ids") and "needs at least one id" in str(exc) \
                else "refused"
            if key == "refused":
                failures_invalid.append({**s, "error": str(exc)})
            tally[key] += 1
            refusals[str(exc).split(": ", 1)[-1][:120]] += 1
    report = {"run": str(Path(a.run).relative_to(REPO)) if Path(a.run).is_relative_to(REPO) else a.run,
              "steps": len(steps), "by_origin": dict(collections.Counter(s["where"].split("/")[0] for s in steps)),
              "kinds": dict(collections.Counter(s["step"].get("kind") for s in steps)),
              **dict(tally), "failures": failures[:50], "n_failures": len(failures),
              "refusal_messages": dict(refusals.most_common(20)),
              "refused_steps": failures_invalid}
    text = json.dumps(report, indent=1, sort_keys=True)
    if a.out:
        Path(a.out).write_text(text + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in ("failures",)}, indent=1, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
