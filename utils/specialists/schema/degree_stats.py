#!/usr/bin/env python3
"""Reproduce the degree / facet statistics the extraction plan rests on.

The plan's central claim is that *the facet block is free*: no node has more than
a handful of distinct facets, so a ``describe`` payload is bounded at a fraction
of a kilobyte of adjacency summary regardless of the node's degree. This module
recomputes the numbers behind that claim from the canonical artifacts, and exists
as a standing guard: if a future change reintroduces a neighbour cap, the gap
between ``max_degree`` (large) and ``max_facet_rows`` (tiny) is the evidence that
the cap is destroying data on hub nodes rather than defending against size.

Run it directly for a human-readable table::

    uv run python -m utils.specialists.schema.degree_stats --data-dir data
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .build import canonical_dir, discover_datasets


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = pct / 100.0 * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    # Nearest-rank-ish: round the interpolated index for an integer degree.
    frac = rank - lower
    return int(round(sorted_values[lower] * (1 - frac) + sorted_values[upper] * frac))


def _median(sorted_values: list[int]) -> int:
    if not sorted_values:
        return 0
    mid = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) // 2


def degree_stats(data_dir: str | Path, dataset: str, cap: int = 25) -> dict:
    """Degree and facet-row distribution for one dataset's canonical graph."""
    canonical = canonical_dir(data_dir, dataset)
    id_to_label: dict[str, str] = {}
    with open(canonical / "nodes.jsonl", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            node = json.loads(line)
            if node.get("id"):
                id_to_label[node["id"]] = node.get("label", "")

    degree: dict[str, int] = defaultdict(int)
    facets: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    with open(canonical / "relationships.jsonl", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            edge = json.loads(line)
            src = edge.get("source_id")
            tgt = edge.get("target_id")
            rel = edge.get("type", "")
            src_label = id_to_label.get(src)
            tgt_label = id_to_label.get(tgt)
            if src in id_to_label:
                degree[src] += 1
                if tgt_label is not None:
                    facets[src].add((rel, "out", tgt_label))
            if tgt in id_to_label:
                degree[tgt] += 1
                if src_label is not None:
                    facets[tgt].add((rel, "in", src_label))

    degrees = sorted(degree.get(node_id, 0) for node_id in id_to_label)
    facet_rows = sorted(len(facets.get(node_id, set())) for node_id in id_to_label)
    edges = sum(degrees) // 2
    over_cap = sum(1 for d in degrees if d > cap)
    return {
        "dataset": dataset,
        "nodes": len(id_to_label),
        "edges": edges,
        "median_degree": _median(degrees),
        "p95_degree": _percentile(degrees, 95),
        "p99_degree": _percentile(degrees, 99),
        "max_degree": degrees[-1] if degrees else 0,
        "nodes_over_cap": over_cap,
        "cap": cap,
        "max_facet_rows": facet_rows[-1] if facet_rows else 0,
        "median_facet_rows": _median(facet_rows),
    }


def format_stats(rows: list[dict]) -> str:
    header = (
        f"{'dataset':<10} {'nodes':>7} {'edges':>7} {'med_deg':>7} "
        f"{'p95':>5} {'p99':>5} {'max_deg':>7} {'>cap':>6} "
        f"{'max_facets':>10} {'med_facets':>10}"
    )
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(
            f"{r['dataset']:<10} {r['nodes']:>7} {r['edges']:>7} "
            f"{r['median_degree']:>7} {r['p95_degree']:>5} {r['p99_degree']:>5} "
            f"{r['max_degree']:>7} {r['nodes_over_cap']:>6} "
            f"{r['max_facet_rows']:>10} {r['median_facet_rows']:>10}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--cap", type=int, default=25)
    parser.add_argument("--dataset", default=None, help="one dataset (default: all discovered)")
    args = parser.parse_args(argv)

    datasets = [args.dataset] if args.dataset else discover_datasets(args.data_dir)
    rows = [degree_stats(args.data_dir, ds, cap=args.cap) for ds in datasets]
    print(format_stats(rows))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
