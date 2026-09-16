#!/usr/bin/env python3
"""Step 0 of EXP-2026-09-023: the shipped name index against EXP-2026-09-022's prototype.

Re-derives, from EXP-2026-09-022's hash-pinned ``predictions.jsonl`` and the
shipped ``namesearch`` index, the comparison the 2026-09-15 review made in a
scratchpad. Same bank (the exposed 579 variants), same gold groups (the
prototype's scorer wrote them into every prediction row), same scoring rule
(mean fraction of a question's gold anchor groups represented in the top k).

Three lists are scored per variant:

* ``shipped``      — ``search_in`` on the variant's bank (both sources, union
                     sorted by score, for the federated bank), top 20;
* ``prototype``    — the prototype's pooled arm exactly as recorded;
* ``rank_only``    — the prototype's pooled BM25 without its exact-prepend step,
                     rebuilt in process, so the cost of that policy is visible.

Writes ``data/metrics.json`` (key ``review``) and ``tables/review.md``.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
sys.path.insert(0, str(REPO))

PREDICTIONS = REPO / "docs/evaluation/experiments/portable-candidate-discovery-2026-09-15/predictions.jsonl"
VARIANTS = REPO / "docs/evaluation/variants-2026-08-29/variants.json"
BUDGETS = (1, 5, 10, 20)


def main() -> int:
    from utils.planner.cards import SourceCardView
    from utils.planner.discovery_candidates import DiscoveryIndex
    from utils.specialists.schema.namesearch import search_in
    from utils.synthesis.grounding import normalize_id

    def rj(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    sources = {}
    for card_path in sorted((REPO / "data/source_cards").glob("*.json")):
        raw = json.loads(card_path.read_text())
        card = SourceCardView.from_card_dict(raw)
        canonical = REPO / raw["canonical_dir"]
        sources[card.dataset] = (card, rj(canonical / "nodes.jsonl"), rj(canonical / "relationships.jsonl"))
    prototype = DiscoveryIndex(sources)
    idmap: dict[tuple[str, str], set[tuple[str, str]]] = collections.defaultdict(set)
    for key, doc in prototype.documents.items():
        for value in doc.identifiers:
            idmap[(key[0], normalize_id(value))].add(key)

    bank = {r["case_id"]: r["bank"] for r in json.loads(VARIANTS.read_text())}
    preds = rj(PREDICTIONS)
    per: dict[str, dict[str, list[float]]] = collections.defaultdict(lambda: collections.defaultdict(list))
    for p in preds:
        groups = [set(map(tuple, g)) for g in p["gold_groups"]]
        if not groups:
            continue
        datasets = ["attack", "capec"] if bank[p["case_id"]] == "federated" else [bank[p["case_id"]]]
        scored = []
        for ds in datasets:
            for hit in search_in(ds, p["question"], top_k=20):
                keys = idmap.get((ds, normalize_id(hit.entity_id)))
                if keys:
                    scored.append((hit.score, sorted(keys)[0]))
        shipped = [k for _, k in sorted(scored, key=lambda x: -x[0])]
        recorded = [tuple(c["key"]) for c in p["arms"]["pooled"]["candidates"]]
        rank_only = [k for k, _ in prototype._indexes["pooled"].search(p["question"], 20)]  # noqa: SLF001
        for name, lst in (("shipped", shipped), ("prototype", recorded), ("rank_only", rank_only)):
            for k in BUDGETS:
                per[p["tier"]][f"{name}@{k}"].append(
                    sum(bool(set(lst[:k]) & g) for g in groups) / len(groups)
                )

    review: dict[str, dict] = {}
    lines = ["| tier | n | list | r@1 | r@5 | r@10 | r@20 |", "|---|---:|---|---:|---:|---:|---:|"]
    for tier in ("T1", "T2", "T3", "T4", "T5"):
        n = len(per[tier]["shipped@1"])
        review[tier] = {"n": n}
        for name in ("shipped", "prototype", "rank_only"):
            vals = {k: round(sum(per[tier][f"{name}@{k}"]) / n, 4) for k in BUDGETS}
            review[tier][name] = vals
            lines.append(f"| {tier} | {n} | {name} | " + " | ".join(f"{vals[k]:.4f}" for k in BUDGETS) + " |")
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / "tables/review.md").write_text("\n".join(lines) + "\n")

    metrics_path = EXP / "data/metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    metrics["review"] = {
        "what": "gold-anchor recall of three candidate lists on identical gold groups (EXP-2026-09-022 scorer)",
        "n_predictions": len(preds),
        "tiers": review,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
