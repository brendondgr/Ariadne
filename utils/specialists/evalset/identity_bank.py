#!/usr/bin/env python3
"""Draw, author and compile a blind question bank against the identity schema.

The three roles ``make_bank.py`` separates are preserved here, and one agent
never holds two:

**Sampler** — :func:`draw`, seeded and uniform over populations taken from the
blueprint, never curated. Nothing is weighted by degree or by how interesting an
anchor looks; the development catalogue's federated anchors were explicitly
chosen for richness and reproducing that here would rebuild the co-authorship
bias the blind protocol exists to remove.

**Author** — :func:`author_all`, which sees the four fields in
``GoldEntry.author_view`` and nothing else: label, name, relationship,
direction. It never sees the expected answer, the templates, the schema, or any
other question. That is what keeps the bank blind.

**Compiler** — :func:`compile_bank`, which pairs authored text with gold that
was computed from the blueprint before any question existed. An anchor whose
gold cannot be computed is **discarded, not repaired**, and the discard is
logged, because a high discard rate is itself a finding about the join surface.

Why this is a sibling of ``holdout_protocol`` rather than a parameterisation of
it: that module's populations, strata and categories are ATT&CK and CAPEC by
construction (techniques, patterns, bridged CWEs). Generalising it would mean
editing code that four recorded experiments depend on, to serve a fifth. The
protocol is what transfers, not the implementation.

Authoring is the only step here that needs a language model, and it is the cheap
half — one short call per question. It checkpoints per question and resumes from
partial output, because the shared inference server is under contention and a
mid-bank failure should cost one question rather than the bank.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable

from utils.kg_builder.catalog.declared import DECLARED
from utils.kg_builder.synthetic.spec import TenantSpec

from .identity_gold import (
    DESCRIBE,
    FACET_IN,
    FACET_OUT,
    HOMO_IN,
    HOMO_OUT,
    MULTIHOP,
    UNANSWERABLE,
    GoldEntry,
    describe_gold,
    facet_gold,
    multihop_gold,
    unanswerable_gold,
)

IDENTITY_SEED = 20260821

# How many questions of each kind. Weighted toward the facet kinds because they
# are where H1 and H3 live, and deliberately not uniform: `homo-*` gets a third
# of the bank between them because eight declared triples is a small population
# and a thin sample there would leave H3 untestable.
BANK_SHAPE: dict[str, int] = {
    DESCRIBE: 4,
    FACET_OUT: 6,
    FACET_IN: 6,
    HOMO_OUT: 5,
    HOMO_IN: 5,
    MULTIHOP: 2,
    UNANSWERABLE: 2,
}

# Properties that make a sensible describe question -- ones a human would ask
# about. Drawn from what the catalog actually declares on USER, GROUP, DEVICE.
_DESCRIBE_PROPS = (
    "user.ldap_person.department",
    "user.ldap_person.location.city",
    "user.name",
    "group.name",
    "group.privileges",
    "active_directory__device_os_name",
)


def _homogeneous_edges(spec: TenantSpec) -> list[tuple[str, str, str]]:
    """Declared triples whose endpoints share a label, as realised in the tenant.

    Filtered to ``DECLARED`` because H3 is a claim about ReliaQuest's schema and
    one of this project's inferred edges (``GROUP -MEMBER_OF-> GROUP``) is
    homogeneous too. Measuring over both would mix a finding about the customer's
    schema with a finding about our own reconstruction.
    """
    seen: set[tuple[str, str, str]] = set()
    for record in spec.edges:
        if record["origin"] != DECLARED:
            continue
        triple = spec.triple_of(record)
        if triple[0] == triple[2]:
            seen.add(triple)
    return sorted(seen)


def _heterogeneous_edges(spec: TenantSpec) -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    for record in spec.edges:
        if record["origin"] != DECLARED:
            continue
        triple = spec.triple_of(record)
        if triple[0] != triple[2]:
            seen.add(triple)
    return sorted(seen)


def _anchors_with_edge(
    spec: TenantSpec, triple: tuple[str, str, str], direction: str
) -> list[str]:
    """Nodes that actually have this edge in the stated direction.

    Anchors are drawn only from nodes whose answer is non-empty, because a
    facet question whose gold is empty measures abstention rather than
    retrieval and would silently dilute H1.
    """
    source_label, edge, target_label = triple
    want_label = source_label if direction == "out" else target_label
    out: list[str] = []
    for node_id, node in spec.nodes.items():
        if node["label"] != want_label:
            continue
        if spec.neighbours(node_id, edge=edge, direction=direction):
            out.append(node_id)
    return sorted(out)


def draw(
    spec: TenantSpec,
    *,
    seed: int = IDENTITY_SEED,
    shape: dict[str, int] | None = None,
) -> tuple[list[GoldEntry], list[dict[str, Any]]]:
    """The seeded draw. Same seed, same anchors, same gold.

    Returns ``(entries, discards)``. Gold is computed here, from the blueprint,
    *before* any question text exists — so no question can have been shaped by
    knowing what its answer would be.
    """
    rng = random.Random(seed)
    plan = dict(BANK_SHAPE)
    if shape:
        plan.update(shape)

    entries: list[GoldEntry] = []
    discards: list[dict[str, Any]] = []
    used_anchors: set[tuple[str, str, str]] = set()
    counter = {kind: 0 for kind in plan}

    def qid(kind: str) -> str:
        counter[kind] += 1
        return f"ID-{kind.upper().replace('-', '')}-{counter[kind]:02d}"

    def take(
        kind: str,
        candidates: list[tuple[str, str, str]],
        builder: Callable[[str, tuple[str, str, str]], GoldEntry],
        direction: str,
        wanted: int,
    ) -> None:
        if not candidates:
            discards.append({"kind": kind, "reason": "no realised triple of this shape"})
            return
        attempts = 0
        made = 0
        while made < wanted and attempts < wanted * 40:
            attempts += 1
            triple = rng.choice(candidates)
            anchors = _anchors_with_edge(spec, triple, direction)
            if not anchors:
                continue
            anchor = rng.choice(anchors)
            key = (anchor, triple[1], direction)
            if key in used_anchors:
                continue
            used_anchors.add(key)
            entry = builder(anchor, triple)
            if not entry.expected_ids:
                discards.append(
                    {"kind": kind, "anchor": anchor, "reason": "gold came out empty"}
                )
                continue
            entries.append(entry)
            made += 1
        if made < wanted:
            discards.append(
                {"kind": kind, "reason": f"only {made} of {wanted} anchors available"}
            )

    homo = _homogeneous_edges(spec)
    hetero = _heterogeneous_edges(spec)

    # Every builder passes the triple's neighbour label, so gold is scoped to
    # one triple rather than to one edge name. In this schema a single label
    # spans up to six triples (ALL_EXTENDED_RIGHTS reaches six target labels),
    # so scoping is what keeps a homogeneous question homogeneous.
    take(FACET_OUT, hetero,
         lambda a, t: facet_gold(spec, a, t[1], "out", qid(FACET_OUT), FACET_OUT, t[2]),
         "out", plan[FACET_OUT])
    take(FACET_IN, hetero,
         lambda a, t: facet_gold(spec, a, t[1], "in", qid(FACET_IN), FACET_IN, t[0]),
         "in", plan[FACET_IN])
    take(HOMO_OUT, homo,
         lambda a, t: facet_gold(spec, a, t[1], "out", qid(HOMO_OUT), HOMO_OUT, t[2]),
         "out", plan[HOMO_OUT])
    take(HOMO_IN, homo,
         lambda a, t: facet_gold(spec, a, t[1], "in", qid(HOMO_IN), HOMO_IN, t[0]),
         "in", plan[HOMO_IN])

    # describe: a node and one of its declared properties.
    made = 0
    attempts = 0
    while made < plan[DESCRIBE] and attempts < plan[DESCRIBE] * 60:
        attempts += 1
        prop = rng.choice(_DESCRIBE_PROPS)
        candidates = [
            n for n, v in spec.nodes.items() if prop in v["properties"]
        ]
        if not candidates:
            continue
        anchor = rng.choice(sorted(candidates))
        if (anchor, prop, "describe") in used_anchors:
            continue
        used_anchors.add((anchor, prop, "describe"))
        entries.append(describe_gold(spec, anchor, prop, qid(DESCRIBE)))
        made += 1

    # multihop: planted chains, sampled without replacement.
    names = sorted(p.name for p in spec.planted_paths)
    rng.shuffle(names)
    for name in names[: plan[MULTIHOP]]:
        entries.append(multihop_gold(spec, name, qid(MULTIHOP)))

    # unanswerable: a label that exists and has no traversable edge at all. 57
    # of the catalog's 72 labels qualify, all of them a consequence of the
    # export's inner join.
    reachable = {t for r in spec.edges for t in (r["source_id"], r["target_id"])}
    isolated = sorted(
        {
            n
            for n, v in spec.nodes.items()
            if n not in reachable
        }
    )
    for _ in range(plan[UNANSWERABLE]):
        if not isolated:
            discards.append({"kind": UNANSWERABLE, "reason": "no isolated node"})
            break
        anchor = rng.choice(isolated)
        isolated.remove(anchor)
        entries.append(
            unanswerable_gold(
                spec,
                anchor,
                "MEMBER_OF",
                qid(UNANSWERABLE),
                note=(
                    f"{spec.label_of(anchor)} declares no relationship of any kind "
                    "in the delivered catalog. The correct answer is an abstention "
                    "carrying the executed query, not rows and not a guess."
                ),
            )
        )

    return entries, discards


# --------------------------------------------------------------------------
# Author
# --------------------------------------------------------------------------

AUTHOR_SYSTEM = """You are writing evaluation questions for a security analyst \
tool that answers questions about an identity graph (Active Directory, Entra, \
Okta, AWS, GCP).

You will be shown four facts about ONE entity and nothing else. Write ONE \
natural question a security analyst would actually ask, which those facts would \
answer.

Rules:
- Name the entity by its name so the question is anchored.
- Phrase it the way a human would, not as a database query.
- Do NOT invent details you were not given.
- Do NOT mention labels, schemas, relationships types in SCREAMING_CASE, or \
directions. Say "owns" not "OWNS", "is a member of" not "MEMBER_OF (out)".
- Output ONLY the question. No preamble, no quotes, no explanation."""


def author_prompt(view: dict[str, Any]) -> str:
    """The four fields the author is allowed to see. Nothing else is passed."""
    lines = [f"entity name: {view.get('name')}", f"entity kind: {view.get('label')}"]
    if view.get("property") is not None:
        lines.append(f"attribute of interest: {view['property']}")
        lines.append(f"its value: {view.get('value')}")
    else:
        lines.append(f"relationship of interest: {view.get('relationship')}")
        lines.append(
            "direction: "
            + (
                "this entity is the one doing it"
                if view.get("direction") == "out"
                else "this entity is the one it is done to"
            )
        )
    return "\n".join(lines)


def author_all(
    entries: list[GoldEntry],
    call: Callable[[str, str], str],
    checkpoint: str | Path | None = None,
) -> dict[str, str]:
    """Author every question, resuming from ``checkpoint`` if it exists.

    ``call(system, user) -> str`` is injected so this module never imports an
    LLM client and the tests never need one. Checkpointing is per question, and
    the file is rewritten after each success: the shared server is contended,
    and a failure at question 25 should not cost the previous 24.
    """
    path = Path(checkpoint) if checkpoint else None
    authored: dict[str, str] = {}
    if path and path.is_file():
        authored = json.loads(path.read_text(encoding="utf-8"))

    for entry in entries:
        if entry.question_id in authored:
            continue
        text = call(AUTHOR_SYSTEM, author_prompt(entry.author_view)).strip()
        # A model that returns nothing has not authored a question; recording an
        # empty string would create an unanswerable question by accident and
        # quietly depress the score.
        if not text:
            continue
        authored[entry.question_id] = text
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(authored, indent=2) + "\n", encoding="utf-8")
    return authored


# --------------------------------------------------------------------------
# Compiler
# --------------------------------------------------------------------------


def compile_bank(
    entries: list[GoldEntry],
    authored: dict[str, str],
    *,
    seed: int = IDENTITY_SEED,
    author_model: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Pair authored text with blueprint gold. Returns ``(bank, discards)``."""
    questions: dict[str, Any] = {}
    discards: list[dict[str, Any]] = []
    for entry in entries:
        text = authored.get(entry.question_id)
        if not text:
            discards.append(
                {"question_id": entry.question_id, "reason": "no authored text"}
            )
            continue
        record = entry.to_dict()
        record["question"] = text
        record["split"] = "identity-blind"
        questions[entry.question_id] = record
    bank = {
        "meta": {
            "dataset": "identity",
            "seed": seed,
            "author_model": author_model or "unknown",
            "split": "identity-blind",
            "protocol": (
                "Sampler, author and compiler are separate. The author saw four "
                "fields of one anchor and nothing else -- never the expected "
                "answer, the templates, the schema, or another question. Gold "
                "was computed from the generator blueprint before any question "
                "text existed."
            ),
        },
        "questions": questions,
    }
    return bank, discards


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------


def _skynet_caller(
    base_url: str, model: str, max_tokens: int, timeout: float
) -> Callable[[str, str], str]:
    """An OpenAI-compatible caller for the local relay.

    ``max_tokens`` defaults high because the served model is a *reasoning*
    model: it spends tokens on a reasoning trace before emitting content, and a
    small budget truncates mid-trace and returns an empty string. An empty reply
    reads as "the model declined" when it actually means "the budget was too
    small", so the floor here is deliberately generous for a one-line answer.
    """
    import httpx

    def call(system: str, user: str) -> str:
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return (payload["choices"][0]["message"].get("content") or "").strip()

    return call


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Draw, author and compile the identity question bank."
    )
    parser.add_argument("--seed", type=int, default=IDENTITY_SEED)
    parser.add_argument(
        "--spec", default="data-identity/graphs/identity/canonical/spec.json"
    )
    parser.add_argument("--out", default="docs/evaluation/identity-2026-08-21")
    parser.add_argument("--base-url", default=os.environ.get("EVAL_LLM_BASE_URL", "http://localhost:4000/v1"))
    parser.add_argument("--model", default=os.environ.get("EVAL_LLM_MODEL", "skynet"))
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="draw and write gold, but do not author (no model needed)",
    )
    args = parser.parse_args(argv)

    spec = TenantSpec.read(args.spec)
    entries, discards = draw(spec, seed=args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from .identity_gold import write_gold

    write_gold(
        entries,
        out / "gold.json",
        meta={
            "dataset": "identity",
            "seed": args.seed,
            "spec": args.spec,
            "derivation": "from the generator blueprint, never from the loaded graph",
        },
    )
    (out / "discards.json").write_text(
        json.dumps(discards, indent=2) + "\n", encoding="utf-8"
    )
    print(f"drew {len(entries)} questions, {len(discards)} discards")
    for kind in sorted({e.kind for e in entries}):
        print(f"  {kind:14s} {sum(1 for e in entries if e.kind == kind)}")

    if args.dry_run:
        print("\n--dry-run: gold written, authoring skipped")
        return 0

    caller = _skynet_caller(args.base_url, args.model, args.max_tokens, args.timeout)
    authored = author_all(entries, caller, checkpoint=out / "authored.json")
    print(f"\nauthored {len(authored)}/{len(entries)}")

    bank, compile_discards = compile_bank(
        entries, authored, seed=args.seed, author_model=args.model
    )
    (out / "bank.json").write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")
    if compile_discards:
        print(f"compile discards: {len(compile_discards)}")
    print(f"wrote {out / 'bank.json'} with {len(bank['questions'])} questions")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
