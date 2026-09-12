#!/usr/bin/env python3
"""Are the authored questions one bank, or several stapled together?

    uv run python scripts/authored_style_check.py --authored <dir> --briefs <dir>
    uv run python scripts/authored_style_check.py --authored <dir> --compare docs/evaluation/composition/bank/bank.json

A bank authored in batches by separate agents can pass every per-question
validator and still be inhomogeneous: one batch writes terse eight-word
questions, another writes twenty-word ones with two subordinate clauses, and the
difficulty of a question set then varies with which agent happened to get it.
That is a confound in the *instrument*, and it is invisible to a validator that
only ever sees one question at a time.

So this looks at the batches side by side, per register, and reports:

* **length** — words per question, mean and spread;
* **complexity** — clauses per question, counted as the commas and subordinating
  conjunctions a reader has to hold open;
* **schema overlap** — the existing tell for an author that has been reading the
  label vocabulary, here aggregated per batch rather than per question;
* **question shape** — how many open with a wh-word, and how many are phrased as
  a request ("list", "give me").

The judgement is a z-score of each batch against the pooled distribution of the
others in its register. A batch beyond `--tolerance` on length or complexity is
named and should be re-authored; the point is to re-run one batch, not to argue
about a style guide.

**It deliberately does not compare against example questions.** The Author must
not see one, so neither may this: it compares batches against each other, and —
with `--compare` — against an existing bank's *distribution*, which is a
summary statistic and not a worked example.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

#: Words that open a subordinate clause the reader must hold open. Counted with
#: commas as a plain proxy for "how much is going on in this sentence".
SUBORDINATORS = (
    "that", "which", "whose", "when", "where", "after", "before", "while",
    "if", "unless", "because", "although", "given", "having",
)
WH = ("what", "which", "who", "whom", "whose", "when", "where", "why", "how")
REQUEST = ("list", "give", "show", "name", "identify", "enumerate", "tell", "provide")


def _words(question: str) -> list[str]:
    return [w for w in re.findall(r"[A-Za-z0-9_.\-]+", question or "") if w]


def _complexity(question: str) -> int:
    low = (question or "").lower()
    commas = low.count(",")
    subs = sum(1 for w in _words(low) if w in SUBORDINATORS)
    return commas + subs


def measure(questions: list[str]) -> dict:
    lengths = [len(_words(q)) for q in questions if q]
    clauses = [_complexity(q) for q in questions if q]
    if not lengths:
        return {"n": 0}
    low = [(q or "").lower().lstrip() for q in questions if q]
    return {
        "n": len(lengths),
        "words_mean": round(statistics.fmean(lengths), 2),
        "words_sd": round(statistics.stdev(lengths), 2) if len(lengths) > 1 else 0.0,
        "words_min": min(lengths),
        "words_max": max(lengths),
        "clauses_mean": round(statistics.fmean(clauses), 2),
        "clauses_sd": round(statistics.stdev(clauses), 2) if len(clauses) > 1 else 0.0,
        "opens_with_wh": round(
            sum(1 for q in low if q.split(" ")[0].strip(",") in WH) / len(low), 3
        ),
        "phrased_as_request": round(
            sum(1 for q in low if q.split(" ")[0].strip(",") in REQUEST) / len(low), 3
        ),
    }


def _z(value: float, pool: list[float]) -> float:
    if len(pool) < 2:
        return 0.0
    sd = statistics.stdev(pool)
    if sd < 1e-9:
        return 0.0
    return (value - statistics.fmean(pool)) / sd


def load_authored(directory: Path) -> dict[str, list[tuple[str, str]]]:
    """batch name -> [(item id, question)]"""
    out: dict[str, list[tuple[str, str]]] = {}
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text())
        rows = [
            (str(q.get("id")), str(q.get("question") or ""))
            for q in payload.get("questions", [])
        ]
        if rows:
            out[path.stem] = rows
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--authored", type=Path, required=True)
    ap.add_argument("--briefs", type=Path, default=None,
                    help="the brief index, to group batches by register")
    ap.add_argument("--compare", type=Path, default=None,
                    help="an existing bank, compared as a DISTRIBUTION only")
    ap.add_argument("--tolerance", type=float, default=2.0,
                    help="|z| beyond which a batch is a candidate outlier")
    ap.add_argument("--min-gap-words", type=float, default=2.0,
                    help="a candidate is only an outlier if it is ALSO this far "
                         "from its register's mean in words")
    ap.add_argument("--min-gap-clauses", type=float, default=0.75,
                    help="the same floor, in clauses")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    batches = load_authored(args.authored)
    if not batches:
        raise SystemExit(f"no authored questions under {args.authored}")

    register_of: dict[str, str] = {}
    if args.briefs:
        index = json.loads((args.briefs / "index.json").read_text())
        register_of = {k: v["register"] for k, v in index.items()}

    report: dict = {"batches": {}, "by_register": {}, "outliers": []}
    for name, rows in batches.items():
        report["batches"][name] = measure([q for _i, q in rows])

    grouped: dict[str, list[str]] = defaultdict(list)
    for name, rows in batches.items():
        registers = {register_of.get(i, name.split("-")[0]) for i, _q in rows}
        grouped[sorted(registers)[0] if len(registers) == 1 else "mixed"].append(name)

    for register, names in sorted(grouped.items()):
        pooled = [q for n in names for _i, q in batches[n]]
        report["by_register"][register] = measure(pooled)
        for metric in ("words_mean", "clauses_mean"):
            pool = [report["batches"][n][metric] for n in names
                    if report["batches"][n].get("n")]
            for name in names:
                row = report["batches"][name]
                if not row.get("n"):
                    continue
                others = [report["batches"][n][metric] for n in names if n != name]
                z = _z(row[metric], others or pool)
                row[f"z_{metric}"] = round(z, 2)
                # A z-score alone is the wrong test once the batches are tight:
                # if every batch lands within a word of the others, the standard
                # deviation collapses and a batch a word and a half out scores
                # |z| > 3 while being, in fact, the same length. The existing
                # bank's batches span 10.2 to 26.8 words; these span about four.
                # So a batch must be BOTH statistically distinguishable and
                # materially different before it is worth re-authoring.
                gap = abs(row[metric] - report["by_register"][register][metric])
                floor = (args.min_gap_words if metric == "words_mean"
                         else args.min_gap_clauses)
                row[f"gap_{metric}"] = round(gap, 2)
                if abs(z) > args.tolerance and gap >= floor:
                    report["outliers"].append(
                        {"batch": name, "register": register, "metric": metric,
                         "value": row[metric], "z": round(z, 2), "gap": round(gap, 2)}
                    )
                elif abs(z) > args.tolerance:
                    report.setdefault("tight_cluster_flags", []).append(
                        {"batch": name, "register": register, "metric": metric,
                         "value": row[metric], "z": round(z, 2), "gap": round(gap, 2)}
                    )

    if args.compare:
        doc = json.loads(args.compare.read_text())
        questions = doc["questions"] if isinstance(doc, dict) else doc
        by_register: dict[str, list[str]] = defaultdict(list)
        for q in questions:
            by_register[q["register"]].append(q["question"])
        report["reference_bank"] = {
            "bank": str(args.compare),
            "overall": measure([q["question"] for q in questions]),
            "by_register": {r: measure(v) for r, v in sorted(by_register.items())},
        }

    print(f"{'batch':22s} {'n':>4s} {'words':>13s} {'clauses':>12s}  z(words) z(clauses)")
    for name, row in sorted(report["batches"].items()):
        if not row.get("n"):
            continue
        print(f"{name:22s} {row['n']:4d} "
              f"{row['words_mean']:6.2f}±{row['words_sd']:<5.2f} "
              f"{row['clauses_mean']:5.2f}±{row['clauses_sd']:<5.2f}  "
              f"{row.get('z_words_mean', 0):+7.2f} {row.get('z_clauses_mean', 0):+9.2f}")
    for register, row in sorted(report["by_register"].items()):
        print(f"\n{register}: n={row['n']} words {row['words_mean']}±{row['words_sd']} "
              f"clauses {row['clauses_mean']}±{row['clauses_sd']} "
              f"wh-opening {row['opens_with_wh']}")
    if args.compare:
        ref = report["reference_bank"]["overall"]
        print(f"\nreference bank: n={ref['n']} words {ref['words_mean']}±{ref['words_sd']} "
              f"clauses {ref['clauses_mean']}±{ref['clauses_sd']} "
              f"wh-opening {ref['opens_with_wh']}")
    if report["outliers"]:
        print(f"\nOUTLIER BATCHES (|z| > {args.tolerance}) — re-author these:")
        for row in report["outliers"]:
            print(f"  {row['batch']}: {row['metric']}={row['value']} "
                  f"z={row['z']} gap={row['gap']}")
    else:
        print(f"\nno batch is both |z| > {args.tolerance} and materially apart "
              f"(>= {args.min_gap_words} words / {args.min_gap_clauses} clauses)")
    for row in report.get("tight_cluster_flags", []):
        print(f"  (statistically apart but materially the same: {row['batch']} "
              f"{row['metric']}={row['value']} z={row['z']} gap={row['gap']})")

    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
