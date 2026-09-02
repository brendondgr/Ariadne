#!/usr/bin/env python3
"""Assemble the expansion bank and split it before anyone can see a score.

Two properties this file exists to guarantee:

**The split is drawn blind.** Dev/holdout membership is `sha256(spec_id)`
parity — a function of the question's identity and nothing else. It cannot be
influenced by which half scores better, because it is fixed before anything has
been run. `make_bank`'s own record says why that matters: holdout v1 found two
defects, both were fixed, and it stopped being blind. A split that is cheap and
mechanical is the only kind that survives contact with a failing result.

**A skewed bank carries its own caveat.** The draw deliberately over-samples the
under-represented corners of the graph, so pooled accuracy over it is not a
natural-distribution estimate. The reweighting table travels in the bank's
metadata, and so does the sentence saying not to quote the pooled figure without
it.

    uv run python scripts/build_bank.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.render_questions import DEFAULT_SPECS, load_specs
from utils.specialists.evalset import spec_bank

BANK_DIR = Path("docs/evaluation/composition/bank")
CENSUS = Path("docs/evaluation/schema-census/attack-19.0-capec-3.9/census.json")


def split_of(spec_id: str) -> str:
    """Dev or holdout, from the id alone. Deterministic, and blind by design."""
    return "dev" if int(hashlib.sha256(spec_id.encode()).hexdigest(), 16) % 2 == 0 else "holdout"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--selection", type=Path, default=BANK_DIR / "selection.json")
    parser.add_argument("--ingested", type=Path, default=BANK_DIR / "ingested.json")
    parser.add_argument("--out", type=Path, default=BANK_DIR)
    args = parser.parse_args()

    selection = json.loads(args.selection.read_text())
    ingested = json.loads(args.ingested.read_text())
    census = json.loads(CENSUS.read_text())
    specs = {s.id: s for s in load_specs(args.specs)}

    kept = [r for r in ingested["questions"] if r["ok"] and r["question"]]
    pairs = [(specs[r["spec_id"]], r["question"], r["register"]) for r in kept]

    bank = spec_bank.to_bank(
        pairs,
        attack_version=census["sources"]["attack"]["version"],
        capec_version=census["sources"]["capec"]["version"],
        author_model=ingested["report"]["author_model"],
        seed=selection["seed"],
        note="Expansion bank. Deliberately over-samples under-represented shapes; "
             "pooled accuracy is NOT a natural-distribution estimate — reweight "
             "per-shape scores using meta.reweighting.census_instances.",
    )

    for entry in bank["questions"]:
        entry["split"] = split_of(entry["spec_id"])

    bank["meta"]["reweighting"] = selection["reweighting"]
    bank["meta"]["stratification"] = {
        k: selection[k]
        for k in ("tier_quota", "by_tier", "by_source", "by_width_band", "by_direction")
        if k in selection
    }
    bank["meta"]["split_rule"] = "sha256(spec_id) parity; drawn before any run"
    bank["meta"]["rejected"] = ingested["report"]["rejection_reasons"]
    bank["meta"]["keep_rate"] = ingested["report"]["keep_rate"]
    bank["meta"]["paraphrase_specs"] = len(selection["paraphrase_specs"])

    splits = Counter(q["split"] for q in bank["questions"])
    tiers = Counter(q["d_tier"] for q in bank["questions"])
    shapes = {s for q in bank["questions"] for s in q["spec"]["shapes"]}
    census_shapes = {e["triple"] for e in census["edges"]}

    path = args.out / "bank.json"
    spec_bank.write(bank, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.out / "MANIFEST.md").write_text(
        f"""# Expansion bank

| | |
|---|---|
| questions | {len(bank['questions'])} |
| dev / holdout | {splits['dev']} / {splits['holdout']} |
| distinct specs | {len({q['spec_id'] for q in bank['questions']})} |
| census shapes covered | {len(shapes & census_shapes)} / {len(census_shapes)} |
| author | {bank['meta']['author_model']} (subagent) |
| keep rate | {bank['meta']['keep_rate']:.1%} |
| sha256 | `{digest}` |

By tier: {dict(sorted(tiers.items()))}

**The split is `sha256(spec_id)` parity, drawn before anything was run.** It
cannot have been influenced by which half scores better.

**This bank is deliberately skewed** toward under-represented shapes. Pooled
accuracy over it is not a natural-distribution estimate. Report per-shape, and
reweight using `meta.reweighting.census_instances` for a comparable figure.
""")

    print(f"bank -> {path}")
    print(f"  {len(bank['questions'])} questions, "
          f"{len({q['spec_id'] for q in bank['questions']})} distinct specs")
    print(f"  dev {splits['dev']} / holdout {splits['holdout']}")
    print(f"  by tier: {dict(sorted(tiers.items()))}")
    print(f"  census shapes covered: {len(shapes & census_shapes)}/{len(census_shapes)}")
    print(f"  sha256: {digest}")


if __name__ == "__main__":
    main()
