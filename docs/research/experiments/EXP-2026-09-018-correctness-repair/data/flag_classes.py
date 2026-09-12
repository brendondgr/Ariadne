#!/usr/bin/env python3
"""What the grader's hallucination flags actually are, counted from the files.

    uv run python .../data/flag_classes.py DIR [DIR…]     # any judged capture
    uv run python .../data/flag_classes.py                # the committed cells

The judged runs report a flag count, and a flag count is not a defect count. On
the development half the repaired arm carried 291 flags against 254 before, on a
correctness score that had risen from 0.7845 to 0.9211 — so either the repair
made the answers less faithful while making them more correct, or the flags were
not all the same kind of thing. They were not, and the four-way split is the
finding: **none of the four is an invention.** Three are the grader reading
something true as an asserted identifier, and the fourth was a real defect
(I-16), now closed.

The classes, in the order they are tested:

``own_id_example``
    The system's own help text. "Check the name, or give its id (e.g. T1566,
    M1017, or CAPEC-98)" puts three real identifiers in an answer that is
    abstaining, and the grader reads them as claims about the question's
    subject. 176 flags at Step 6. Entirely self-inflicted, and removed in the
    close-out's step 2.

``false_absence``
    "CAPEC-703 has no MEMBER_OF relationships" in an answer that enumerates
    them. The only class that is a genuine defect. I-16; zero after step 1.

``gold_omits_identifier``
    A real identifier, retrieved and grounded, that the gold does not list
    because the gold template deliberately rolls group and campaign technique
    lists up to their parents. The answer is right and the gold is narrow; see
    the `_top_level` note in the evalset. This class *rises* as enumeration
    improves, which is why the headline count rose with the score.

``node_text_as_identifier``
    A CAPEC consequence, execution step, prerequisite or indicator has no
    published id — its text *is* its identity — so the enumeration lists text,
    and the grader parses each list item as an asserted identifier. One answer
    scores 1.0 with 24 flags.

``other``
    Anything the four tests do not claim. Kept in the output rather than
    folded into a neighbour: a residue that grows is the signal that this
    classifier has stopped describing the data.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))

#: The identifiers the composer's own help text used to name.
ID_EXAMPLES = ("T1566", "M1017", "CAPEC-98")
#: A published catalogue identifier, as the answer surface spells it.
PUBLISHED_ID = re.compile(
    r"\b(?:CAPEC|CWE|T|S|G|M|C|TA|DET|AN|D3F)[-\d][\w.\-]*\b", re.I
)
#: "X has no Y in this catalogue." — I-16's shape.
ABSENCE = re.compile(r"\bhas no\b.*\b(?:relationships|in this catalogue)\b", re.I)
#: The grader disputing a COUNT or the enumeration's restriction line, rather
#: than any identifier in it. A distinct observation, and a fair one.
COUNT_OR_SCOPE = re.compile(
    r"contains \d+ entries|labell?ed \d+ but|\bnot \d+\.|restricted to|"
    r"\b\d+ distinct\b",
    re.I,
)
#: Below this length an item must match the flag exactly; "Low" and "1" appear
#: inside half the sentences the grader writes.
MIN_SUBSTRING = 8

#: The full judged development half (both grading positions) is the population
#: the four-way table describes. The three `i15-slice` cells are the close-out's
#: 12-case acceptance test for I-15, one position only — kept because the
#: intermediate one is the evidence that quoting alone did nothing.
CELLS = {
    **{
        arm: f"docs/evaluation/experiments/dev-half-2026-09-12/{arm}/answers"
        for arm in ("generic", "generic_composed", "deterministic")
    },
    "i15-slice/quoting-only":
        "docs/evaluation/experiments/i15-slice-2026-09-12/generic_composed/answers",
    "i15-slice/quoting-and-provenance":
        "docs/evaluation/experiments/i15-slice2-2026-09-12/generic_composed/answers",
}


def _answer_text(answer: dict) -> str:
    block = answer.get("answer") or {}
    parts = [block.get("headline") or "", block.get("narrative") or ""]
    parts += [c.get("text", "") for c in block.get("claims") or []]
    parts += [a.get("statement", "") for a in block.get("abstentions") or []]
    parts += [str(n) for n in block.get("notes") or []]
    return " ".join(parts)


def _retrieved_ids(answer: dict) -> set[str]:
    """Every identifier the executed walks actually returned."""
    out: set[str] = set()
    for result in (answer.get("logic_flow") or {}).get("results") or []:
        for record in result.get("records") or []:
            if record.get("primary_id"):
                out.add(str(record["primary_id"]))
            for rel in record.get("related") or []:
                if isinstance(rel, dict) and (rel.get("id") or rel.get("entry_id")):
                    out.add(str(rel.get("id") or rel.get("entry_id")))
    return out


def _listed_text(answer: dict) -> list[str]:
    """Items the answer LISTS that are text rather than published identifiers.

    Recovered from the composed claims, not from the evidence: the answer
    serializer writes a related entry as ``{id, name, label, type}`` and drops
    the properties the composer rendered it from, so a CAPEC consequence arrives
    here as ``capec:attack-pattern:295:consequence:1`` while the claim beside it
    reads "has 1 consequence: Other Confidentiality". The claim is the surface
    the grader read, so the claim is what this reads too.
    """
    out: list[str] = []
    for claim in (answer.get("answer") or {}).get("claims") or []:
        if claim.get("kind") not in ("enumeration", "fact"):
            continue
        text = str(claim.get("text") or "")
        _, sep, tail = text.partition(":")
        if not sep:
            continue
        for part in re.split(r"[;,]", tail):
            item = part.strip().rstrip(".").strip()
            if item and not PUBLISHED_ID.fullmatch(item):
                out.append(item.lower())
    return out


def classify(flag: str, answer: dict) -> str:
    text = flag.strip()
    low = text.lower()
    if any(example in text for example in ID_EXAMPLES) and any(
        example in _answer_text(answer) for example in ID_EXAMPLES
    ):
        return "own_id_example"
    if ABSENCE.search(text):
        return "false_absence"
    quoted = {m.group(0).upper() for m in PUBLISHED_ID.finditer(text)}
    if quoted & {i.upper() for i in _retrieved_ids(answer)}:
        return "gold_omits_identifier"
    # Text the answer listed, carrying no published identifier of its own. The
    # grader parses each item of an enumeration as an asserted id, so a CAPEC
    # consequence ("Other Confidentiality") or an execution-step phase
    # ("Explore 1") is flagged exactly as a fabricated identifier would be.
    listed = _listed_text(answer)
    if not quoted and any(
        item == low
        or (len(item) >= MIN_SUBSTRING and (item in low or low in item))
        for item in listed
    ):
        return "node_text_as_identifier"
    if COUNT_OR_SCOPE.search(text):
        return "count_or_scope_mismatch"
    return "other"


def scan(directory: Path) -> dict:
    counts: Counter[str] = Counter()
    residue: list[str] = []
    answers = 0
    for path in sorted(directory.glob("*.json")):
        if ".judgment" not in path.name:
            continue
        judgment = json.loads(path.read_text())
        flags = judgment.get("hallucinations") or []
        if not flags:
            continue
        stem = path.name.split(".judgment")[0] + ".json"
        source = directory / stem
        answer = json.loads(source.read_text()) if source.is_file() else {}
        answers += 1
        for flag in flags:
            kind = classify(str(flag), answer)
            counts[kind] += 1
            if kind == "other":
                residue.append(str(flag)[:160])
    return {
        "flags": sum(counts.values()),
        "judgments_with_flags": answers,
        "by_class": dict(counts.most_common()),
        "residue": residue[:20],
    }


def main(argv: list[str]) -> int:
    targets = {d: d for d in argv} or {k: str(REPO / v) for k, v in CELLS.items()}
    report = {}
    for name, path in targets.items():
        directory = Path(path)
        if not directory.is_dir():
            print(f"{name:24s} MISSING {directory}")
            continue
        report[name] = scan(directory)
        row = report[name]
        print(f"{name:24s} flags={row['flags']:4d}  {row['by_class']}")
    if not argv:
        out = Path(__file__).with_suffix(".json")
        out.write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
