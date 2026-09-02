#!/usr/bin/env python3
"""Step 6 — can the builder express the shapes no bank has ever asked?

Build a bank from the probe selection plus its authored questions, run one arm
over it, and score with **no judge**: the arm's own answer files carry
`deterministic_scores.coverage`, which is recall of the snapshot-derived gold
from the retrieved evidence. No model is in the scoring loop, so a low number
here is a retrieval fact rather than a grading opinion.

The probe carries controls on shapes the banks already ask. Without them a low
score could be the new shapes or could be the harness, and there would be no way
to tell them apart — which is the whole reason Step 6 runs before Step 7 rather
than after.

    uv run python scripts/run_probe.py --build
    uv run python -m utils.evaluation.experiment_untruncated \
        --arm deterministic --bank docs/evaluation/composition/probe/bank.json \
        --root docs/evaluation/experiments/probe-2026-09-01 --workers 4
    uv run python scripts/run_probe.py --score
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.render_questions import DEFAULT_SPECS, load_specs
from utils.specialists.evalset import spec_bank

PROBE = Path("docs/evaluation/composition/probe")
DEFAULT_ROOT = Path("docs/evaluation/experiments/probe-2026-09-01")


def build(args: argparse.Namespace) -> None:
    selection = json.loads((PROBE / "selection.json").read_text())
    index = json.loads((PROBE.parent / "briefs" / "index.json").read_text())
    ingested = json.loads((PROBE.parent / "authored" / "ingested.json").read_text())

    questions = {
        row["spec_id"]: row["question"]
        for row in ingested["questions"]
        if row["ok"] and row["question"]
    }
    specs = {s.id: s for s in load_specs(args.specs)}

    pairs = []
    missing = []
    for spec_id in selection["spec_ids"]:
        question = questions.get(spec_id)
        if not question:
            missing.append(spec_id)
            continue
        pairs.append((specs[spec_id], question, "analyst"))

    census = json.loads(
        (Path("docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json")).read_text()
    )
    bank = spec_bank.to_bank(
        pairs,
        attack_version=census["sources"]["attack"]["version"],
        capec_version=census["sources"]["capec"]["version"],
        author_model=ingested["report"]["author_model"],
        seed=selection["seed"],
        note="Step 6 capability probe: every never-asked edge type, plus controls "
             "on already-asked shapes so a low score is attributable.",
    )
    spec_bank.write(bank, PROBE / "bank.json")
    print(f"bank -> {PROBE / 'bank.json'}  ({len(pairs)} questions)")
    if missing:
        print(f"  {len(missing)} specs had no authored question: {missing[:5]}")
    controls = set(selection["controls"])
    print(f"  controls: {sum(1 for s, _, _ in pairs if s.id in controls)}")
    print(f"  federated entries: {sum(1 for q in bank['questions'] if 'sub_questions' in q)}")


def score(args: argparse.Namespace) -> None:
    bank = json.loads((PROBE / "bank.json").read_text())
    selection = json.loads((PROBE / "selection.json").read_text())
    census = json.loads(
        Path("docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json").read_text()
    )
    never = set(census["coverage"]["never_asked"])
    controls = set(selection["controls"])
    by_id = {q["id"]: q for q in bank["questions"]}

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
        rows.append(
            {
                "id": answer["id"],
                "spec_id": entry["spec_id"],
                "d_tier": entry["d_tier"],
                "shapes": entry["spec"]["shapes"],
                "control": entry["spec_id"] in controls,
                "gold_width": entry["spec"]["gold_width"],
                "gold": coverage.get("gold"),
                "found": coverage.get("found"),
                "recall": coverage.get("coverage"),
                "missing": coverage.get("missing") or [],
                "anchor_label": entry["spec"].get("anchor_label", "?"),
                "records": volume.get("records"),
                "related": volume.get("related"),
            }
        )

    scored = [r for r in rows if r["recall"] is not None and r["d_tier"] != "D0"]
    d0 = [r for r in rows if r["d_tier"] == "D0"]

    def mean(values: list[float]) -> float | None:
        return round(statistics.fmean(values), 4) if values else None

    per_shape: dict[str, list[float]] = defaultdict(list)
    for row in scored:
        for shape in row["shapes"]:
            per_shape[shape].append(row["recall"])

    # Direction is the axis the blind holdout collapsed on, and the committed
    # banks only ever ask one side of each shape. Reporting a single recall
    # number would average the side the system handles with the side it does
    # not, and hide the only thing this probe can actually see.
    per_anchor: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in scored:
        if len(row["shapes"]) == 1:
            per_anchor[(row["shapes"][0], row["anchor_label"])].append(row["recall"])

    new_shape_rows = [r for r in scored if not r["control"]]
    control_rows = [r for r in scored if r["control"]]
    report = {
        "arm": args.arm,
        "answers": len(rows),
        "scored": len(scored),
        "d0_probes": len(d0),
        "recall_all": mean([r["recall"] for r in scored]),
        "recall_new_shapes": mean([r["recall"] for r in new_shape_rows]),
        "recall_controls": mean([r["recall"] for r in control_rows]),
        "fully_answered": sum(1 for r in scored if r["recall"] == 1.0),
        "nothing_retrieved": sum(1 for r in scored if r["recall"] == 0.0),
        "by_tier": {
            tier: mean([r["recall"] for r in scored if r["d_tier"] == tier])
            for tier in sorted({r["d_tier"] for r in scored})
        },
        "by_shape_and_anchor": {
            f"{shape}  |  anchored on {anchor}": {"n": len(v), "recall": mean(v)}
            for (shape, anchor), v in sorted(per_anchor.items())
        },
        "by_shape": {
            shape: {
                "n": len(values),
                "recall": mean(values),
                "never_asked": shape in never,
            }
            for shape, values in sorted(per_shape.items())
        },
        "d0_abstained": sum(1 for r in d0 if not r.get("related") and not r.get("records")),
    }
    out = PROBE / "probe-report.json"
    out.write_text(json.dumps({"report": report, "rows": rows}, indent=1) + "\n")

    print(f"probe report -> {out}")
    print(f"  {report['scored']} answerable questions, {report['d0_probes']} D0 probes")
    print(f"  recall overall {report['recall_all']}; "
          f"new shapes {report['recall_new_shapes']}; controls {report['recall_controls']}")
    print(f"  fully answered {report['fully_answered']}/{report['scored']}; "
          f"nothing retrieved {report['nothing_retrieved']}")
    print(f"  by tier: {report['by_tier']}")
    print("\n  single-hop recall by shape AND anchor (direction matters):")
    for key, value in sorted(report["by_shape_and_anchor"].items(), key=lambda kv: kv[1]["recall"]):
        print(f"    {value['recall']:.2f}  (n={value['n']})  {key}")
    print("\n  shapes the builder cannot reach (recall 0):")
    dead = [s for s, v in report["by_shape"].items() if v["recall"] == 0.0]
    for shape in dead:
        print(f"    - {shape}" + ("  [never asked]" if report["by_shape"][shape]["never_asked"] else ""))
    if not dead:
        print("    none")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--arm", default="deterministic")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.build:
        build(args)
    if args.score:
        score(args)
    if not (args.build or args.score):
        parser.error("pass --build or --score")


if __name__ == "__main__":
    main()
