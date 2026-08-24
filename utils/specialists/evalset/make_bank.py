#!/usr/bin/env python3
"""Generate a fresh question bank end to end: draw → author → compile gold.

The point of this module is to make a fairly-drawn question set **cheap**, and
the reason that matters is a methodological trap the project already walked
into once.

``docs/plans/robustness/02-holdout-question-generation.md`` warned that a blind
holdout dies silently if *"something gets fixed in response to a failure — a
template tweaked because a holdout question failed converts the experiment into
a second development set."* That is exactly what happened to holdout v1: it
found the direction defect and the join defect, both were fixed, and it stopped
being blind. The prediction was correct and the outcome was still not avoided,
because the only alternative was commissioning another thirty hand-written
questions.

So the trap is not really a discipline problem. It is a *cost* problem. A test
set that is expensive to produce will be reused past the point where it is still
valid, every time. Make it cheap and the trap disappears — burn a bank, draw
another.

Nothing here weakens the protocol. All three roles are preserved and still
separated:

* **Sampler** — ``holdout_protocol.draw``, seeded and uniform, unchanged except
  that it now accepts an exclusion set so successive banks are disjoint. It has
  to: over 59 reseeds against v1, 51% shared at least one anchor.
* **Author** — ``author.author_all``, which sees four fields of one anchor and
  nothing else. See that module for what automating this does and does not cost.
* **Compiler** — ``holdout_protocol.compile_bank``, which computes every
  expected answer from the pinned raw snapshot and *discards* an anchor whose
  gold it cannot compute rather than repairing it.

The one thing a generated bank is not is a substitute for human-authored
questions in a published headline figure — one model at one temperature explores
a narrower band of phrasing than thirty authors would. The generated dataset
card says so, and this module writes that card.

Usage::

    # a fresh 30-question bank, excluding everything ever drawn before
    uv run python -m utils.specialists.evalset.make_bank --seed 20260819

    # bigger, and put it somewhere specific
    uv run python -m utils.specialists.evalset.make_bank --seed 777 --scale 2 \\
        --out docs/evaluation/banks/bank-2026-08-19/bank.json

    # recompile gold from questions already authored, without calling any model
    uv run python -m utils.specialists.evalset.make_bank --seed 20260819 \\
        --authored docs/evaluation/banks/bank-2026-08-19/authored.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from utils.specialists.evalset.author import AuthorConfig, author_all
from utils.specialists.evalset.gold_bank import load_gold_bank
from utils.specialists.evalset.holdout_protocol import (
    REPO_ROOT,
    DrawExhausted,
    compile_bank,
    draw,
)

#: Every anchor any generated or committed bank has ever used. Committed,
#: because exclusion is only meaningful if it persists across sessions — an
#: in-memory registry would let tomorrow's bank silently re-draw today's.
REGISTRY_PATH = REPO_ROOT / "utils" / "specialists" / "evalset" / "drawn_anchors.json"

DEFAULT_BANK_DIR = REPO_ROOT / "docs" / "evaluation" / "banks"


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"banks": {}}
    return json.loads(path.read_text())


def used_anchors(registry: dict[str, Any]) -> set[str]:
    """The union of every anchor recorded across every bank in the registry."""
    out: set[str] = set()
    for entry in registry.get("banks", {}).values():
        out.update(entry.get("anchors", []))
    return out


def record_bank(
    registry: dict[str, Any], name: str, seed: int, anchors: list[str], note: str
) -> dict[str, Any]:
    registry.setdefault("banks", {})[name] = {
        "seed": seed,
        "n": len(anchors),
        "anchors": sorted(anchors),
        "note": note,
    }
    return registry


def dataset_card(bank: dict[str, Any], drawn: dict[str, Any], authored: dict[str, Any]) -> str:
    """The card that travels with a generated bank, limitations included."""
    meta = bank["meta"]
    n = len(bank["questions"])
    strata = drawn["strata"]
    retries = len(authored.get("retries") or {})
    failures = len(authored.get("failures") or {})
    return f"""# Dataset Card — generated bank, seed {meta['seed']}

**Size:** {n} questions · **Scale:** {meta.get('scale', 1)}× · **Authored by:** {authored['author_model']}
**Snapshot:** ATT&CK {meta['attack_version']} / CAPEC {meta['capec_version']}
**Excluded before drawing:** {meta.get('excluded_anchors', 0)} previously-used anchors

## What it is

A question set drawn and compiled by
`utils/specialists/evalset/make_bank.py`. Anchors were sampled uniformly from
the live id space of the pinned snapshot — {strata} by stratum — with every
anchor used by a previous bank excluded, so this set is disjoint from all of
them.

Gold is **computed, never authored**: every expected answer is derived from
`gold_bank.py`'s independent parse of the raw STIX/XML. An anchor whose gold
could not be computed was discarded rather than repaired.

## How blind it is

As blind as the hand-driven holdout v1, by the same mechanism: the Author is
shown a category description, an identifier, an entity type and a name, and
nothing else — never the templates, never the schema, never an example question.
Each question is a stateless completion with no tool access and no repository
access.

Authored questions were validated, not trusted: a question that failed to name
its own anchor, or that named any *other* MITRE identifier, was rejected and
re-requested. {retries} question(s) needed at least one retry; {failures}
anchor(s) could not be authored at all.

## What it is not

**Not a substitute for human-authored questions in a published headline figure.**
One model at one temperature explores a narrower band of phrasing than a set of
independent human authors would, and phrasing is part of what a question set
tests. This bank is a strong *regression* and *arm-comparison* instrument — it
is disjoint, fairly drawn, and mechanically scored — and a weaker basis for an
absolute claim about generalisation.

**Not immortal.** The moment a defect this bank finds gets fixed, it stops being
blind, exactly as holdout v1 did. That is expected and is no longer expensive:
draw another.

## Reproduction

```bash
uv run python -m utils.specialists.evalset.make_bank --seed {meta['seed']} \\
    --scale {meta.get('scale', 1)}
```
"""


def generate(
    *,
    seed: int,
    scale: int = 1,
    out: Path | None = None,
    authored_path: Path | None = None,
    workers: int = 8,
    model: str | None = None,
    use_exclusion: bool = True,
    registry_path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    """Draw, author and compile one bank. Returns a summary dict."""
    gold = load_gold_bank()
    registry = load_registry(registry_path)
    exclude = used_anchors(registry) if use_exclusion else set()

    try:
        drawn = draw(gold, seed=seed, exclude=exclude, scale=scale)
    except DrawExhausted as exc:
        raise SystemExit(
            f"draw exhausted: {exc}\n"
            f"{len(exclude)} anchors are already excluded. Either lower --scale, "
            f"or pass --no-exclusion to allow overlap with earlier banks."
        ) from exc

    # The registry is keyed by name, and the name comes from the path. Keying on
    # the parent directory is right for the intended `<dir>/<bank>/bank.json`
    # layout and catastrophic for a flat `<dir>/bank9001.json` one: every bank
    # collides on the parent's name, each overwrites the last, and exclusion
    # silently degrades to "exclude only the previous bank" while still printing
    # a plausible count. EXP-2026-08-015 lost five banks to exactly that before
    # a pairwise-overlap check caught it. Fall back to the file stem whenever the
    # file is not the conventional `bank.json`.
    if out is None:
        name = f"bank-seed-{seed}"
    elif out.name == "bank.json":
        name = out.parent.name
    else:
        name = out.stem
    out = out or (DEFAULT_BANK_DIR / name / "bank.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    config = AuthorConfig(model=model) if model else AuthorConfig()
    if authored_path:
        authored = json.loads(authored_path.read_text())
    else:
        authored = author_all(drawn["anchors"], config=config, workers=workers)

    bank, discards = compile_bank(
        drawn, authored["questions"], gold, author_model=authored["author_model"]
    )

    (out.parent / "anchors.json").write_text(
        json.dumps({**drawn, "discards": discards}, indent=1, ensure_ascii=False) + "\n"
    )
    (out.parent / "authored.json").write_text(
        json.dumps(authored, indent=1, ensure_ascii=False) + "\n"
    )
    out.write_text(json.dumps(bank, indent=1, ensure_ascii=False) + "\n")
    (out.parent / "CARD.md").write_text(dataset_card(bank, drawn, authored))

    # Record every anchor that was *drawn*, not just those that survived
    # compilation: a discarded anchor was still consumed, and re-drawing it in a
    # later bank would only discard it again.
    record_bank(
        registry,
        name,
        seed,
        [entry["anchor"] for entry in drawn["anchors"]],
        f"generated {len(bank['questions'])} questions, {len(discards)} discarded",
    )
    registry_path.write_text(json.dumps(registry, indent=1, ensure_ascii=False) + "\n")

    return {
        "bank": str(out),
        "questions": len(bank["questions"]),
        "discards": discards,
        "retries": len(authored.get("retries") or {}),
        "failures": authored.get("failures") or {},
        "excluded": len(exclude),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a fresh, fairly-drawn, mechanically-scored question bank."
    )
    parser.add_argument("--seed", type=int, required=True, help="draw seed; use a new one per bank")
    parser.add_argument("--scale", type=int, default=1, help="1 = 30 questions, 2 = 60, …")
    parser.add_argument("--out", type=Path, default=None, help="path for the bank json")
    parser.add_argument(
        "--authored", type=Path, default=None,
        help="reuse an existing authored.json instead of calling the Author model",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--model", default=None, help="Author model; must not be the pipeline's")
    parser.add_argument(
        "--no-exclusion", action="store_true",
        help="allow anchors used by earlier banks (not recommended — 51%% of reseeds collide)",
    )
    parser.add_argument("--dry-run", action="store_true", help="draw only; author nothing")
    args = parser.parse_args(argv)

    if args.dry_run:
        gold = load_gold_bank()
        exclude = set() if args.no_exclusion else used_anchors(load_registry())
        drawn = draw(gold, seed=args.seed, exclude=exclude, scale=args.scale)
        print(f"would draw {len(drawn['anchors'])} anchors, excluding {len(exclude)}")
        for entry in drawn["anchors"]:
            print(f"  {entry['id']:<12} {entry['category']:<21} {entry['anchor']}")
        return 0

    summary = generate(
        seed=args.seed, scale=args.scale, out=args.out, authored_path=args.authored,
        workers=args.workers, model=args.model, use_exclusion=not args.no_exclusion,
    )
    print(f"wrote {summary['bank']}: {summary['questions']} questions")
    print(f"  excluded {summary['excluded']} previously-drawn anchors")
    if summary["retries"]:
        print(f"  {summary['retries']} question(s) needed an Author retry")
    for discard in summary["discards"]:
        print(f"  DISCARDED {discard.get('id')}: {discard.get('reason')}")
    for case, why in (summary["failures"] or {}).items():
        print(f"  AUTHOR FAILED {case}: {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
