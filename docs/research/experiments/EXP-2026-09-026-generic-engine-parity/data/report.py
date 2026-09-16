#!/usr/bin/env python3
"""Tables for EXP-2026-09-026 from the scored files only: control vs treatment, per tier, both banks.

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

ARMS = ("anchor_first", "generic", "form_execute", "generic_form")
PAIRS = (("anchor_first", "generic"), ("form_execute", "generic_form"))


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
    # per-category paired counts on the exposed bank (case id's middle token)
    cat_lines = ["| category | n | templates only | generic only | both | neither |", "|---|---:|---:|---:|---:|---:|"]
    ex = BANKS["exposed"]
    a_path, g_path = ex / "scored_form_execute.json", ex / "scored_generic_form.json"
    if a_path.exists() and g_path.exists():
        a = {(r["case_id"], r["question"]): r for r in json.loads(a_path.read_text())}
        g = {(r["case_id"], r["question"]): r for r in json.loads(g_path.read_text())}
        cats: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
        for k, ra in a.items():
            rg = g.get(k)
            if rg is None or ra["tier"] not in ("T1", "T2", "T3"):
                continue
            cat = k[0].split("-")[1]
            ta, tg = bool(ra["records_exact"]), bool(rg["records_exact"])
            cats[cat]["n"] += 1
            cats[cat]["both" if ta and tg else "t_only" if ta else "g_only" if tg else "neither"] += 1
        for cat, c in sorted(cats.items(), key=lambda kv: -(kv[1]["t_only"] - kv[1]["g_only"])):
            cat_lines.append(f"| {cat} | {c['n']} | {c['t_only']} | {c['g_only']} | {c['both']} | {c['neither']} |")
        paired["exposed_by_category_T1-T3"] = {cat: dict(c) for cat, c in cats.items()}
    (EXP / "tables").mkdir(exist_ok=True)
    (EXP / "tables/by_category.md").write_text("\n".join(cat_lines) + "\n")
    (EXP / "tables/arms.md").write_text("\n".join(a_lines) + "\n")
    (EXP / "tables/paired.md").write_text("\n".join(p_lines) + "\n")
    gaps = {}
    for bank in arms:
        if "form_execute" in arms[bank] and "generic_form" in arms[bank]:
            for tier in ("T1", "T2", "T3"):
                if tier in arms[bank]["form_execute"] and tier in arms[bank]["generic_form"]:
                    gaps[f"records_exact_{tier}_gap_generic_minus_templates_{bank}"] = round(
                        arms[bank]["generic_form"][tier]["records_exact"] - arms[bank]["form_execute"][tier]["records_exact"], 4)
    (EXP / "data/metrics.json").write_text(json.dumps({"arms": arms, "paired": paired, "gaps": gaps}, indent=2) + "\n")
    print("\n".join(a_lines)); print(); print("\n".join(p_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
