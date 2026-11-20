#!/usr/bin/env python3
"""Count the retrieval shapes of Ariadne's questions (Era 2, Step 9, Phase A).

Which operations do the questions we have actually need? The rubric is
``docs/evaluation/shape-count-2026-11/RUBRIC.md``. Ariadne's own banks carry
structure and are labelled here by code. External questions, and the
out-of-coverage questions of Step 6, are labelled by two labellers against the
rubric. This script draws the items they label, and then merges every label
into the counts.

    uv run --with pyarrow python scripts/count_question_shapes.py sample
    uv run python scripts/count_question_shapes.py count

Only the banks in ``SOURCES`` are opened, and ``open_bank`` refuses anything
else. The sealed held-out banks are never read (the unit test checks this).

Neither external benchmark's text is committed. CTIBench is CC-BY-NC-SA, and
D-020 keeps both out of the repository. The items to label go to
``.cache/shape-count/``, which is ignored. The committed label files carry row
ids and labels only.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs/evaluation/shape-count-2026-11"
CACHE = REPO / ".cache/shape-count"
EXTERNAL = REPO / ".cache/external-benchmarks"
SEED = 20261120
ATTACKQA_SAMPLE = 600
ATTACKQA_MIN_PER_FAMILY = 5
SECOND_LABELLER_SHARE = 0.20

#: Every bank this script may open, relative to the repository.
SOURCES: dict[str, str] = {
    "dev": "docs/evaluation/composition/bank/bank-dev.json",
    "gold": "docs/evaluation/experiments/typed-engine-fixes-2026-11-20/variants/reference.json",
    "variants": "docs/evaluation/variants-2026-09-15/variants.json",
    **{f"step6-{d}-{k}": f"docs/evaluation/banks/card-sonnet-2026-11-16-{d}-{k}-tuning/bank.json"
       for d in ("attack", "capec") for k in ("grounding", "relation_choice", "exit")},
}
SEALED = re.compile(r"held-?out|holdout|fresh", re.I)

#: The operator order the coverage curve follows.
STAGES = ["today", "1", "2", "3", "4", "5", "6", "7", "8", "gaps", "outside"]
CODES = {
    "T.describe": "today", "T.walk": "today", "T.count": "today", "T.scan": "today",
    "T.common": "today", "T.eqfilter": "today", "T.refuse": "today",
    "O1.filter": "1", "O2.aggregate": "2", "O3.rank": "3", "O4.verify": "4",
    "O5.typescan": "5", "O6.groupby": "6", "O7a.edgefilter": "7", "O7b.time": "7",
    "O7c.union": "7", "O7d.absence": "7", "O8.path": "8",
    "G1.multiagg": "gaps", "G2.groupbyvalue": "gaps", "G3.twovars": "gaps",
    "X.textsearch": "outside", "X.extract": "outside", "X.similar": "outside",
    "X.knowledge": "outside", "X.other": "outside",
}


class SealedBank(PermissionError):
    """Raised when anything outside ``SOURCES``, or a sealed bank, is opened."""


def open_bank(name: str) -> Any:
    """Load one allowlisted bank by its key in ``SOURCES``."""
    if name not in SOURCES:
        raise SealedBank(f"{name!r} is not an allowlisted source")
    rel = SOURCES[name]
    if SEALED.search(rel):
        raise SealedBank(f"{rel} looks sealed; refusing to open it")
    return json.loads((REPO / rel).read_text())


def stage_of(codes: Iterable[str]) -> str:
    """The first stage at which every code is covered."""
    stages = [CODES[c] for c in codes]
    if not stages:
        raise ValueError("a question needs at least one code")
    if "outside" in stages:
        return "outside"
    return max(stages, key=STAGES.index)


# --- deterministic labels ---------------------------------------------------

def label_dev() -> list[dict[str, Any]]:
    out = []
    for q in open_bank("dev")["questions"]:
        spec = q["spec"]
        codes = {"T.walk" if spec["steps"] else "T.describe"}
        for f in spec.get("filters") or []:
            codes.add("T.eqfilter" if f.get("op") == "eq" else "O1.filter")
        out.append({"source": "dev", "id": q["id"], "codes": sorted(codes), "by": "spec"})
    return out


GOLD_TEMPLATE = {"describe": "T.describe", "label_scan": "T.scan", "capec_scan": "T.scan",
                 "tactic_technique_mitigations": "T.common", "boundary_refusal": "T.refuse"}


def label_gold() -> list[dict[str, Any]]:
    """Gold 120 by template. The 579 variants inherit their gold question's codes."""
    gold = {}
    for r in open_bank("gold"):
        code = GOLD_TEMPLATE.get(r.get("expected_template") or "", "T.walk")
        gold[r["case_id"]] = {"source": "gold", "id": r["case_id"], "codes": [code], "by": "template"}
    variants = [{"source": "variants", "id": f"{v['case_id']}::{v['tier']}",
                 "codes": gold[v["case_id"]]["codes"], "by": "inherited"}
                for v in open_bank("variants")]
    return list(gold.values()) + variants


def step6_rows() -> list[tuple[str, dict[str, Any]]]:
    return [(k, q) for k in SOURCES if k.startswith("step6-") for q in open_bank(k)["questions"]]


def label_step6() -> list[dict[str, Any]]:
    return [{"source": k, "id": q["id"], "codes": ["T.walk"], "by": "slot"}
            for k, q in step6_rows() if q["card_gen"].get("slot")]


# --- items for the labellers -----------------------------------------------

def _attackqa_rows() -> list[dict[str, Any]]:
    sys.path.insert(0, str(REPO))
    from utils.evaluation.external.fetch import read_attackqa
    return list(read_attackqa(EXTERNAL / "attackqa.parquet"))


def _cti_ate_rows() -> list[dict[str, str]]:
    sys.path.insert(0, str(REPO))
    from utils.evaluation.external.fetch import read_cti_ate
    return read_cti_ate(EXTERNAL / "cti-ate.tsv")


def allocate(sizes: dict[str, int], total: int, floor: int) -> dict[str, int]:
    """Split ``total`` across families in proportion to size, with a floor.

    Largest-remainder rounding. A family smaller than the floor is taken whole.
    """
    fixed = {f: min(n, floor) for f, n in sizes.items()}
    left = total - sum(fixed.values())
    big = {f: n - fixed[f] for f, n in sizes.items() if n > fixed[f]}
    pool = sum(big.values())
    raw = {f: left * n / pool for f, n in big.items()}
    take = {f: int(v) for f, v in raw.items()}
    for f in sorted(raw, key=lambda f: (raw[f] - take[f], f), reverse=True)[: left - sum(take.values())]:
        take[f] += 1
    return {f: fixed[f] + take.get(f, 0) for f in sizes}


def build_items() -> dict[str, Any]:
    rng = random.Random(SEED)
    rows = _attackqa_rows()
    fams: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        fams[r["source"]].append(r)
    sizes = {f: len(v) for f, v in sorted(fams.items())}
    plan = allocate(sizes, ATTACKQA_SAMPLE, ATTACKQA_MIN_PER_FAMILY)
    items = []
    for fam in sorted(fams):
        for r in rng.sample(sorted(fams[fam], key=lambda r: r["__index_level_0__"]), plan[fam]):
            items.append({"item": f"attackqa:{r['__index_level_0__']}", "source": "attackqa",
                          "family": fam, "question": r["question"]})
    for i, r in enumerate(_cti_ate_rows()):
        items.append({"item": f"cti-ate:{i}", "source": "cti-ate", "family": "cti-ate",
                      "question": r["Prompt"]})
    for k, q in step6_rows():
        if not q["card_gen"].get("slot"):
            items.append({"item": f"{k}:{q['id']}", "source": k, "family": q["card_gen"]["kind"],
                          "question": q["question"]})
    second = sorted(rng.sample([it["item"] for it in items], round(SECOND_LABELLER_SHARE * len(items))))
    return {"items": items, "second": second, "family_sizes": sizes, "allocation": plan}


# --- agreement and counts --------------------------------------------------

def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if n == 0:
        raise ValueError("no items")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def read_labels(path: Path) -> dict[str, list[str]]:
    out = {}
    for line in path.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            bad = [c for c in r["codes"] if c not in CODES]
            if bad:
                raise ValueError(f"{path.name} {r['item']}: unknown codes {bad}")
            out[r["item"]] = sorted(set(r["codes"]))
    return out


def curve(rows: list[dict[str, Any]], weight: dict[str, float] | None = None) -> dict[str, Any]:
    """Cumulative coverage per stage, optionally weighted per row."""
    w = [(weight or {}).get(r.get("family", ""), 1.0) for r in rows]
    tot = sum(w)
    by = collections.Counter()
    for r, x in zip(rows, w):
        by[stage_of(r["codes"])] += x
    cum, run = {}, 0.0
    for s in STAGES:
        run += by[s]
        cum[s] = round(run / tot, 4) if tot else None
    codes = collections.Counter()
    for r, x in zip(rows, w):
        for c in r["codes"]:
            codes[c] += x
    return {"n": len(rows), "weighted_n": round(tot, 1), "stage_share": {s: round(by[s] / tot, 4) for s in STAGES},
            "cumulative": cum, "code_share": {c: round(v / tot, 4) for c, v in sorted(codes.items())}}


def count() -> dict[str, Any]:
    meta = json.loads((OUT / "items.json").read_text())
    a = read_labels(OUT / "labels-a.jsonl")
    b = read_labels(OUT / "labels-b.jsonl")
    adj = read_labels(OUT / "adjudicated.jsonl") if (OUT / "adjudicated.jsonl").exists() else {}
    items = {it["item"]: it for it in meta["items"]}
    missing = sorted(set(items) - set(a))
    if missing:
        raise SystemExit(f"labeller A missing {len(missing)} items, e.g. {missing[:3]}")
    if sorted(b) != sorted(meta["second"]):
        raise SystemExit("labeller B's items differ from the drawn 20%")
    sa = [stage_of(a[i]) for i in meta["second"]]
    sb = [stage_of(b[i]) for i in meta["second"]]
    disagree = [i for i in meta["second"] if stage_of(a[i]) != stage_of(b[i])]
    unresolved = [i for i in disagree if i not in adj]
    final = {i: adj.get(i, a[i]) for i in items}
    labelled = [{"source": items[i]["source"], "family": items[i]["family"], "id": i, "codes": final[i],
                 "by": "adjudicated" if i in adj else "labeller-a"} for i in items]
    det = label_dev() + label_gold() + label_step6()
    rows = det + labelled
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in rows:
        g = "step6" if r["source"].startswith("step6-") else r["source"]
        groups[g].append(r)
    sizes, plan = meta["family_sizes"], meta["allocation"]
    family_weight = {f: sizes[f] / plan[f] for f in sizes}
    result = {
        "agreement": {"n": len(sa), "kappa_stage": round(cohen_kappa(sa, sb), 4),
                      "exact_stage": round(sum(x == y for x, y in zip(sa, sb)) / len(sa), 4),
                      "exact_codes": round(sum(a[i] == b[i] for i in meta["second"]) / len(sa), 4),
                      "stage_disagreements": disagree, "unresolved": unresolved},
        "sources": {g: curve(v) for g, v in sorted(groups.items())},
        "attackqa_weighted": curve(groups["attackqa"], family_weight),
        "own_banks": curve([r for g in ("dev", "gold", "step6") for r in groups[g]]),
        "external_retrieval": curve([r for g in ("attackqa", "cti-ate") for r in groups[g]
                                     if stage_of(r["codes"]) != "outside"]),
        "attackqa_weighted_retrieval": curve([r for r in groups["attackqa"] if stage_of(r["codes"]) != "outside"],
                                             family_weight),
        "attackqa_by_family": {f: curve([r for r in groups["attackqa"] if r["family"] == f])
                               for f in sorted(sizes)},
    }
    (OUT / "per_question.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (OUT / "counts.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["sample", "count"])
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    if a.cmd == "sample":
        meta = build_items()
        CACHE.mkdir(parents=True, exist_ok=True)
        (CACHE / "items.jsonl").write_text("".join(json.dumps(it) + "\n" for it in meta["items"]))
        (CACHE / "items-second.jsonl").write_text("".join(
            json.dumps(it) + "\n" for it in meta["items"] if it["item"] in set(meta["second"])))
        public = {"seed": SEED, "family_sizes": meta["family_sizes"], "allocation": meta["allocation"],
                  "second": meta["second"],
                  "items": [{k: it[k] for k in ("item", "source", "family")} for it in meta["items"]]}
        (OUT / "items.json").write_text(json.dumps(public, indent=1, sort_keys=True) + "\n")
        print(f"{len(meta['items'])} items to label; {len(meta['second'])} for the second labeller")
    else:
        r = count()
        print(json.dumps({"agreement": r["agreement"] | {"stage_disagreements": len(r["agreement"]["stage_disagreements"])},
                          "own_banks": r["own_banks"]["cumulative"],
                          "external_retrieval": r["external_retrieval"]["cumulative"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
