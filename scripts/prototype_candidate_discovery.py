#!/usr/bin/env python3
"""Replay the frozen EXP-2026-09-022 discovery diagnostic, never answer scoring."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.planner.cards import SourceCardView
from utils.planner.discovery_candidates import DiscoveryIndex
from utils.synthesis.grounding import normalize_id

EXPERIMENT = REPO / "docs/research/experiments/EXP-2026-09-022-portable-candidate-discovery"
RAW = REPO / "docs/evaluation/experiments/portable-candidate-discovery-2026-09-15"
ARMS = ("pooled", "fields", "graph")
BUDGETS = (1, 5, 10, 20)


def read_jsonl(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def mean(values):
    return sum(values) / len(values) if values else None


def gold_groups(record, index):
    """SCORER ONLY: translate this bank's public IDs to source-qualified keys.

    An anchor can have multiple canonical interpretations: score a match to any
    matching identity, restricted to the annotated source and labels where given.
    Keep unmatched gold in the denominator; do not silently score only easy IDs.
    """
    bank = record.get("bank")
    labels = set(record.get("anchor_labels") or [])
    groups = []
    for anchor in record.get("anchors") or []:
        matches = {
            key for key, doc in index.documents.items()
            if (bank not in {"attack", "capec"} or key[0] == bank)
            and (not labels or doc.label in labels)
            and anchor in {normalize_id(value) for value in doc.identifiers}
        }
        groups.append(matches)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, default=EXPERIMENT)
    parser.add_argument("--output", type=Path, default=RAW)
    parser.add_argument("--data-dir", type=Path, default=REPO / "data")
    args = parser.parse_args()
    experiment = args.experiment.resolve()
    manifest = yaml.safe_load((experiment / "manifest.yaml").read_text())
    if manifest["status"] in {"complete", "failed", "superseded"}:
        raise SystemExit("Use a new scaffolded experiment for a new run; completed records are immutable.")
    predictions_path = args.output.resolve() / "predictions.jsonl"
    if predictions_path.exists():
        raise SystemExit("Predictions already exist; choose a fresh --output to preserve the run.")
    started = time.perf_counter()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).strip())
    sources, inputs = {}, []
    for card_path in sorted((args.data_dir / "source_cards").glob("*.json")):
        raw = json.loads(card_path.read_text())
        if not raw.get("canonical_dir"):
            continue
        card = SourceCardView.from_card_dict(raw)
        canonical = Path(raw["canonical_dir"])
        if not canonical.is_absolute():
            canonical = REPO / canonical
        nodes, edges = canonical / "nodes.jsonl", canonical / "relationships.jsonl"
        sources[card.dataset] = (card, read_jsonl(nodes), read_jsonl(edges))
        inputs.extend([card_path, nodes, edges])
    if not sources:
        raise SystemExit("No cards with canonical graph paths found.")
    index = DiscoveryIndex(sources)
    variants_path = REPO / "docs/evaluation/variants-2026-08-29/variants.json"
    gold_path = variants_path.with_name("slot_gold.json")
    inputs.extend([variants_path, gold_path, REPO / "uv.lock"])
    variants = json.loads(variants_path.read_text())
    gold = {row["case_id"]: row for row in json.loads(gold_path.read_text())}
    groups = {case_id: gold_groups(record, index) for case_id, record in gold.items()}
    predictions = []
    for position, variant in enumerate(variants, 1):
        expected = [] if variant["tier"] == "T6" else groups.get(variant["case_id"], [])
        exact = index.exact_matches(variant["question"])
        result = {
            "case_id": variant["case_id"], "tier": variant["tier"],
            "question": variant["question"],
            "gold_anchors": [] if variant["tier"] == "T6" else gold.get(variant["case_id"], {}).get("anchors", []),
            "gold_groups": [sorted(group) for group in expected],
            "exact": [{"key": key, "reasons": reasons} for key, reasons in exact.items()],
            "arms": {},
        }
        for arm in ARMS:
            t0 = time.perf_counter()
            hits = index.search(variant["question"], arm=arm, top_k=max(BUDGETS))
            candidates = [{"key": h.key, "label": h.label, "name": h.name,
                           "score": h.score, "exact": h.exact, "views": h.views,
                           "matched_fields": h.matched_fields,
                           "context_neighbours": [c.neighbour for c in h.context],
                           "context_truncated": h.key in index.context_truncated} for h in hits]
            result["arms"][arm] = {"candidates": candidates, "latency_ms": (time.perf_counter() - t0) * 1000}
        predictions.append(result)
        if position % 100 == 0:
            print(f"Processed {position}/{len(variants)}", flush=True)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    predictions_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions))

    values, tiers = {}, {}

    def metric(key, value, n):
        if value is not None:
            values[key] = {"mean": value, "std": None, "n": n}

    for tier in sorted({row["tier"] for row in predictions}):
        rows = [row for row in predictions if row["tier"] == tier]
        eligible = [row for row in rows if row["gold_groups"]]
        tier_info = {"n": len(rows), "eligible": len(eligible), "no_anchor_gold": len(rows) - len(eligible)}
        metric(f"{tier}_eligible", len(eligible), len(rows))
        metric(f"{tier}_exact_candidate_presence", mean([bool(r["exact"]) for r in rows]), len(rows))
        metric(f"{tier}_exact_ambiguity", mean([len(r["exact"]) > 1 for r in rows]), len(rows))
        metric(f"{tier}_corpus_anchor_coverage", mean([mean([bool(g) for g in r["gold_groups"]]) for r in eligible]), len(eligible))
        metric(f"{tier}_exact_anchor_recall", mean([
            mean([bool(set(map(tuple, g)) & {tuple(h["key"]) for h in r["exact"]}) for g in r["gold_groups"]])
            for r in eligible]), len(eligible))
        for arm in ARMS:
            metric(f"{arm}_{tier}_candidate_presence", mean([bool(r["arms"][arm]["candidates"]) for r in rows]), len(rows))
            for k in BUDGETS:
                recalls, all_found = [], []
                for row in eligible:
                    keys = {tuple(h["key"]) for h in row["arms"][arm]["candidates"][:k]}
                    found = [bool(keys & set(map(tuple, group))) for group in row["gold_groups"]]
                    recalls.append(mean(found))
                    all_found.append(all(found))
                metric(f"{arm}_{tier}_anchor_recall_at_{k}", mean(recalls), len(eligible))
                metric(f"{arm}_{tier}_all_anchors_at_{k}", mean(all_found), len(eligible))
        tiers[tier] = tier_info
    metric("corpus_nodes", len(index.documents), 1)
    metric("graph_context_truncated_nodes", len(index.context_truncated), 1)
    missing = {case_id: gold[case_id].get("anchors") for case_id, gs in groups.items() if any(not g for g in gs)}
    metrics = {"values": values, "tiers": tiers, "missing_gold_cases": missing,
               "code_commit": commit, "dirty": dirty,
               "inputs": {str(p.relative_to(REPO)): digest(p) for p in inputs},
               "wall_clock_seconds": time.perf_counter() - started}
    (experiment / "data/metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    table = ["| Tier | Eligible / total | Pooled R@10 | Fields R@10 | Graph R@10 | Fields R@1 | Fields R@20 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for tier, info in tiers.items():
        if tier == "T6":
            continue
        keys = [f"{arm}_{tier}_anchor_recall_at_10" for arm in ARMS] + [f"fields_{tier}_anchor_recall_at_{k}" for k in (1, 20)]
        cells = [f"{values[key]['mean']:.4f}" if key in values else "n/a" for key in keys]
        table.append(f"| {tier} | {info['eligible']} / {info['n']} | " + " | ".join(cells) + " |")
    (experiment / "tables/discovery.md").write_text("\n".join(table) + "\n")
    manifest["status"] = "running"
    manifest["code"].update(commit=commit, dirty=dirty)
    manifest["metrics"]["values"] = values
    manifest["environment"]["python"] = platform.python_version()
    manifest["compute"]["wall_clock_hours"] = metrics["wall_clock_seconds"] / 3600
    manifest["data"]["n_examples"] = len(variants)
    (experiment / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    pointer = ["# Artifact pointers", "", "| Artifact | Path (repo-relative) | Bytes | SHA-256 | What it is |", "|---|---|---:|---|---|"]
    for path in inputs + [predictions_path]:
        pointer.append(f"| {path.name} | `{path.relative_to(REPO)}` | {path.stat().st_size} | `{digest(path)}` | Frozen diagnostic input/output |")
    (experiment / "data/POINTERS.md").write_text("\n".join(pointer) + "\n")
    print(f"Saved diagnostic to {experiment.relative_to(REPO)}", flush=True)


if __name__ == "__main__":
    main()
