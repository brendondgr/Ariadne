#!/usr/bin/env python3
"""Paired per-variant comparison of two harness arms, per tier, per bank.

``fixed`` = exact under the treatment and not under the control; ``broken`` =
the reverse. Also counts wrong-entity and dump flips, so an arm that trades a
wrong answer for an abstention is visible as such rather than as "recall
fell". Writes ``data/metrics.json`` under ``paired.<control>_vs_<treatment>``
and ``tables/paired_<control>_vs_<treatment>.md``.

    uv run python .../data/paired.py --control baseline --treatment anchor_first
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(EXP / "data"))

from arm_table import BANKS, FILES, TIERS  # noqa: E402


def load(bank: str, arm: str) -> dict[tuple[str, str], dict]:
    path = BANKS[bank] / FILES.get((bank, arm), f"scored_{arm}.json")
    if not path.exists():
        return {}
    return {(r["case_id"], r["question"]): r for r in json.loads(path.read_text())}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--control", required=True)
    ap.add_argument("--treatment", required=True)
    args = ap.parse_args()
    key = f"{args.control}_vs_{args.treatment}"
    result: dict[str, dict] = {}
    lines = ["| bank | tier | n | fixed | broken | wrong→ok | ok→wrong | dump→none | none→dump | abstain→answer | answer→abstain |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for bank in BANKS:
        c, t = load(bank, args.control), load(bank, args.treatment)
        if not c or not t:
            continue
        per: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for k, rc in c.items():
            rt = t.get(k)
            if rt is None or "records_exact" not in rc or "records_exact" not in rt:
                continue
            tier = rc["tier"]
            per[tier]["n"] += 1
            per[tier]["fixed"] += int(bool(rt["records_exact"]) and not rc["records_exact"])
            per[tier]["broken"] += int(bool(rc["records_exact"]) and not rt["records_exact"])
            per[tier]["wrong_ok"] += int(bool(rc["wrong_entity"]) and not rt["wrong_entity"])
            per[tier]["ok_wrong"] += int(bool(rt["wrong_entity"]) and not rc["wrong_entity"])
            per[tier]["dump_none"] += int(bool(rc["catalogue_dump"]) and not rt["catalogue_dump"])
            per[tier]["none_dump"] += int(bool(rt["catalogue_dump"]) and not rc["catalogue_dump"])
            per[tier]["abst_ans"] += int(bool(rc["abstained"]) and not rt["abstained"])
            per[tier]["ans_abst"] += int(bool(rt["abstained"]) and not rc["abstained"])
        result[bank] = {}
        for tier in TIERS:
            if tier not in per:
                continue
            p = per[tier]
            result[bank][tier] = dict(p)
            lines.append(f"| {bank} | {tier} | {p['n']} | {p['fixed']} | {p['broken']} | {p['wrong_ok']} | {p['ok_wrong']} | "
                         f"{p['dump_none']} | {p['none_dump']} | {p['abst_ans']} | {p['ans_abst']} |")
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / f"tables/paired_{key}.md").write_text("\n".join(lines) + "\n")
    metrics_path = EXP / "data/metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    metrics.setdefault("paired", {})[key] = result
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
