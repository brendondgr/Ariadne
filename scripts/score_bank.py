#!/usr/bin/env python3
"""Score the expansion bank without a grader, and report it honestly.

Recall of snapshot-derived gold from retrieved evidence — no model in the
scoring loop, so every number here is a retrieval fact rather than a grading
opinion. That is the point of computing gold before the question exists.

Three reporting rules, each of which exists because breaking it produces a
figure that looks comparable and is not:

* **Never a pooled figure alone.** The bank deliberately over-samples the
  under-represented corners, so its pooled accuracy is an artifact of the draw.
  A reweighted estimate is printed beside it, weighting each shape by how many
  instances the census says it actually has.
* **Direction is separated.** Step 6 found the system answers one side of an
  edge and not the other; averaging the two hides the only finding that has
  moved a conclusion.
* **The holdout half is reported apart from dev**, and neither is quoted until
  both exist, so a split cannot be re-drawn after seeing a score.

    uv run python scripts/score_bank.py
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from utils.evaluation.property_gold import rescore_artifact

BANK = Path("docs/evaluation/composition/bank/bank.json")
ROOT = Path("docs/evaluation/experiments/expansion-2026-09-01")


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 4) if values else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, default=BANK)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--arm", default="deterministic")
    parser.add_argument(
        "--rewrite", choices=("off", "det", "model"), default=None,
        help="score the EXP-2026-09-014 arm for this rewrite mode "
             "(shorthand for --arm rewrite_off|rewrite_det|rewrite_model)",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--rescore-property-gold", action="store_true",
                        help="rematch property values by containment in the answer "
                             "(utils.evaluation.property_gold); records both figures")
    args = parser.parse_args()
    if args.rewrite:
        args.arm = f"rewrite_{args.rewrite}"

    bank = json.loads(args.bank.read_text())
    by_id = {q["id"]: q for q in bank["questions"]}
    weights = bank["meta"]["reweighting"]["census_instances"]

    rows: list[dict[str, Any]] = []
    for path in sorted((args.root / args.arm / "answers").glob("*.json")):
        if ".judgment" in path.name:
            continue
        answer = json.loads(path.read_text())
        entry = by_id.get(answer["id"])
        if entry is None:
            continue
        coverage = (answer.get("deterministic_scores") or {}).get("coverage") or {}
        volume = answer.get("evidence_volume") or {}
        # Which rung of the rewrite stage answered this question, straight off
        # the artifact. Absent for every arm that predates the stage and for the
        # off arm, which is what makes "the model was consulted on X%" a fact
        # about this run rather than an assumption about the flag.
        rewrite = (answer.get("run_meta") or {}).get("rewrite") or {}
        recall_before = coverage.get("coverage")
        recall = recall_before
        # Property reads were scored against a rule nothing could satisfy: the
        # gold is a value and the matcher only ever held identifiers. Under
        # --rescore-property-gold the value half is rematched by containment in
        # the composed answer; the identifier half is taken from the artifact's
        # own verdict, so exactly one thing differs between the two figures.
        if args.rescore_property_gold:
            rescored = rescore_artifact(entry, answer)
            if rescored is not None:
                recall = rescored["coverage"]
        rows.append(
            {
                "id": answer["id"],
                "spec_id": entry["spec_id"],
                "split": entry["split"],
                "d_tier": entry["d_tier"],
                "register": entry["register"],
                "shapes": entry["spec"]["shapes"],
                "anchor_label": entry["spec"].get("anchor_label"),
                "reverse": bool(entry["spec"]["steps"] and entry["spec"]["steps"][-1]["reverse"]),
                "gold_width": entry["spec"]["gold_width"],
                "recall": recall,
                "recall_before": recall_before,
                "retrieved_nothing": not (volume.get("records") or volume.get("related")),
                "rung": rewrite.get("rung", "off"),
                "model_consulted": bool(rewrite.get("served_model")),
                "cache_hit": bool(rewrite.get("cache_hit")),
                "served_model": rewrite.get("served_model", ""),
            }
        )

    answerable = [r for r in rows if r["d_tier"] != "D0" and r["recall"] is not None]
    abstain = [r for r in rows if r["d_tier"] == "D0"]

    per_shape: dict[str, list[float]] = defaultdict(list)
    for row in answerable:
        for shape in row["shapes"]:
            per_shape[shape].append(row["recall"])

    # Reweight per-shape means by how many instances the census says each shape
    # has. This is the figure comparable to a naturally-drawn bank; the pooled
    # one is not.
    weighted_num = sum(
        statistics.fmean(v) * weights.get(shape, 0) for shape, v in per_shape.items()
    )
    weighted_den = sum(weights.get(shape, 0) for shape in per_shape)

    def slice_mean(pred) -> float | None:
        return mean([r["recall"] for r in answerable if pred(r)])

    rungs = Counter(r["rung"] for r in rows)
    report = {
        "arm": args.arm,
        "rewrite": {
            "rungs": dict(sorted(rungs.items())),
            "model_consulted": (
                round(sum(r["model_consulted"] for r in rows) / len(rows), 4) if rows else None
            ),
            "cache_hit": (
                round(sum(r["cache_hit"] for r in rows) / len(rows), 4) if rows else None
            ),
            "served_models": sorted({r["served_model"] for r in rows} - {""}),
        },
        "property_gold_rescored": bool(args.rescore_property_gold),
        "questions": len(rows),
        "answerable": len(answerable),
        "abstention_probes": len(abstain),
        "pooled_recall": mean([r["recall"] for r in answerable]),
        "reweighted_recall": round(weighted_num / weighted_den, 4) if weighted_den else None,
        "by_split": {s: slice_mean(lambda r, s=s: r["split"] == s) for s in ("dev", "holdout")},
        "by_tier": {
            t: slice_mean(lambda r, t=t: r["d_tier"] == t)
            for t in sorted({r["d_tier"] for r in answerable})
        },
        "by_direction": {
            "forward": slice_mean(lambda r: not r["reverse"]),
            "reverse": slice_mean(lambda r: r["reverse"]),
        },
        "by_register": {
            reg: slice_mean(lambda r, reg=reg: r["register"] == reg)
            for reg in sorted({r["register"] for r in answerable})
        },
        "by_width_band": {
            band: slice_mean(lambda r, lo=lo, hi=hi: lo <= r["gold_width"] <= hi)
            for lo, hi, band in ((1, 1, "1"), (2, 5, "2-5"), (6, 20, "6-20"), (21, 10**9, "21+"))
        },
        "abstention": {
            "n": len(abstain),
            "correctly_returned_nothing": sum(1 for r in abstain if r["retrieved_nothing"]),
            "rate": round(
                sum(1 for r in abstain if r["retrieved_nothing"]) / len(abstain), 4
            ) if abstain else None,
        },
        "by_shape": {
            shape: {"n": len(v), "recall": mean(v), "census_instances": weights.get(shape)}
            for shape, v in sorted(per_shape.items())
        },
        "fully_answered": sum(1 for r in answerable if r["recall"] == 1.0),
        "nothing_retrieved": sum(1 for r in answerable if r["recall"] == 0.0),
    }

    out = args.out or args.bank.parent / "score.json"
    out.write_text(json.dumps({"report": report, "rows": rows}, indent=1) + "\n")

    print(f"score -> {out}")
    print(f"  {report['answerable']} answerable + {report['abstention_probes']} abstention probes")
    print(f"\n  pooled recall      {report['pooled_recall']}   <- draw artifact, do not quote alone")
    print(f"  reweighted recall  {report['reweighted_recall']}   <- comparable figure")
    print(f"  dev {report['by_split']['dev']} / holdout {report['by_split']['holdout']}")
    print(f"\n  by tier:      {report['by_tier']}")
    print(f"  by direction: {report['by_direction']}")
    print(f"  by register:  {report['by_register']}")
    print(f"  by width:     {report['by_width_band']}")
    a = report["abstention"]
    print(f"\n  abstention: returned nothing on {a['correctly_returned_nothing']}/{a['n']} "
          f"({a['rate']:.1%})" if a["rate"] is not None else "")
    print(f"  fully answered {report['fully_answered']}/{report['answerable']}; "
          f"nothing retrieved {report['nothing_retrieved']}")
    worst = sorted(report["by_shape"].items(), key=lambda kv: kv[1]["recall"])[:8]
    print("\n  weakest shapes:")
    for shape, v in worst:
        print(f"    {v['recall']:.2f}  (n={v['n']}, census {v['census_instances']})  {shape}")


if __name__ == "__main__":
    main()
