#!/usr/bin/env python3
"""Tables for EXP-2026-09-028 from the scored files only: control vs treatment, per tier, both banks.

Reuses EXP-2026-09-023's tabulation (``arm_table.tier_means``) so the two
records compute every metric the same way. Writes ``data/metrics.json`` and
``tables/arms.md`` / ``tables/paired.md``.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "docs/research/experiments/EXP-2026-09-023-anchor-hygiene-and-q59/data"))

from arm_table import BANKS, TIERS, tier_means  # noqa: E402

ARMS = ("form_execute", "disclosed")
PAIRS = (("form_execute", "disclosed"),)


def main() -> int:
    arms: dict[str, dict] = {}
    paired: dict[str, dict] = {}
    a_lines = ["| bank | arm | tier | n | records_exact | records_recall | recall (no dump) | abstained | wrong_entity | catalogue_dump |",
               "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    p_lines = ["| bank | pair | tier | n | fixed | broken | recall ↑ (≥0.1) | recall ↓ (≥0.1) | none→dump | dump→none | mean Δrecall |",
               "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for bank, bank_dir in BANKS.items():
        rows = {}
        for arm in ARMS:
            path = bank_dir / f"scored_{arm}.json"
            if not path.exists():
                continue
            rows[arm] = json.loads(path.read_text())
            means = tier_means(rows[arm])
            arms.setdefault(bank, {})[arm] = means
            for tier, m in means.items():
                a_lines.append(f"| {bank} | {arm} | {tier} | {m['n']} | {m['records_exact']:.4f} | {m['records_recall']:.4f} | "
                               f"{m['recall_no_dump']:.4f} | {m['abstained']:.4f} | {m['wrong_entity']:.4f} | {m['catalogue_dump']:.4f} |")
        for CONTROL, TREATMENT in PAIRS:
          if CONTROL not in rows or TREATMENT not in rows:
            continue
          c = {(r["case_id"], r["question"]): r for r in rows[CONTROL]}
          t = {(r["case_id"], r["question"]): r for r in rows[TREATMENT]}
          per: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
          deltas: dict[str, list[float]] = collections.defaultdict(list)
          for k, rc in c.items():
              rt = t.get(k)
              if rt is None or "records_exact" not in rc or "records_exact" not in rt:
                  continue
              tier = rc["tier"]
              d = float(rt.get("records_recall") or 0.0) - float(rc.get("records_recall") or 0.0)
              deltas[tier].append(d)
              per[tier]["n"] += 1
              per[tier]["fixed"] += int(bool(rt["records_exact"]) and not rc["records_exact"])
              per[tier]["broken"] += int(bool(rc["records_exact"]) and not rt["records_exact"])
              per[tier]["up"] += int(d >= 0.1)
              per[tier]["down"] += int(d <= -0.1)
              per[tier]["none_dump"] += int(bool(rt["catalogue_dump"]) and not rc["catalogue_dump"])
              per[tier]["dump_none"] += int(bool(rc["catalogue_dump"]) and not rt["catalogue_dump"])
          paired.setdefault(bank, {})[f"{CONTROL}_vs_{TREATMENT}"] = {}
          for tier in TIERS:
              if tier not in per:
                  continue
              p = per[tier]
              mean_d = round(sum(deltas[tier]) / len(deltas[tier]), 4)
              paired[bank][f"{CONTROL}_vs_{TREATMENT}"][tier] = {**dict(p), "mean_delta_recall": mean_d}
              p_lines.append(f"| {bank} | {CONTROL}→{TREATMENT} | {tier} | {p['n']} | {p['fixed']} | {p['broken']} | {p['up']} | {p['down']} | "
                             f"{p['none_dump']} | {p['dump_none']} | {mean_d:+.4f} |")
    # disclosed answers: how many carried a resolution line, and of those how many were exact / wrong
    disc = {}
    for bank, bank_dir in BANKS.items():
        path = bank_dir / "scored_disclosed.json"
        if not path.exists():
            continue
        rows = json.loads(path.read_text())
        per = collections.defaultdict(collections.Counter)
        for r in rows:
            block = (r.get("rewrite") or {}).get("disclosed_anchor") if isinstance(r.get("rewrite"), dict) else None
            if not block:
                continue
            per[r["tier"]]["disclosed"] += 1
            per[r["tier"]]["exact"] += int(bool(r.get("records_exact")))
            per[r["tier"]]["wrong"] += int(bool(r.get("wrong_entity")))
        disc[bank] = {t: dict(c) for t, c in per.items()}
    paired["disclosed_answers"] = disc
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / "tables/arms.md").write_text("\n".join(a_lines) + "\n")
    (EXP / "tables/paired.md").write_text("\n".join(p_lines) + "\n")
    (EXP / "data/metrics.json").write_text(json.dumps({"arms": arms, "paired": paired}, indent=2) + "\n")
    print("\n".join(a_lines)); print(); print("\n".join(p_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
