#!/usr/bin/env python3
"""Write author briefs for a spec selection — and nothing but briefs.

The Author role is defined by what it cannot see: not the gold, not the answer
path, not the difficulty tier, not the query templates, not the repository. When
the Author is an API call that restriction enforces itself, because the prompt
is the only channel. When the Author is a subagent with a filesystem, it does
not — so the restriction moves here, into the file the agent is given.

This script writes that file and asserts the restriction on the way out:
`_assert_no_leakage` fails if any spec's gold, tier, predicate or step appears
anywhere in the payload. A brief that leaked would produce questions that score
well for the wrong reason, and nothing downstream would notice.

Usage:
    uv run python scripts/prepare_briefs.py --limit 42 --batches 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from utils.specialists.evalset import render as rd
from utils.specialists.evalset.composition import Spec
from scripts.render_questions import DEFAULT_SPECS, _stratified, load_specs

#: Exactly what an item may contain. Anything else is a leak by construction.
ALLOWED_ITEM_KEYS = frozenset({
    "id", "subject_name", "subject_type", "identifier", "ask_for",
    "answer_shape", "restriction",
})

INSTRUCTIONS = """\
You are writing evaluation questions for a cybersecurity knowledge-base benchmark.

For each item below, write ONE natural-language question. Return JSON only:
{"questions": [{"id": "<item id>", "question": "<the question>"}, ...]}

Each item gives you: a subject (its name, its type, its identifier), what the
question should ask for, and sometimes a restriction to apply.

Rules, all of which are checked automatically and will cause a rejection:
- The question MUST contain the subject's identifier exactly as given.
- The question MUST NOT contain any other identifier.
- Do NOT answer the question. Do NOT explain yourself.
- Do NOT use underscores, camelCase, or database field names. Write it the way a
  person would say it.
- Exactly one question mark.
- Some items have no answer in the data. You cannot tell which, and you should
  not try: write every item as a straightforward question regardless.
"""


def item_id(spec: Spec, register: str) -> str:
    """An opaque handle.

    The spec id cannot be used: `D0-Analytic-kill_chain_phase-AN1504` names the
    tier and the predicate, which are two of the four things the Author must not
    see. The leakage guard caught it, which is what the guard is for.
    """
    digest = hashlib.sha256(f"{spec.id}::{register}".encode()).hexdigest()[:12]
    return f"q{digest}"


def brief_payload(spec: Spec, register: str) -> dict[str, Any]:
    brief = rd.brief_for(spec)
    item: dict[str, Any] = {
        "id": item_id(spec, register),
        "subject_name": brief.anchor_name,
        "subject_type": brief.anchor_type,
        "identifier": brief.anchor_key,
        "ask_for": brief.ask,
        "answer_shape": brief.answer_type,
    }
    if brief.constraint:
        item["restriction"] = brief.constraint
    return item


def partition(specs: list[Spec], batches: int) -> list[list[Spec]]:
    """Split specs into files where no item's anchor is another item's answer.

    A batch is one prompt, so every brief in it is visible at once. Put
    "what mitigates M1038" (whose gold includes T1204.004) in the same file as
    an item anchored on T1204.004 and the Author can read one answer off
    another — not likely, but the whole point of the role is that it *cannot*,
    not that it probably won't.

    Greedy first-fit, deterministic in the order specs arrive. Batch count is a
    lower bound: conflicts create more files, never fewer.
    """
    target = max(1, -(-len(specs) // max(1, batches)))
    groups: list[list[Spec]] = []
    golds: list[set[str]] = []
    anchors: list[set[str]] = []
    for spec in specs:
        for index, group in enumerate(groups):
            if len(group) >= target:
                continue
            if spec.anchor_key in golds[index] or set(spec.gold) & anchors[index]:
                continue
            group.append(spec)
            golds[index] |= set(spec.gold)
            anchors[index].add(spec.anchor_key)
            break
        else:
            groups.append([spec])
            golds.append(set(spec.gold))
            anchors.append({spec.anchor_key})
    return groups


def _assert_no_leakage(payload: dict[str, Any], specs: list[Spec]) -> None:
    """Fail loudly if anything the Author must not see reached the file."""
    blob = json.dumps(payload)
    lookup = {item_id(s, r): s for s in specs for r in rd.REGISTERS}
    for item in payload["items"]:
        spec = lookup[item["id"]]
        for answer in spec.gold:
            token = answer if len(answer) > 8 else f" {answer} "
            assert token not in blob, f"{spec.id}: gold {answer[:40]!r} leaked into the brief"
        assert spec.tier not in {v for v in item.values() if isinstance(v, str)}

    # Predicates are checked as *schema tokens*, not as strings: `detects` and
    # `uses` are predicate names and also ordinary English, and the glosses are
    # supposed to say "is detected by". `schema_leakage` draws exactly that
    # line — it fires on `kill_chain_phase` and `MAPS_TO`, not on `detects`.
    leaks = rd.schema_leakage(blob)
    assert not leaks, f"schema vocabulary reached the brief file: {leaks}"

    # Checked as an exact key set rather than a substring scan. "steps" is a
    # spec field *and* an ordinary word — "the execution steps it is carried out
    # through" is a legitimate brief — so scanning for the word rejects good
    # briefs while an allow-list rejects exactly the wrong ones.
    for item in payload["items"]:
        extra = set(item) - ALLOWED_ITEM_KEYS
        assert not extra, f"unexpected keys reached the brief file: {sorted(extra)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs", type=Path, default=DEFAULT_SPECS)
    parser.add_argument("--out", type=Path, default=Path("docs/evaluation/composition/briefs"))
    parser.add_argument("--limit", type=int, default=42)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--tiers", default=None)
    parser.add_argument("--select", type=Path, default=None,
                        help="a selection.json listing spec_ids; overrides --limit/--tiers")
    parser.add_argument("--registers", default=",".join(rd.REGISTERS))
    parser.add_argument("--batches", type=int, default=3,
                        help="split each register's briefs into this many files")
    args = parser.parse_args()

    specs = load_specs(args.specs)
    if args.select:
        wanted_ids = set(json.loads(args.select.read_text())["spec_ids"])
        specs = [s for s in specs if s.id in wanted_ids]
        args.limit = None
    if args.tiers:
        wanted = {t.strip() for t in args.tiers.split(",")}
        specs = [s for s in specs if s.tier in wanted]
    specs = [s for s in specs if rd.renderable(s)]
    if args.limit:
        specs = _stratified(specs, args.limit, args.seed)
    registers = [r.strip() for r in args.registers.split(",") if r.strip() in rd.REGISTERS]

    args.out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for register in registers:
        for number, group in enumerate(partition(specs, args.batches), start=1):
            payload = {
                "instructions": INSTRUCTIONS,
                "style": rd.REGISTERS[register],
                "items": [brief_payload(spec, register) for spec in group],
            }
            _assert_no_leakage(payload, specs)
            path = args.out / f"{register}-{number:02d}.json"
            path.write_text(json.dumps(payload, indent=1) + "\n")
            written.append(f"{path} ({len(group)} items)")

    index_path = args.out / "index.json"
    index_path.write_text(
        json.dumps(
            {
                item_id(spec, register): {"spec_id": spec.id, "register": register}
                for spec in specs
                for register in registers
            },
            indent=1,
        )
        + "\n"
    )

    print(f"{len(specs)} specs x {len(registers)} registers -> {len(written)} brief files")
    print(f"  index: {index_path}")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
