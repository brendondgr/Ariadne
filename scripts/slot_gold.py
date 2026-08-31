#!/usr/bin/env python3
"""Derive what the system *should* understand, from data — never from behaviour.

    uv run python scripts/slot_gold.py --out docs/evaluation/variants-2026-08-29

For each golden question, write down the anchor it is about, that anchor's type,
the type of thing it asks for, and the relationship between them. Every variant
inherits its question's slots, so a paraphrase is judged on whether it
*understood*, independently of whether the query then worked.

## Provenance is the whole design

An earlier proposal derived these slots from a recorded run of the current
system. **That defines the incumbent as correct**: the replacement can never
score above it, every accidental success becomes a target, and every genuine
improvement scores as a failure. It is the same species as fitting thresholds
against the test bank — worse, because truth would come from *system output*
rather than from data.

So each slot comes from one of three sources, and none of them is a run:

``anchor``        the question's own authored ``task.seed_ids``, else identifiers
                  written in the authored question text.
``anchor_label``  that identifier's ``label`` in the **canonical snapshot** —
                  the checksummed parse of raw STIX and CAPEC XML.
``target_label``  the labels of the question's **computed gold answers**
                  (``ex_gold.expected``), also read from the snapshot.
``relation``      the authored ``expected_template`` **name** read against the
                  card's declared relationship types. The name states intent —
                  ``technique_mitigations`` is techniques-to-mitigations — and
                  the card states which relationship connects those labels. The
                  template's *code* is never consulted.

## Disagreement is the point, not noise

Where the relationship implied by the template name does not connect the labels
the gold answers actually carry, that is **recorded as a finding**: a question
the engine answers through a route that does not match what was asked. The
version that derived slots from behaviour would have discarded that signal by
construction, because behaviour and truth would be the same thing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from utils.config import load_env  # noqa: E402

load_env()

from utils.synthesis.grounding import normalize_id  # noqa: E402

_ID_RE = re.compile(
    r"\b(?:T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4}|TA\d{4}|C\d{4}|DC\d{4}|"
    r"DET\d{4}|AN\d{4}|CAPEC[-\s]?\d+|CWE[-\s]?\d+)\b",
    re.IGNORECASE,
)
_CAPEC_CANON = re.compile(r"^capec:[a-z-]+:(\d+)$", re.IGNORECASE)

#: Templates whose question shape names no single relationship. Authored here as
#: a declaration about the template *library*, not read out of any template's
#: implementation.
_RELATION_FREE = frozenset({
    "describe", "capec_neighbors", "capec_hierarchy_chain",
    "label_scan", "capec_scan", "boundary_refusal",
})


def snapshot_labels() -> dict[str, str]:
    """``identifier -> label``, straight from the checksummed canonical parse."""
    out: dict[str, str] = {}
    for dataset in ("attack", "capec"):
        path = REPO / "data" / "graphs" / dataset / "canonical" / "nodes.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            node = json.loads(line)
            props = node.get("properties") or {}
            label = str(node.get("label") or "")
            for raw in {str(props.get("attack_id") or ""), str(node.get("id") or "")}:
                if not raw:
                    continue
                m = _CAPEC_CANON.match(raw)
                key = f"CAPEC-{m.group(1)}" if m else raw
                out[normalize_id(key)] = label
    return out


def card_relationships() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for dataset in ("attack", "capec"):
        card = json.loads((REPO / "data-tri" / "source_cards" / f"{dataset}.json").read_text())
        out[dataset] = list(card.get("relationship_types") or [])
    return out


def _words(name: str) -> list[str]:
    return [w for w in re.split(r"[_\W]+", name or "") if w]


def _stems(name: str) -> set[str]:
    """Stemmed words of an identifier. `mitigations` and `MITIGATES` agree only
    after stemming — a trailing-`s` rule leaves `mitigation` against `mitigate`
    and matches nothing, which is why the first run of this script derived a
    relationship for 31 of 120 questions."""
    from utils.planner.lexicon import stem

    return {stem(w) for w in _words(name) if len(w) >= 3} - {""}


def relation_from_template(template: str, rels: list[str]) -> tuple[str | None, str]:
    """The relationship a template *name* declares, matched against the card.

    Returns ``(relationship, how)``. The template's implementation is never
    read — only its authored name and the card's authored relationship list.
    """
    if not template:
        return None, "no template declared"
    # A template name reads ``<subject>_<object>``, and the **object** is what
    # the question asks for: `technique_mitigations` wants mitigations. Plain
    # token overlap ties it — the name genuinely mentions both a technique and a
    # mitigation, so `MITIGATES` and `HAS_TECHNIQUE` score equally and the tie
    # rule discards both. Weighting the trailing word breaks that in favour of
    # the thing being asked for, which is what the name is declaring.
    words = _words(template)
    toks = _stems(template)
    obj = _stems(words[-1]) if words else set()
    scored: list[tuple[int, str]] = []
    for rel in rels:
        rel_stems = _stems(rel)
        overlap = len(toks & rel_stems) + 2 * len(obj & rel_stems)
        if overlap:
            scored.append((overlap, rel))
    if not scored:
        return None, "template name matches no declared relationship"
    scored.sort(key=lambda x: (-x[0], x[1]))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None, f"template name matches several relationships equally: {[s[1] for s in scored[:3]]}"
    return scored[0][1], "matched from the template name"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from pathlib import Path as _P

    from utils.specialists.evalset.compile_banks import (
        ATTACK_BANK_PATH, CAPEC_BANK_PATH, FEDERATED_BANK_PATH, load_bank,
    )

    def gold_questions():
        """Full bank entries — `variant_harness.gold_questions` drops the gold
        fields, which is why `target_labels` derived for 0 of 120 on the first
        run."""
        out = []
        for bank, path in (("attack", ATTACK_BANK_PATH), ("capec", CAPEC_BANK_PATH),
                           ("federated", FEDERATED_BANK_PATH)):
            entries = load_bank(_P(path))
            qs = entries["questions"] if isinstance(entries, dict) else entries
            for e in qs:
                txt = e.get("question") or e.get("text") or ""
                if not txt:
                    continue
                out.append({
                    "case_id": e.get("id", ""), "bank": bank, "question": txt,
                    "expected_template": e.get("expected_template", ""),
                    "seed_ids": list((e.get("task") or {}).get("seed_ids") or []),
                    "ex_gold": e.get("ex_gold") or {},
                    "assertions": e.get("assertions") or {},
                })
        return out

    labels = snapshot_labels()
    rels = card_relationships()

    rows: list[dict] = []
    findings: list[dict] = []
    for q in gold_questions():
        text = q["question"]
        seeds = [str(s) for s in q["seed_ids"] if s] or [
            re.sub(r"^capec\s*[-\s]?", "CAPEC-", m, flags=re.IGNORECASE)
            for m in _ID_RE.findall(text)
        ]
        anchors = [normalize_id(s) for s in seeds]
        anchor_labels = sorted({labels.get(a, "") for a in anchors} - {""})

        raw_gold: set[str] = set()
        for block, key in (("ex_gold", "expected"),
                           ("assertions", "must_include_related")):
            for value in ((q.get(block) or {}).get(key) or []):
                raw_gold.add(normalize_id(str(value)))
        gold_ids = sorted(raw_gold - {""})
        target_labels = sorted({labels.get(g, "") for g in gold_ids} - {""})

        dataset = "capec" if q["bank"] == "capec" else "attack"
        relation, how = relation_from_template(q["expected_template"], rels[dataset])

        row = {
            "case_id": q["case_id"], "bank": q["bank"],
            "anchors": anchors, "anchor_labels": anchor_labels,
            "target_labels": target_labels,
            "relation": relation, "relation_source": how,
            "template": q["expected_template"],
        }
        rows.append(row)

        # Templates that ask about an entity rather than about one link have no
        # single relationship to declare, and saying so is not a failure to
        # derive. `describe` returns a node and its facets; `capec_neighbors` is
        # relation-agnostic on purpose; the scans and the refusal probe have no
        # traversal at all. Counting these as disagreements would report 41
        # problems where there are none.
        if q["expected_template"] and relation is None:
            kind = ("relation-free-by-design"
                    if q["expected_template"] in _RELATION_FREE
                    else "template-name-declares-no-relation")
            findings.append({"case_id": q["case_id"], "kind": kind,
                             "detail": how, "template": q["expected_template"]})
        if anchors and not anchor_labels:
            findings.append({"case_id": q["case_id"], "kind": "anchor-not-in-snapshot",
                             "detail": f"anchors {anchors} have no label in the canonical parse"})
        if gold_ids and not target_labels:
            findings.append({"case_id": q["case_id"], "kind": "gold-not-in-snapshot",
                             "detail": f"gold {gold_ids[:4]} have no label in the canonical parse"})

    out_dir = REPO / args.out
    (out_dir / "slot_gold.json").write_text(json.dumps(rows, indent=2) + "\n")
    (out_dir / "slot_gold_findings.json").write_text(json.dumps(findings, indent=2) + "\n")

    filled = Counter()
    for r in rows:
        for slot in ("anchors", "anchor_labels", "target_labels", "relation"):
            if r[slot]:
                filled[slot] += 1
    print(f"  {len(rows)} questions")
    for slot in ("anchors", "anchor_labels", "target_labels", "relation"):
        print(f"    {slot:16s} derived for {filled[slot]:>4d}/{len(rows)}")
    real = [f for f in findings if f["kind"] != "relation-free-by-design"]
    print(f"\n  {len(findings)} note(s), of which {len(real)} are genuine gaps:")
    for kind, n in Counter(f["kind"] for f in findings).most_common():
        print(f"    {n:>4d}  {kind}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
