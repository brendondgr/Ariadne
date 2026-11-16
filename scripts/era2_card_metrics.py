#!/usr/bin/env python3
"""EXP-2026-11-012: data/metrics.json from card_bank.json, questions.jsonl and proxy-read.json.

    uv run python scripts/era2_card_metrics.py <experiment>/data
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

d = Path(sys.argv[1])
cb = json.loads((d / "card_bank.json").read_text())
qs = [json.loads(line) for line in (d / "questions.jsonl").open()]
m: dict = {"total_questions": len(qs), "datasets": {}}
for ds, r in cb["datasets"].items():
    dq = [q for q in qs if q["task"]["source"] == ds]
    ans = Counter(q["card_gen"]["tier"] for q in dq if q["card_gen"]["kind"] == "answerable")
    drop = Counter()
    for k, v in r["dropped"].items():
        drop[k.split(":")[0]] += v
    yield_ = {t: {"kept": ans[t], "dropped": drop.get(t, 0),
                  "yield": round(ans[t] / (ans[t] + drop.get(t, 0)), 4) if ans[t] + drop.get(t, 0) else None}
              for t in sorted(ans)}
    m["datasets"][ds] = {
        "questions": r["questions"], "by_kind": r["by_kind"], "by_split": r["by_split"],
        "by_decision": r["by_decision"],
        "ambiguous_by_type": dict(Counter(q["card_gen"].get("ambiguity") for q in dq
                                          if q["card_gen"]["kind"] == "ambiguous")),
        "insufficient_diagnoses": dict(Counter(q["card_gen"].get("diagnosis") for q in dq
                                               if q["card_gen"]["kind"] == "insufficient")),
        "yield_by_tier": yield_, "dropped": r["dropped"],
        "G1_gold_reexecuted": r["gold_reexecuted_match"], "G2_split_overlap": len(r["split_overlap"]),
        "G3_leaks": len(r["leak_audit"]), "notes": r["notes"], "gold_size_median": r["gold_sizes"]["median"],
    }
m["G2_global_split_overlap"] = len(cb["global_split_overlap"])
pr = d / "proxy-read.json"
if pr.exists():
    items = json.loads(pr.read_text())["items"]
    by = defaultdict(lambda: [0, 0])
    for it in items:
        by[it["tier"]][0] += bool(it["fluent"])
        by[it["tier"]][1] += 1
    amb = [it for it in items if it["kind"] == "ambiguous"]
    m["E2_proxy"] = {
        "reader": json.loads(pr.read_text())["reader"], "n": len(items),
        "fluent": sum(bool(i["fluent"]) for i in items),
        "fluent_by_tier": {t: f"{a}/{n}" for t, (a, n) in sorted(by.items())},
        "ambiguous_truly": f"{sum(bool(i['truly_ambiguous']) for i in amb)}/{len(amb)}",
        "rejected": [{"n": i["n"], "kind": i["kind"], "note": i["note"]} for i in items
                     if not i["fluent"] or (i["kind"] == "ambiguous" and not i["truly_ambiguous"])],
    }
m["banks"] = cb.get("banks")
(d / "metrics.json").write_text(json.dumps(m, indent=1))
print(json.dumps({k: v for k, v in m.items() if k != "banks"}, indent=1)[:4000])
