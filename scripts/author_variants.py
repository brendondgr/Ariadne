#!/usr/bin/env python3
"""Prepare, gate and assemble the Sonnet-authored variant bank.

    uv run python scripts/author_variants.py prepare --out docs/evaluation/variants-2026-08-29
    uv run python scripts/author_variants.py gate    --out docs/evaluation/variants-2026-08-29

**Why the authoring inputs are not just the question.** A variant author asked
for "a paraphrase that does not use the technique id" will reach for the
schema's own word — "mitigation", "technique", "group" — and hand back a T1
wearing a T5 label. Two things prevent that, and both must be computed here
rather than trusted to the author:

``anchor_names``   the real ``name`` of each seeded entity, read from the
                   canonical snapshot. Without it a T3 ("use the exact name")
                   cannot be written at all, because nothing in the gold
                   question carries it — ``T1176`` never says
                   *Software Extensions*.
``avoid``          every word appearing in a node label or relationship type of
                   the banks this question touches. T4 and T5 must avoid all of
                   them, and ``gate`` enforces it mechanically afterwards.

**The gate is the point.** An author's self-declared tier is a claim, not
evidence. ``gate`` rejects a T3+ that still carries the identifier and a T4/T5
that carries a schema word, and it records every rejection rather than dropping
it, so the bank's coverage is honest about what could not be written.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TIERS = ("T1", "T2", "T3", "T4", "T5", "T6")

#: Bank -> the datasets whose vocabulary a variant must avoid at T4/T5.
BANK_DATASETS: dict[str, tuple[str, ...]] = {
    "attack": ("attack",),
    "capec": ("capec",),
    "federated": ("attack", "capec"),
}

_ID_RE = re.compile(r"\b(?:T\d{4}(?:\.\d{3})?|G\d{4}|S\d{4}|M\d{4}|TA\d{4}|C\d{4}|"
                    r"DC\d{4}|DET\d{4}|AN\d{4}|CAPEC[-\s]?\d+)\b", re.IGNORECASE)


def _split_identifier(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ")
    return [w.lower() for w in spaced.split() if len(w) >= 3]


def _card(dataset: str) -> dict[str, Any]:
    return json.loads((REPO / "data-tri" / "source_cards" / f"{dataset}.json").read_text())


def avoid_words(datasets: tuple[str, ...]) -> list[str]:
    """Every word in a label or relationship name of the given datasets."""
    words: set[str] = set()
    for ds in datasets:
        card = _card(ds)
        for name in list(card.get("node_labels") or []) + list(
            card.get("relationship_types") or []
        ):
            words.update(_split_identifier(name))
    return sorted(words)


#: CAPEC's canonical node id is ``capec:attack-pattern:66`` while every question
#: and every bank writes ``CAPEC-66``. Indexing only the canonical form loses
#: the name for every CAPEC anchor, which silently removes T3-T5 from a third of
#: the bank -- so both spellings are indexed.
_CAPEC_CANON_RE = re.compile(r"^capec:[a-z-]+:(\d+)$", re.IGNORECASE)


def canonical_names(datasets: tuple[str, ...]) -> dict[str, dict[str, str]]:
    """``id -> {name, description, label}`` from each dataset's canonical snapshot.

    Keyed under every spelling a question might use: the ATT&CK id, the raw
    canonical id, and for CAPEC the ``CAPEC-N`` form the analyst-facing world
    actually writes.
    """
    out: dict[str, dict[str, str]] = {}
    for ds in datasets:
        path = REPO / "data" / "graphs" / ds / "canonical" / "nodes.jsonl"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            node = json.loads(line)
            props = node.get("properties") or {}
            entry = {
                "name": str(node.get("name") or ""),
                "description": str(props.get("description") or "")[:300],
                "label": str(node.get("label") or ""),
            }
            keys = {str(props.get("attack_id") or ""), str(node.get("id") or "")}
            m = _CAPEC_CANON_RE.match(str(node.get("id") or ""))
            if m:
                keys.add(f"CAPEC-{m.group(1)}")
            for key in keys:
                if key:
                    out[key.upper()] = entry
    return out


def seed_ids_for(question: dict[str, Any]) -> list[str]:
    """Declared seed ids, falling back to identifiers written in the question.

    The federated bank declares no ``seed_ids`` at all -- all 40 of its entries
    carry the anchor inline, as in "Which ATT&CK techniques does CAPEC-150
    (Collect Data from Common Resource) map to?". Reading only the declared
    field drops every federated question out of T3-T5.
    """
    declared = [str(s) for s in question.get("seed_ids") or [] if s]
    if declared:
        return declared
    found = _ID_RE.findall(question.get("question") or "")
    return [re.sub(r"^capec\s*[-\s]?", "CAPEC-", f, flags=re.IGNORECASE) for f in found]


def cmd_prepare(args: argparse.Namespace) -> int:
    from scripts.variant_harness import gold_questions  # noqa: PLC0415

    names = canonical_names(("attack", "capec"))
    avoid_by_bank = {b: avoid_words(ds) for b, ds in BANK_DATASETS.items()}

    rows: list[dict[str, Any]] = []
    missing = 0
    for q in gold_questions():
        anchors: list[dict[str, str]] = []
        q["seed_ids"] = seed_ids_for(q)
        for sid in q["seed_ids"]:
            info = names.get(str(sid).upper())
            if info and info["name"]:
                anchors.append({"id": sid, **info})
            else:
                missing += 1
        rows.append({**q, "anchor_names": anchors,
                     "avoid": avoid_by_bank.get(q["bank"], [])})

    out_dir = REPO / args.out / "authoring"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs.json").write_text(json.dumps(rows, indent=2) + "\n")

    batches = [rows[i:i + args.batch] for i in range(0, len(rows), args.batch)]
    for i, batch in enumerate(batches, 1):
        (out_dir / f"batch_{i:02d}.json").write_text(json.dumps(batch, indent=2) + "\n")

    no_anchor = [r for r in rows if not r["anchor_names"]]
    print(f"prepared {len(rows)} questions into {len(batches)} batches of ≤{args.batch}")
    print(f"  {len(rows) - len(no_anchor)} have at least one named anchor; "
          f"{len(no_anchor)} have none ({missing} seed ids unresolved)")
    print(f"  avoid-list sizes: { {b: len(w) for b, w in avoid_by_bank.items()} }")
    for r in no_anchor[:6]:
        print(f"    no anchor: {r['case_id']:12s} {r['question'][:56]}")
    return 0


# -- gate -------------------------------------------------------------------


def gate_one(v: dict[str, Any], src: dict[str, Any]) -> str | None:
    """Return a rejection reason, or ``None`` if the variant is honest."""
    text = str(v.get("question") or "").strip()
    tier = str(v.get("tier") or "")
    if not text:
        return "empty question"
    if tier not in TIERS:
        return f"unknown tier {tier!r}"
    low = text.lower()

    if tier in ("T3", "T4", "T5") and _ID_RE.search(text):
        return f"{tier} still carries an identifier"
    if tier in ("T4", "T5"):
        for word in src.get("avoid") or []:
            if re.search(rf"\b{re.escape(word)}s?\b", low):
                return f"{tier} uses schema word {word!r}"
    if tier in ("T1", "T2") and not _ID_RE.search(text):
        return f"{tier} must keep the identifier"
    if tier == "T3":
        exact = [a["name"].lower() for a in src.get("anchor_names") or []]
        if exact and not any(n and n in low for n in exact):
            return "T3 must contain the anchor's exact name"
    if tier == "T5":
        for a in src.get("anchor_names") or []:
            if a["name"] and a["name"].lower() in low:
                return "T5 must not contain the anchor name"
    return None


def cmd_gate(args: argparse.Namespace) -> int:
    out_dir = REPO / args.out
    src_by_id = {r["case_id"]: r
                 for r in json.loads((out_dir / "authoring" / "inputs.json").read_text())}

    raw: list[dict[str, Any]] = []
    for path in sorted((out_dir / "authoring").glob("authored_*.json")):
        raw.extend(json.loads(path.read_text()))
    print(f"gating {len(raw)} authored variants from "
          f"{len(list((out_dir / 'authoring').glob('authored_*.json')))} files")

    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for v in raw:
        src = src_by_id.get(v.get("case_id", ""))
        if src is None:
            rejected.append({**v, "rejected": "unknown case_id"})
            continue
        key = (v["case_id"], str(v.get("question", "")).strip().lower())
        if key in seen:
            rejected.append({**v, "rejected": "duplicate"})
            continue
        reason = gate_one(v, src)
        if reason:
            rejected.append({**v, "rejected": reason})
            continue
        seen.add(key)
        kept.append({"case_id": v["case_id"], "bank": src["bank"], "tier": v["tier"],
                     "question": v["question"].strip(),
                     "note": str(v.get("note", ""))[:200],
                     "gold_question": src["question"]})

    (out_dir / "variants.json").write_text(json.dumps(kept, indent=2) + "\n")
    (out_dir / "variants_rejected.json").write_text(json.dumps(rejected, indent=2) + "\n")

    per_tier = Counter(v["tier"] for v in kept)
    per_case: dict[str, set[str]] = defaultdict(set)
    for v in kept:
        per_case[v["case_id"]].add(v["tier"])
    full = sum(1 for c in src_by_id if {"T1", "T2", "T3", "T4", "T5"} <= per_case.get(c, set()))

    print(f"\n  kept {len(kept)} | rejected {len(rejected)}")
    print(f"  per tier: { dict(sorted(per_tier.items())) }")
    print(f"  gold questions with all of T1-T5: {full}/{len(src_by_id)}")
    print(f"  gold questions with no variants at all: "
          f"{sum(1 for c in src_by_id if c not in per_case)}")
    if rejected:
        print("\n  top rejection reasons:")
        for reason, n in Counter(r["rejected"] for r in rejected).most_common(8):
            print(f"    {n:>4d}  {reason}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--out", required=True)
    p.add_argument("--batch", type=int, default=10); p.set_defaults(func=cmd_prepare)
    g = sub.add_parser("gate"); g.add_argument("--out", required=True)
    g.set_defaults(func=cmd_gate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
