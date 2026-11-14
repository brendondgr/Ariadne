"""EXP-2026-11-005: the part-B kill rule, part-A comparisons, and the exploratory miss taxonomy.

    uv run python -m utils.killtests.t2c.analysis

The taxonomy (exploratory, post hoc): for each part-B question where free Cypher (3-shot) was
right and typed v2 (3-shot, Cypher backend) was wrong, the gold Cypher's features are matched by
regular expressions. A miss whose gold uses a feature the format has no operator for is a
**format gap**; otherwise it is a **fill error** (the format could say it; the model did not).
"""

from __future__ import annotations

import json
import re
from collections import Counter

from ..config import REPO
from ..stages import atomic_write_json
from ..t2c import load as T
from .run import OUT, REPAIR

EXP = REPO / "docs/research/experiments/EXP-2026-11-005-typed-v2-second-benchmark"

#: gold-Cypher features the v2 format has no operator for.
GAP = {
    "variable_length_path": r"\[[^\]]*\*[^\]]*\]",
    "list_functions": r"\b(collect|size|head|last|reduce|range|keys|labels|nodes|relationships)\s*\(|\bUNWIND\b|\[\s*\w+\s+IN\b",
    "arithmetic_in_return": r"RETURN\b[^\n]*?(\w\)?\s*[\+\-\*/]\s*\(?\w)",
    "case": r"\bCASE\b",
    "string_functions": r"\b(toLower|toUpper|substring|split|replace|trim|left|right|toString)\s*\(",
    "exists_or_negated_pattern": r"\bEXISTS\s*[\{\(]|\bNOT\s*\(\s*\(|\bNOT\s+EXISTS",
    "temporal_functions": r"\b(duration|date\.truncate|datetime\.truncate)\b",
    "several_aggregates": None,  # computed below
    "aggregate_then_filter": r"\bWITH\b[^\n]*\b(count|sum|avg|min|max)\s*\([^\n]*\bWHERE\b",
    "with_chain": None,  # two or more WITH clauses
}
_AGG = re.compile(r"\b(count|sum|avg|min|max|collect)\s*\(", re.I)


def features(cy: str) -> list[str]:
    out = []
    for name, rx in GAP.items():
        if rx and re.search(rx, cy, re.I):
            out.append(name)
    if len(_AGG.findall(cy)) >= 2:
        out.append("several_aggregates")
    if len(re.findall(r"\bWITH\b", cy, re.I)) >= 2:
        out.append("with_chain")
    return out


def verdict_b(sc: dict) -> dict:
    per = {}
    for tag, b in sc["by_model"].items():
        a = b["arms"]
        tc, tg = a["typed2-3shot-cypher"]["exact_records"], a["typed2-3shot-gremlin"]["exact_records"]
        fc, fg = a["free-cypher-3shot"]["exact_records"], a["free-gremlin-3shot"]["exact_records"]
        per[tag] = {"typed2_3shot_cypher": tc, "typed2_3shot_gremlin": tg, "free_cypher_3shot": fc,
                    "free_gremlin_3shot": fg,
                    "H1_backend_independent": abs(tc - tg) <= 0.02 + 1e-9,
                    "H2_beats_free_gremlin": tg - fg >= 0.10 - 1e-9,
                    "H3_not_worse_than_free_cypher": tc >= fc - 0.05 - 1e-9,
                    "ci_typed_gremlin_minus_free_gremlin": b["diffs"]["typed2-3shot-gremlin_minus_free-gremlin-3shot"]["ci95"],
                    "ci_typed_cypher_minus_free_cypher": b["diffs"]["typed2-3shot-cypher_minus_free-cypher-3shot"]["ci95"],
                    "repair": {k: a[f"{REPAIR}-{k}"]["exact_records"] for k in ("cypher", "gremlin")}}
    killed = any(not v["H2_beats_free_gremlin"] for v in per.values()) or \
        all(not v["H3_not_worse_than_free_cypher"] for v in per.values())
    return {"rule": "killed if H2 fails for any model or H3 fails for every model (3-shot); H1 reported",
            "inputs": per, "verdict": "killed" if killed else "survives",
            "H1_holds_all": all(v["H1_backend_independent"] for v in per.values())}


def taxonomy() -> dict:
    gold = {q["qid"]: q for q in json.loads((T.OUT / "gold.json").read_text())["questions"]}
    ex = json.loads((OUT / "B-execute.json").read_text())["executions"]
    res = {}
    for tag in sorted({k.split("|")[2] for k in ex}):
        misses, gaps, feats, status = [], 0, Counter(), Counter()
        for qid, q in gold.items():
            fc = ex.get(f"{qid}|cypher-3shot|{tag}", {}).get("correct")
            t = ex.get(f"{qid}|typed2-3shot|{tag}", {})
            if fc and not t.get("cypher_ok"):
                f = features(q["gold_cypher"])
                misses.append(qid)
                status[t.get("status")] += 1
                if f:
                    gaps += 1
                    feats.update(f)
        res[tag] = {"typed_missed_free_cypher_right": len(misses), "format_gap": gaps,
                    "fill_error": len(misses) - gaps, "gap_features": dict(feats.most_common()),
                    "typed_status_on_these": dict(status)}
    gap_share = Counter()
    for q in gold.values():
        if features(q["gold_cypher"]):
            gap_share["uses_a_gap_feature"] += 1
    res["benchmark"] = {"n": len(gold), "gold_uses_a_gap_feature": gap_share["uses_a_gap_feature"]}
    return res


def main() -> int:
    a = json.loads((OUT / "A-score.json").read_text())
    b = json.loads((OUT / "B-score.json").read_text())
    vb = verdict_b(b)
    tx = taxonomy()
    va = {}
    for tag, blk in a["by_model"].items():
        arms = blk["arms"]
        va[tag] = {k: arms[k]["exact_records"] for k in ("typed2-3shot-cypher", "typed2-3shot-gremlin", REPAIR + "-cypher",
                                                          "typed-3shot-cypher", "free-cypher-3shot", "free-gremlin-3shot")
                   if k in arms}
        va[tag]["A1_not_worse_than_v1"] = arms["typed2-3shot-cypher"]["exact_records"] >= arms["typed-3shot-cypher"]["exact_records"] - 0.02
        va[tag]["union_v2"] = arms["typed2-3shot-cypher"]["by_group"].get("special_union")
        va[tag]["status_typed2_3shot"] = blk["status"]["typed2-3shot"]
    data = EXP / "data"
    data.mkdir(parents=True, exist_ok=True)
    atomic_write_json(data / "metrics.json", {"A": a, "B": b})
    atomic_write_json(data / "killrule.json", {"B": vb, "A": va})
    atomic_write_json(data / "taxonomy.json", tx)
    print(json.dumps({"B": {k: vb[k] for k in ("verdict", "H1_holds_all", "inputs")}, "A": va, "taxonomy": tx},
                     indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
