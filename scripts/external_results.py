#!/usr/bin/env python3
"""Generate the numeric blocks of EXP-2026-08-010's RESULTS.md and manifest.

The research record forbids reporting a metric that is not written to
``data/metrics.json`` first, and forbids hand-transcribing one. This reads the
sweep's own output and emits both the tables RESULTS.md embeds and the metrics
block the manifest carries, so a figure can only ever be wrong in one place.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
EXPERIMENT = REPO / "docs/research/experiments/EXP-2026-08-010-external-validation"

ARM_ROWS = [
    ("oracle--plan-given", "ceiling (direct graph read)"),
    ("deterministic--plan-given", "deterministic, plan given"),
    ("deterministic--plan-given--subset60", "deterministic, plan given (subset of 60)"),
    ("generic--plan-given", "generic, plan given"),
    ("llm--plan-free", "LLM-planned, question text only"),
]


def _row(cell: dict[str, Any]) -> dict[str, Any] | None:
    got = (cell or {}).get("answered") or {}
    return got if got.get("n") else None


def tables(metrics: dict[str, Any]) -> str:
    cells = metrics["cells"]
    out: list[str] = []
    out.append("| arm | n | micro recall | micro precision | macro recall | exact |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for key, label in ARM_ROWS:
        got = _row(cells.get(key, {}))
        if not got:
            out.append(f"| {label} | — | _did not run_ | | | |")
            continue
        out.append(f"| {label} | {got['n']} | {got['micro_recall']:.4f} | "
                   f"{got['micro_precision']:.4f} | {got['macro_recall']:.4f} | "
                   f"{got['exact_match']:.4f} |")
    out.append("")

    ceiling = (cells.get("oracle--plan-given") or {}).get("by_family") or {}
    fam = (cells.get("deterministic--plan-given") or {}).get("by_family") or {}
    if fam:
        out.append("| question family | n | ceiling | deterministic | shortfall |")
        out.append("|---|---:|---:|---:|---:|")
        for name in sorted(fam, key=lambda k: fam[k]["micro_recall"]
                           - (ceiling.get(k) or {}).get("micro_recall", 0)):
            top = (ceiling.get(name) or {}).get("micro_recall", 0.0)
            got = fam[name]["micro_recall"]
            out.append(f"| `{name}` | {fam[name]['n']} | {top:.3f} | {got:.3f} "
                       f"| {got - top:+.3f} |")
        out.append("")

    bench = (cells.get("deterministic--plan-given") or {}).get("by_benchmark") or {}
    if bench:
        out.append("| benchmark | n | recall | precision | exact |")
        out.append("|---|---:|---:|---:|---:|")
        for name, roll in bench.items():
            out.append(f"| {name} | {roll['n']} | {roll['micro_recall']:.4f} | "
                       f"{roll['micro_precision']:.4f} | {roll['exact_match']:.4f} |")
        out.append("")
    return "\n".join(out)


def metric_values(metrics: dict[str, Any]) -> dict[str, Any]:
    """The manifest's ``metrics.values`` block, keyed so nothing is ambiguous."""
    cells = metrics["cells"]
    values: dict[str, Any] = {}
    for key, _label in ARM_ROWS:
        got = _row(cells.get(key, {}))
        if not got:
            continue
        slug = key.replace("--", "_").replace("-", "_")
        values[f"{slug}_micro_recall"] = {"mean": got["micro_recall"], "std": None, "n": got["n"]}
        values[f"{slug}_micro_precision"] = {"mean": got["micro_precision"], "std": None, "n": got["n"]}
        values[f"{slug}_exact_match"] = {"mean": got["exact_match"], "std": None, "n": got["n"]}

    ceiling = _row(cells.get("oracle--plan-given", {}))
    det = _row(cells.get("deterministic--plan-given", {}))
    if ceiling and det:
        values["ariadne_minus_oracle_recall"] = {
            "mean": round(det["micro_recall"] - ceiling["micro_recall"], 4),
            "std": None, "n": det["n"]}

    fam = (cells.get("deterministic--plan-given") or {}).get("by_family") or {}
    fam_top = (cells.get("oracle--plan-given") or {}).get("by_family") or {}
    if fam:
        gaps = {k: fam[k]["micro_recall"] - (fam_top.get(k) or {}).get("micro_recall", 0)
                for k in fam}
        values["families_matching_ceiling"] = {
            "mean": sum(1 for g in gaps.values() if g >= -0.01), "std": None, "n": len(gaps)}
        values["families_returning_nothing"] = {
            "mean": sum(1 for g in gaps.values() if g <= -0.99), "std": None, "n": len(gaps)}
    return values


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1
                   else "docs/evaluation/external-2026-08-21")
    metrics = json.loads((out_dir / "metrics.json").read_text())
    (EXPERIMENT / "data").mkdir(parents=True, exist_ok=True)
    (EXPERIMENT / "data" / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n")
    (EXPERIMENT / "tables").mkdir(parents=True, exist_ok=True)
    (EXPERIMENT / "tables" / "results.md").write_text(tables(metrics) + "\n")
    (EXPERIMENT / "data" / "manifest_metrics.json").write_text(
        json.dumps(metric_values(metrics), indent=2) + "\n")
    print(tables(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
