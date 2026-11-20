"""``records_exact`` with the gold question's own ids removed from both sides (EXP-2026-11-018).

    uv run python scripts/era2_anchor_exact.py --runs <run root> --arms E,T-lazy,T-full,T-lazy-G \
        [--merge <metrics.json>]

``records_exact`` compares the answer's entity ids with the reference's. Whether the
question's own anchor is among them depends on the record shape of the reference
template: the reference for "which techniques did campaign C0027 use" lists the 10
techniques without C0027, while the one for "what mitigates T1047" lists T1047 with its
mitigations. A typed ``expand`` always returns its anchor, so a correct typed answer to the
first question is scored inexact; English plans route to the same templates as the
reference and never meet this. In EXP-2026-11-017, 9 of T-lazy's 49 inexact T0 answers
differed from the reference by the anchor alone.

The measure here removes, from both the answer and the reference, every id written in the
GOLD question (the case's anchor). It is defined by the case, not by the plan, so it treats
every arm alike, and it can only differ from ``records_exact`` on answers that differ from
the reference by anchor ids. Prints one line per arm and, with ``--merge``, records
``anchor_exact[<arm>][<tier>] = {"exact": n, "anchor_exact": n, "n": n}``.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

IDS = re.compile(r"\b(?:T\d{4}(?:\.\d{3})?|TA\d{4}|[GSMC]\d{4}|DS\d{4}|DC\d{4}|DET\d{4}|CAPEC-\d+|CWE-\d+)\b",
                 re.IGNORECASE)


def case_anchors(question: str) -> set[str]:
    return {m.upper() for m in IDS.findall(question or "")}


def anchor_exact(row: dict, ref: dict) -> bool:
    a = case_anchors(ref.get("question", ""))
    return set(row.get("entity_ids") or []) - a == set(ref.get("entity_ids") or []) - a


def tiers(rows: list[dict], refs: dict[str, dict]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(lambda: {"exact": 0, "anchor_exact": 0, "n": 0})
    for r in rows:
        cell = out[r["tier"]]
        cell["n"] += 1
        cell["exact"] += bool(r["records_exact"])
        cell["anchor_exact"] += anchor_exact(r, refs[r["case_id"]])
    return dict(sorted(out.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", required=True, help="run root holding variants/<arm>.json and variants/reference.json")
    ap.add_argument("--arms", default="E,T-lazy,T-full,T-lazy-G")
    ap.add_argument("--merge", default=None)
    args = ap.parse_args(argv)
    vdir = Path(args.runs) / "variants"
    refs = {r["case_id"]: r for r in json.loads((vdir / "reference.json").read_text())}
    result: dict[str, dict] = {}
    for arm in args.arms.split(","):
        p = vdir / f"{arm}.json"
        if not p.exists():
            continue
        rows = [r for r in json.loads(p.read_text()) if "records_exact" in r]
        result[arm] = tiers(rows, refs)
        print(arm, " ".join(f"{t}:{c['exact']}/{c['anchor_exact']}/{c['n']}" for t, c in result[arm].items()))
    if args.merge:
        mp = Path(args.merge)
        m = json.loads(mp.read_text())
        m["anchor_exact"] = result
        mp.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
