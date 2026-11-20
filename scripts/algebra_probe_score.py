#!/usr/bin/env python3
"""Score answers to the algebra probe set (Era 2, Step 9, Phase G).

    uv run python scripts/algebra_probe_score.py <answers_dir> <bank.json> [--out report.json]

``answers_dir`` holds the per-question artifacts ``experiment_untruncated`` writes
(``<root>/<arm>/answers/<id>.json``; ``*.judgment.json`` sidecars are skipped).
``bank.json`` is ``probe-tune.json`` or ``probe-measure.json`` from
``scripts/algebra_probe_set.py bank``.

What the answer said is read from two places:
- ``run_meta.algebra_results``: a list of ``{"step", "kind", "value", "ids", "rows",
  "total", "complete", "info"}``. The **last** step is the final answer.
- the answer's claims (``answer.claims[].entity_ids``), used for node gold when
  there are no algebra results.

Per item, one verdict:
- ``exact``: node gold - the final ids equal the gold ids as a set (ids are compared
  in public form; a stored id the item's gold maps is translated). Scalar gold - the
  value equals the gold value: booleans strictly, numbers exactly except that floats
  agree within a relative 1e-9 (S11), and ISO date text agrees on its YYYY-MM-DD prefix.
- ``abstained``: nothing came back - no algebra results and no claimed ids, or a final
  step with no ids and no value - and that is not the gold answer.
- ``confidently_wrong``: something came back and it is not the gold answer.
- ``unparsed``: scalar gold, the answer made claims, but no structured value exists
  to compare (no algebra results); reported apart, never counted exact.
- ``missing``: no answer file for the item.

Reported per operator, per switch group (core / extended), per dataset and per source.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

REL_TOL = 1e-9
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_GREMLIN_CAPEC = re.compile(r"^capec:(?:attack-pattern|category|view):(\d+)$")
_GREMLIN_CWE = re.compile(r"^cwe:(\d+)$")
VERDICTS = ("exact", "confidently_wrong", "abstained", "unparsed", "missing")


def normalize_id(value: Any, stored_to_public: dict[str, str] | None = None) -> str:
    """Public form of an id: the item's own stored->public map first, then CAPEC/CWE stored forms."""
    v = str(value or "").strip()
    if stored_to_public and v in stored_to_public:
        return stored_to_public[v]
    m = _GREMLIN_CAPEC.match(v)
    if m:
        return f"CAPEC-{m.group(1)}"
    m = _GREMLIN_CWE.match(v)
    if m:
        return f"CWE-{m.group(1)}"
    return v


def values_equal(got: Any, want: Any) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return isinstance(want, bool) and isinstance(got, bool) and got == want
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        if got == want:
            return True
        if isinstance(want, float) or isinstance(got, float):
            return math.isclose(float(got), float(want), rel_tol=REL_TOL, abs_tol=0.0)
        return False
    if isinstance(want, (int, float)) and isinstance(got, str):  # a number spelled as text
        try:
            return values_equal(float(got) if "." in got or "e" in got.lower() else int(got), want)
        except ValueError:
            return False
    if isinstance(want, str) and isinstance(got, str):
        if got == want:
            return True
        if ISO.match(want) and ISO.match(got):
            return got[:10] == want[:10]
        return False
    return got == want


def _claimed_ids(answer: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for c in (answer.get("answer") or {}).get("claims") or []:
        out += [str(e) for e in c.get("entity_ids") or []]
    return out


def _step_ids(step: dict[str, Any]) -> list[str]:
    ids = [str(x) for x in step.get("ids") or []]
    if ids:
        return ids
    rows = step.get("rows") or []
    for r in rows:
        if isinstance(r, dict) and isinstance(r.get("path"), list):  # shortest: nodes sit at even positions
            ids += [str(x) for x in r["path"][0::2]]
        elif isinstance(r, dict) and r.get("id") is not None:
            ids.append(str(r["id"]))
    return ids


def final_answer(answer: dict[str, Any]) -> dict[str, Any]:
    """What the answer asserts: ``ids`` (or ``None``), ``value`` (or ``None``), and where it came from."""
    results = ((answer.get("run_meta") or {}).get("algebra_results")) or []
    if results:
        last = results[-1]
        return {"source": "algebra_results", "ids": _step_ids(last), "value": last.get("value"),
                "kind": last.get("kind"), "has_claims": bool(_claimed_ids(answer))}
    claimed = _claimed_ids(answer)
    return {"source": "entity_ids", "ids": claimed, "value": None, "kind": None, "has_claims": bool(claimed)}


def judge(item: dict[str, Any], answer: dict[str, Any] | None) -> dict[str, Any]:
    """One verdict for one bank entry and its answer artifact."""
    probe = item["algebra_probe"]
    gold = probe["gold"]
    row = {"id": item["id"], "operator": probe["operator"], "detail": probe["detail"], "switch": probe["switch"],
           "dataset": probe["dataset"], "source": probe["source"], "split": probe["split"],
           "negative": probe["negative"], "gold_kind": gold["kind"]}
    if answer is None:
        return {**row, "verdict": "missing"}
    fa = final_answer(answer)
    row["answer_source"] = fa["source"]
    if gold["kind"] == "nodes":
        mapping = dict(zip(gold.get("stored_ids") or [], gold.get("ids") or []))
        got = {normalize_id(x, mapping) for x in fa["ids"]}
        want = {normalize_id(x, mapping) for x in gold["ids"]}
        row.update(got_n=len(got), gold_n=len(want), missing_ids=sorted(want - got)[:10],
                   extra_ids=sorted(got - want)[:10])
        if got == want:
            return {**row, "verdict": "exact"}
        if not got:
            return {**row, "verdict": "abstained"}
        return {**row, "verdict": "confidently_wrong"}
    want_v = gold["value"]
    got_v = fa["value"]
    row.update(gold_value=want_v, got_value=got_v)
    if fa["source"] == "algebra_results":
        if got_v is not None and values_equal(got_v, want_v):
            return {**row, "verdict": "exact"}
        if got_v is None and not fa["ids"]:
            return {**row, "verdict": "abstained"}
        return {**row, "verdict": "confidently_wrong"}
    if not fa["has_claims"]:
        return {**row, "verdict": "abstained"}
    return {**row, "verdict": "unparsed"}


def load_answers(answers_dir: Path) -> dict[str, dict[str, Any]]:
    d = answers_dir / "answers" if (answers_dir / "answers").is_dir() else answers_dir
    out: dict[str, dict[str, Any]] = {}
    for p in sorted(d.glob("*.json")):
        if p.name.endswith(".judgment.json") or ".judgment" in p.name:
            continue
        try:
            doc = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        if isinstance(doc, dict) and "id" in doc:
            out[doc["id"]] = doc
    return out


def summarize(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in rows:
        groups[str(r[key])][r["verdict"]] += 1
    out = {}
    for g, c in sorted(groups.items()):
        n = sum(c.values())
        out[g] = {"n": n, **{v: c.get(v, 0) for v in VERDICTS},
                  "exact_rate": round(c.get("exact", 0) / n, 4) if n else None,
                  "confidently_wrong_rate": round(c.get("confidently_wrong", 0) / n, 4) if n else None}
    return out


def score(answers_dir: Path, bank_path: Path) -> dict[str, Any]:
    bank = json.loads(Path(bank_path).read_text())
    answers = load_answers(Path(answers_dir))
    rows = [judge(q, answers.get(q["id"])) for q in bank["questions"]]
    total = collections.Counter(r["verdict"] for r in rows)
    n = len(rows)
    return {
        "bank": str(bank_path),
        "answers": str(answers_dir),
        "n": n,
        "overall": {"n": n, **{v: total.get(v, 0) for v in VERDICTS},
                    "exact_rate": round(total.get("exact", 0) / n, 4) if n else None},
        "by_operator": summarize(rows, "operator"),
        "by_switch": summarize(rows, "switch"),
        "by_dataset": summarize(rows, "dataset"),
        "by_source": summarize(rows, "source"),
        "items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Score algebra probe answers.")
    ap.add_argument("answers_dir")
    ap.add_argument("bank")
    ap.add_argument("--out", default=None, help="write the full report here (default: stdout)")
    args = ap.parse_args(argv)
    rep = score(Path(args.answers_dir), Path(args.bank))
    text = json.dumps(rep, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(json.dumps({k: rep[k] for k in ("overall", "by_switch")}, indent=1))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
