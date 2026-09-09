#!/usr/bin/env python3
"""Check that every number quoted in prose traces to a *current* experiment metric.

Two questions, asked of every numeric literal in a document:

1. **Traceability** — does the number appear as a metric value in some
   ``manifest.yaml``? A number that traces nowhere is a question, not a verdict
   (years, counts in prose, figures quoted from other papers legitimately do not
   trace), so untraced numbers are a review list.
2. **Currency** — does it trace *only* to a value an experiment has since
   withdrawn (``metrics.withdrawn``), or *only* to an experiment marked
   ``superseded``? Then the prose is quoting a figure the record has retracted.
   That is a defect, and with ``--gate`` it fails the run.

The second question is the one this repository had never asked. On 2026-09-09 a
full audit found the withdrawn federated-versus-merged pair quoted as current in
six documents, including the paper's abstract, while the first question reported
"0 untraced". Traceability was checked; currency never was.

    uv run python scripts/verify_paper_numbers.py              # the paper, review mode
    uv run python scripts/verify_paper_numbers.py --docs       # every prose document that quotes results
    uv run python scripts/verify_paper_numbers.py --docs --gate   # what the pre-commit hook runs
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "docs/research/paper/tmlr/ariadne-tmlr.tex"
EXPERIMENTS = REPO / "docs/research/experiments"

#: Prose that quotes results and must therefore quote *current* results.
#: Anything under docs/research/experiments/ is exempt: an experiment's own
#: RESULTS.md legitimately carries the numbers it later withdrew.
PROSE_DOCS = (
    "README.md",
    "docs/research/CLAIMS.md",
    "docs/research/OPEN_QUESTIONS.md",
    # DECISIONS.md is a dated, append-only ADR log: an entry legitimately quotes
    # the figure that was current on its date, so it is not scanned.
    "docs/research/paper/OUTLINE.md",
    "docs/research/paper/tmlr/ariadne-tmlr.tex",
    "docs/research/paper/ARTIFACT_APPENDIX.md",
    "docs/evaluation/README.md",
    "docs/ARCHITECTURE.md",
    "docs/goals.md",
    "docs/query-safety.md",
    "docs/pitch/october-pitch-plan.md",
)

#: Numbers that are never experiment metrics.
IGNORE = {
    "2026", "2025", "2024", "2021", "2017", "1729", "0.05", "0.95", "2000",
    "9090", "4000", "84000", "16384", "67617", "84001", "32768", "512",
}

#: Prose regions where numbers are quoted from OTHER people's work.
FOREIGN_CONTEXT = ("SPLIT-RAG", "Hit-point", "arXiv", "PhantomBench",
                   "Deceptive Grounding", "QUINT", "TeBaQA", "SEMANTiCS",
                   "WWW", "DOI", "TMLR", "OpenReview", "FedV-KGQA", "EMNLP")

#: A line carrying one of these words is *about* the withdrawal and may name
#: the old figure — "−0.0334 was withdrawn on 31 August" is not a stale quote.
RETRACTION_CONTEXT = re.compile(
    r"withdraw|retract|supersed|superced|do not quote|must not be quoted|"
    r"never quote|not quotable|no longer quot|artifact of|replaced by|"
    r"corrected|instead of|was wrong|old figure|stale|historical|history",
    re.IGNORECASE,
)

NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:[,{]\d{3}\}?)+|\d+\.\d{2,4})(?![\w])")


@dataclass
class Source:
    experiment: str
    metric: str
    status: str          # the experiment's status
    withdrawn: bool      # True when the value is in metrics.withdrawn
    replaced_by: str = ""

    @property
    def current(self) -> bool:
        return not self.withdrawn and self.status != "superseded"


@dataclass
class Index:
    by_form: dict[str, list[Source]] = field(default_factory=dict)

    def add(self, form: str, src: Source) -> None:
        self.by_form.setdefault(form, []).append(src)

    def lookup(self, raw: str, line: str) -> list[Source]:
        hit = self.by_form.get(raw) or self.by_form.get(raw.lstrip("0"))
        if not hit and "." in raw:
            hit = self.by_form.get(f"{float(raw):.4f}")
        # A percentage in prose is the same measurement as a fraction in a
        # manifest: 22.71% and 0.2271 are one number.
        if not hit and "%" in line:
            try:
                hit = self.by_form.get(f"{float(raw) / 100:.4f}")
            except ValueError:
                pass
        return hit or []


def _forms(v: float | int) -> set[str]:
    out = {f"{v}", f"{abs(v):.4f}", f"{abs(v):.3f}", f"{abs(v):.2f}"}
    if float(v).is_integer():
        out.add(f"{int(v)}")
    return {f for f in out if f} | {f.lstrip("0") or "0" for f in out if f}


def manifest_index() -> Index:
    """Every metric value in the record — current and withdrawn — with its status."""
    index = Index()
    for mf in sorted(glob.glob(str(EXPERIMENTS / "EXP-*" / "manifest.yaml"))):
        exp = Path(mf).parent.name
        try:
            m = yaml.safe_load(open(mf)) or {}
        except Exception:
            continue
        status = str(m.get("status", "unknown"))
        metrics = m.get("metrics") or {}
        for bucket, withdrawn in (("values", False), ("withdrawn", True)):
            cells = metrics.get(bucket) or {}
            if not isinstance(cells, dict):
                continue
            for name, cell in cells.items():
                if not isinstance(cell, dict):
                    continue
                src = Source(exp, name, status, withdrawn, str(cell.get("replaced_by", "")))
                for key in ("mean", "std", "n"):
                    v = cell.get(key)
                    if v is None:
                        continue
                    for form in _forms(v):
                        index.add(form, src)
    return index


def normalise(tok: str) -> str:
    return tok.replace(",", "").replace("{", "").replace("}", "")


def scan(doc: Path, index: Index) -> dict[str, list[dict]]:
    """Classify every numeric literal in one document."""
    traced, orphan, foreign, stale = [], [], [], []
    is_tex = doc.suffix == ".tex"
    for lineno, line in enumerate(doc.read_text(errors="replace").splitlines(), 1):
        if is_tex and line.lstrip().startswith("%"):
            continue
        is_foreign = any(f in line for f in FOREIGN_CONTEXT)
        is_retraction = bool(RETRACTION_CONTEXT.search(line))
        for tok in NUM.findall(line):
            raw = normalise(tok)
            if raw in IGNORE:
                continue
            hits = index.lookup(raw, line)
            row = {"line": lineno, "value": raw, "context": line.strip()[:110]}
            if hits:
                current = [h for h in hits if h.current]
                row["experiments"] = sorted({h.experiment for h in hits})[:3]
                # A superseded experiment's figure may be quoted as history when
                # the line names the experiment; a withdrawn value only beside
                # words that say it is withdrawn.
                cited = any(
                    not h.withdrawn and h.experiment[:15] in line for h in hits
                )
                if current or is_retraction or cited:
                    traced.append(row)
                else:
                    h = hits[0]
                    row["withdrawn_in"] = h.experiment
                    row["metric"] = h.metric
                    row["replaced_by"] = h.replaced_by or (
                        "the successor experiment" if h.status == "superseded" else "")
                    stale.append(row)
            elif is_foreign:
                foreign.append(row)
            else:
                orphan.append(row)
    return {"traced": traced, "untraced": orphan, "foreign": foreign, "stale": stale}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", default=None, help="write the full classification here")
    ap.add_argument("--paper", default=str(PAPER), help="document to check (default: the paper)")
    ap.add_argument("--docs", action="store_true",
                    help="check every prose document in PROSE_DOCS instead of one file")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any document quotes a withdrawn or superseded figure")
    ap.add_argument("--quiet", action="store_true", help="print only stale findings")
    args = ap.parse_args()

    if args.docs:
        docs = [REPO / d for d in PROSE_DOCS if (REPO / d).exists()]
    else:
        paper = Path(args.paper)
        paper = paper if paper.is_absolute() else (REPO / paper).resolve()
        if not paper.exists():
            print(f"document not found: {paper}")
            return 2
        docs = [paper]

    index = manifest_index()
    report = {}
    total_stale = 0
    for doc in docs:
        result = scan(doc, index)
        shown = doc.relative_to(REPO)
        report[str(shown)] = result
        total_stale += len(result["stale"])
        if not args.quiet:
            print(f"document         : {shown}")
            print(f"traced           : {len(result['traced'])}")
            print(f"quoted from others: {len(result['foreign'])}  (not expected to trace)")
            print(f"UNTRACED         : {len(result['untraced'])}  (review list, never a gate)")
            print(f"STALE            : {len(result['stale'])}  (withdrawn or superseded figures quoted as current)")
        for r in result["stale"]:
            print(f"  STALE  {shown}:{r['line']:<5} {r['value']:<10} withdrawn in {r['withdrawn_in']} "
                  f"({r['metric']}); quote {r['replaced_by'] or 'nothing — figure has no replacement'}")
            print(f"         {r['context']}")
        if not args.quiet and not args.docs and result["untraced"]:
            print("\n-- numbers with no manifest source (review, not a verdict) --")
            for r in result["untraced"][:40]:
                print(f"  L{r['line']:<5} {r['value']:<12} {r['context']}")
        if not args.quiet:
            print()

    print(f"manifest values  : {len(index.by_form)} distinct numeric forms "
          f"({sum(1 for v in index.by_form.values() if any(s.withdrawn for s in v))} withdrawn forms)")
    print(f"stale quotes     : {total_stale} across {len(docs)} document(s)")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
        print(f"written -> {args.json}")

    if args.gate and total_stale:
        print("\nFAIL: a document quotes a figure the record has withdrawn. "
              "Quote the replacement named in docs/research/CURRENT.md, or say on the "
              "same line that the figure is withdrawn.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
