#!/usr/bin/env python3
"""The blind-holdout protocol: seeded anchor sampling and the Author prompt.

This module is the *sampler* role of
``docs/plans/robustness/02-holdout-question-generation.md`` and the execution
brief ``04-holdout-execution-brief.md``. It is committed because it is part of
the artifact: a human-authored holdout cannot be re-run, but this one can, and a
reviewer can regenerate the entire draw and confirm the anchors really were
sampled uniformly rather than picked for richness.

Three things this module deliberately does NOT do:

* It never weights by degree, mapping count, fame or category. The existing
  federated bank selected CWE anchors *because* "many famous web CWEs bridge
  only to unmapped patterns and would be empty chains"
  (``federated_questions.py``); reproducing that selection here would reproduce
  the very bias the holdout exists to detect.
* It never filters unmapped CAPEC patterns out. 381 of the 558 live patterns
  carry no ATT&CK mapping, and for those the *correct* system behaviour is an
  abstention carrying the executed query — a capability the system has. Those
  are the most informative anchors in the set, so the federated stratum is
  over-drawn and **partitioned**, not filtered.
* It never writes question text. That is the Author's job, and the Author is a
  separate agent with a hard context restriction.

Populations come from the committed ``gold_bank.json``, which is itself derived
from the pinned raw snapshot rather than from the loaded graph, so the draw is
independent of both the ingest and the specialists.

Run with::

    uv run python -m utils.specialists.evalset.holdout_protocol
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from utils.specialists.evalset.gold_bank import GOLD_BANK_PATH, load_gold_bank

REPO_ROOT = Path(__file__).resolve().parents[3]
ANCHORS_PATH = REPO_ROOT / "docs" / "evaluation" / "holdout-v1" / "anchors.json"

# The draw seed. **This must never change.** Changing it silently invalidates
# every holdout figure, because the anchors would no longer be the ones the
# committed `anchors.json` timestamped as drawn before authoring. Deliberately
# not 1729, which `utils/evaluation/stats.py` already uses for bootstrap
# resampling — two different seeds doing two different jobs must not be
# confused for one another.
HOLDOUT_SEED = 20260805

#: Stratum sizes, matching the existing bank's 46/34/40 source proportions
#: scaled to 30 questions (plan §2.2).
STRATA = {"attack": 12, "capec": 8, "federated": 10}

#: Federated partition targets (plan §2.4). The stratum is over-drawn from the
#: seeded sequence until both partitions are full.
FEDERATED_ANSWERABLE = 6
FEDERATED_ABSTENTION = 4

#: Category labels handed to the Author, verbatim from plan §5. The Author sees
#: the label and the "ask for" text and nothing else — no example questions,
#: because phrasing style is itself a leak.
ATTACK_CATEGORIES: dict[str, str] = {
    "mitigations": "The mitigations listed for a technique",
    "groups": "The techniques a named group uses, or the groups using a technique",
    "software": "The techniques a piece of software implements",
    "detection": "How a technique is detected — data components, analytics",
    "tactics": "The tactics a technique belongs to",
    "subtechnique": "The parent/child relationship around a sub-technique",
    "lookup": "A plain description of one entity",
}

CAPEC_CATEGORIES: dict[str, str] = {
    "mapping": "The ATT&CK techniques a pattern maps to",
    "weakness": "The CWEs a pattern exploits",
    "hierarchy": "The abstraction chain — Detailed → Standard → Meta",
    "execution": "The execution steps of a pattern",
    "consequence": "The consequences a pattern carries",
    "prerequisite": "What a pattern requires",
    "lookup": "A plain description of one pattern",
}

FEDERATED_CATEGORIES: dict[str, str] = {
    "pattern-to-mitigation": (
        "From a CAPEC pattern, through its ATT&CK techniques, to mitigations"
    ),
    "reverse-mapping": (
        "From an ATT&CK technique back to the patterns referencing it"
    ),
    "cwe-chain": "From a CWE, through patterns, to ATT&CK techniques",
}

#: Federated category -> how many of the 10 federated anchors it takes.
FEDERATED_SPLIT = {"pattern-to-mitigation": 4, "reverse-mapping": 3, "cwe-chain": 3}

#: Short id segment per category, for the `H-<SEG>-NN` ids.
ID_SEGMENT: dict[str, str] = {
    "mitigations": "MIT", "groups": "GRP", "software": "SW", "detection": "DET",
    "tactics": "TAC", "subtechnique": "SUB", "lookup": "LKP",
    "mapping": "MAP", "weakness": "CWE", "hierarchy": "ABS",
    "execution": "EXE", "consequence": "CSQ", "prerequisite": "PRE",
    "pattern-to-mitigation": "CTM", "reverse-mapping": "REV", "cwe-chain": "CHN",
}


def _sha256_of(items: list[str]) -> str:
    """SHA256 over a population list, so a reviewer can confirm the snapshot."""
    payload = "\n".join(items).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# populations
# ---------------------------------------------------------------------------


def attack_population(gold: dict[str, Any]) -> list[str]:
    """Every live Technique and SubTechnique id in the pinned ATT&CK snapshot.

    ``gold_bank`` already applied the exclude-at-load policy, so revoked and
    deprecated objects are absent by construction rather than by a filter here.
    """
    objects = gold["attack"]["objects"]
    return sorted(
        cid for cid, obj in objects.items()
        if obj["label"] in ("Technique", "SubTechnique")
    )


def capec_population(gold: dict[str, Any]) -> list[str]:
    """Every live CAPEC AttackPattern id, *including* the unmapped majority."""
    return sorted(gold["capec"]["patterns"], key=lambda c: int(c.split("-")[1]))


def cwe_population(gold: dict[str, Any]) -> list[str]:
    """Every bridged weakness, with no filtering for a terminating chain."""
    return sorted(gold["capec"]["cwe_to_capec"], key=lambda c: int(c.split("-")[1]))


# ---------------------------------------------------------------------------
# neighbour resolution — the same maps the Compiler later turns into gold
# ---------------------------------------------------------------------------


def _reverse(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    for src, targets in mapping.items():
        for tgt in targets:
            out.setdefault(tgt, set()).add(src)
    return {k: sorted(v) for k, v in out.items()}


def _subtechnique_neighbours(gold: dict[str, Any], anchor: str) -> list[str]:
    """Children for a parent Technique, the parent for a SubTechnique."""
    subs = gold["attack"]["subtechniques"]
    if anchor in subs:
        return sorted(subs[anchor])
    return sorted(p for p, kids in subs.items() if anchor in kids)


def _hierarchy_ancestors(gold: dict[str, Any], anchor: str) -> list[str]:
    """The transitive ChildOf chain upward — Detailed → Standard → Meta."""
    hierarchy = gold["capec"]["hierarchy"]
    seen: list[str] = []
    frontier = list(hierarchy.get(anchor, {}).get("ChildOf", []))
    while frontier:
        node = frontier.pop(0)
        if node in seen:
            continue
        seen.append(node)
        frontier.extend(hierarchy.get(node, {}).get("ChildOf", []))
    return sorted(seen)


def live_mappings(gold: dict[str, Any], cid: str) -> list[str]:
    """A pattern's ATTACK-taxonomy T-ids that also exist on the ATT&CK side.

    Mirrors ``federated_questions._live_mappings`` exactly — the intersection,
    not the CAPEC-side claim, because a mapping to a technique ATT&CK has since
    revoked is not a live join.
    """
    attack = gold["attack"]["objects"]
    return [t for t in gold["capec"]["attack_mappings"].get(cid, []) if t in attack]


def neighbours(gold: dict[str, Any], category: str, anchor: str) -> list[str]:
    """The resolved neighbour set for one (category, anchor), from gold_bank only."""
    attack, capec = gold["attack"], gold["capec"]
    if category == "mitigations":
        return sorted(attack["technique_mitigations"].get(anchor, []))
    if category == "groups":
        return _reverse(attack["group_techniques"]).get(anchor, [])
    if category == "software":
        return _reverse(attack["software_techniques"]).get(anchor, [])
    if category == "detection":
        return sorted(attack["technique_detections"].get(anchor, []))
    if category == "tactics":
        return sorted(attack["technique_tactics"].get(anchor, []))
    if category == "subtechnique":
        return _subtechnique_neighbours(gold, anchor)
    if category == "mapping":
        return live_mappings(gold, anchor)
    if category == "weakness":
        return sorted(capec["related_weaknesses"].get(anchor, []))
    if category == "hierarchy":
        return _hierarchy_ancestors(gold, anchor)
    if category == "execution":
        return [s["node_id"] for s in capec["execution_steps"].get(anchor, [])]
    if category == "consequence":
        return [c["node_id"] for c in capec["consequences"].get(anchor, [])]
    if category == "prerequisite":
        # gold_bank parses Skills_Required, which is the machine-readable form
        # of "what a pattern requires"; free-text <Prerequisites> is not a node.
        return [s["node_id"] for s in capec["skills"].get(anchor, [])]
    if category == "lookup":
        return []
    raise ValueError(f"unknown single-source category {category!r}")


def federated_correlation(gold: dict[str, Any], category: str, anchor: str) -> list[str]:
    """The cross-source join ids for a federated anchor — empty means abstain."""
    capec = gold["capec"]
    if category == "pattern-to-mitigation":
        return live_mappings(gold, anchor)
    if category == "reverse-mapping":
        return [anchor] if any(
            anchor in live_mappings(gold, cid) for cid in capec["patterns"]
        ) else []
    if category == "cwe-chain":
        out: set[str] = set()
        for cid in capec["cwe_to_capec"].get(anchor, []):
            out.update(live_mappings(gold, cid))
        return sorted(out)
    raise ValueError(f"unknown federated category {category!r}")


# ---------------------------------------------------------------------------
# the draw
# ---------------------------------------------------------------------------


def _feasible(gold: dict[str, Any], population: list[str], category: str) -> list[str]:
    """Anchors for which this category resolves to a non-empty neighbour set.

    Category is drawn first and the anchor uniformly *within* the category's
    feasible sub-population. This is the one place the draw is conditioned on
    the data, and it is conditioned only on "the relation exists at all" — never
    on how many neighbours there are. Asking for the mitigations of a technique
    that has none is not a hard question, it is a malformed one, and the two
    federated strata are where honest-empty behaviour is measured instead.
    """
    if category == "lookup":
        return list(population)
    return [a for a in population if neighbours(gold, category, a)]


def _category_allocation(count: int, categories: list[str], rng: random.Random) -> list[str]:
    """Spread ``count`` draws as evenly as possible over ``categories``."""
    order = list(categories)
    rng.shuffle(order)
    out: list[str] = []
    while len(out) < count:
        out.extend(order[: count - len(out)])
    return out


def _draw_single_source(
    gold: dict[str, Any],
    *,
    stratum: str,
    population: list[str],
    categories: dict[str, str],
    count: int,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drawn: list[dict[str, Any]] = []
    overdraw: list[dict[str, Any]] = []
    used: set[str] = set()
    for category in _category_allocation(count, list(categories), rng):
        feasible = _feasible(gold, population, category)
        while True:
            anchor = feasible[rng.randrange(len(feasible))]
            if anchor not in used:
                break
            overdraw.append({
                "stratum": stratum, "category": category, "anchor": anchor,
                "reason": "already drawn in this stratum",
            })
        used.add(anchor)
        drawn.append({
            "stratum": stratum,
            "category": category,
            "anchor": anchor,
            "feasible_population": len(feasible),
        })
    return drawn, overdraw


def _draw_federated(
    gold: dict[str, Any],
    *,
    populations: dict[str, list[str]],
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Over-draw and partition, rather than filter (plan §2.4).

    Every category is sampled uniformly over its FULL population — unmapped
    patterns included — and each draw is classified by whether the chain
    terminates in a live ATT&CK technique. Draws are kept until both partitions
    are full; the surplus is recorded as over-draw so the partition is visible
    as a partition rather than as a selection.
    """
    source_of = {
        "pattern-to-mitigation": "capec",
        "reverse-mapping": "attack",
        "cwe-chain": "cwe",
    }
    quota = {
        cat: {
            "answerable": round(FEDERATED_ANSWERABLE * n / STRATA["federated"]),
            "abstention-expected": round(FEDERATED_ABSTENTION * n / STRATA["federated"]),
        }
        for cat, n in FEDERATED_SPLIT.items()
    }
    drawn: list[dict[str, Any]] = []
    overdraw: list[dict[str, Any]] = []
    used: set[str] = set()
    for category, wanted in quota.items():
        population = populations[source_of[category]]
        filled = {"answerable": 0, "abstention-expected": 0}
        while sum(filled.values()) < FEDERATED_SPLIT[category]:
            anchor = population[rng.randrange(len(population))]
            correlate = federated_correlation(gold, category, anchor)
            partition = "answerable" if correlate else "abstention-expected"
            if anchor in used:
                reason = "already drawn"
            elif filled[partition] >= wanted[partition]:
                reason = f"{partition} quota already full"
            else:
                used.add(anchor)
                filled[partition] += 1
                drawn.append({
                    "stratum": "federated",
                    "category": category,
                    "anchor": anchor,
                    "partition": partition,
                    "correlation_size": len(correlate),
                    "feasible_population": len(population),
                })
                continue
            overdraw.append({
                "stratum": "federated", "category": category,
                "anchor": anchor, "partition": partition, "reason": reason,
            })
    return drawn, overdraw


def draw(gold: dict[str, Any] | None = None, *, seed: int = HOLDOUT_SEED) -> dict[str, Any]:
    """The full seeded draw. Deterministic: same seed, same bank, same anchors."""
    gold = gold if gold is not None else load_gold_bank()
    populations = {
        "attack": attack_population(gold),
        "capec": capec_population(gold),
        "cwe": cwe_population(gold),
    }
    rng = random.Random(seed)

    attack_drawn, attack_over = _draw_single_source(
        gold, stratum="attack", population=populations["attack"],
        categories=ATTACK_CATEGORIES, count=STRATA["attack"], rng=rng,
    )
    capec_drawn, capec_over = _draw_single_source(
        gold, stratum="capec", population=populations["capec"],
        categories=CAPEC_CATEGORIES, count=STRATA["capec"], rng=rng,
    )
    fed_drawn, fed_over = _draw_federated(gold, populations=populations, rng=rng)

    anchors = attack_drawn + capec_drawn + fed_drawn
    counts: dict[str, int] = {}
    for entry in anchors:
        seg = ID_SEGMENT[entry["category"]]
        counts[seg] = counts.get(seg, 0) + 1
        entry["id"] = f"H-{seg}-{counts[seg]:02d}"
        entry["name"] = entity_name(gold, entry["anchor"])
        entry["entity_type"] = entity_type(gold, entry["anchor"])
    for index, entry in enumerate(anchors):
        entry["draw_index"] = index

    return {
        "seed": seed,
        "protocol": "utils/specialists/evalset/holdout_protocol.py",
        "gold_bank": str(GOLD_BANK_PATH.relative_to(REPO_ROOT)),
        "snapshot": {
            "attack_version": gold["meta"]["attack_version"],
            "capec_version": gold["meta"]["capec_version"],
            "checksums": gold["meta"]["checksums"],
        },
        "strata": dict(STRATA),
        "federated_targets": {
            "answerable": FEDERATED_ANSWERABLE,
            "abstention-expected": FEDERATED_ABSTENTION,
        },
        "populations": {
            name: {"size": len(items), "sha256": _sha256_of(items)}
            for name, items in populations.items()
        },
        "anchors": anchors,
        "overdraw": attack_over + capec_over + fed_over,
        "discards": [],
    }


# ---------------------------------------------------------------------------
# entity naming — the only snapshot fact the Author is given
# ---------------------------------------------------------------------------


def entity_name(gold: dict[str, Any], anchor: str) -> str:
    if anchor.startswith("CAPEC-"):
        return gold["capec"]["patterns"][anchor]["name"]
    if anchor.startswith("CWE-"):
        return anchor  # CWE names are not in the CAPEC catalog; the id is canonical
    return gold["attack"]["objects"][anchor]["name"]


def entity_type(gold: dict[str, Any], anchor: str) -> str:
    if anchor.startswith("CAPEC-"):
        return "AttackPattern"
    if anchor.startswith("CWE-"):
        return "Weakness"
    return gold["attack"]["objects"][anchor]["label"]


# ---------------------------------------------------------------------------
# the Author prompt
# ---------------------------------------------------------------------------

AUTHOR_MODEL = "claude-fable-5 (high effort)"

#: The prompt handed to every Author subagent. It contains an anchor, a type, a
#: snapshot name, one category description and the reference-discipline rule —
#: and deliberately nothing else. No repository path, no file name, no example
#: question, no template identifier appears anywhere in it. That absence IS the
#: write-lock of plan §3: it is enforced by what the prompt contains, not by
#: asking an agent to avert its eyes.
AUTHOR_PROMPT_TEMPLATE = """\
You are a cybersecurity analyst writing ONE question for a question set.

Write the single question a working analyst would actually type when they want:

  {category_description}

about this entity:

  Identifier: {anchor}
  Entity type: {entity_type}
  Name as it appears in the catalogue: {name}

Rules, all binding:

1. Reference the entity by its canonical identifier AND, on first mention, by
   the catalogue name exactly as given above — for example
   "CAPEC-150 (Collect Data from Common Resource Locations)". Never by
   description alone, and never by a name that differs from the one above.
2. Use no other identifier, entity, or fact. In particular do not name any
   other technique, pattern, weakness, group, piece of software, or mitigation,
   and do not state or guess what the answer is.
3. Do not consult any external source, any file, any tool, or your own recall
   of MITRE content. Everything you need is in this prompt. Long-tail
   identifier recall is unreliable and a question built on it would be
   unanswerable through no fault of the system under test.
4. Write it as a security analyst would type it — natural length, natural
   phrasing. Do not signal a category, a query shape, or a data model in the
   wording.

Return ONLY the question text. No preamble, no quotes, no explanation, no
answer, no expected result, no difficulty rating, no metadata.
"""


def author_prompt(anchor_entry: dict[str, Any]) -> str:
    """Build the Author prompt for one drawn anchor."""
    category = anchor_entry["category"]
    descriptions = {**ATTACK_CATEGORIES, **CAPEC_CATEGORIES, **FEDERATED_CATEGORIES}
    return AUTHOR_PROMPT_TEMPLATE.format(
        category_description=descriptions[category],
        anchor=anchor_entry["anchor"],
        entity_type=anchor_entry["entity_type"],
        name=anchor_entry["name"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Draw the blind-holdout anchors.")
    parser.add_argument("--out", type=Path, default=ANCHORS_PATH)
    parser.add_argument("--seed", type=int, default=HOLDOUT_SEED)
    args = parser.parse_args()

    result = draw(seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}")
    for name, info in result["populations"].items():
        print(f"  population {name}: {info['size']} (sha256 {info['sha256'][:16]}…)")
    for entry in result["anchors"]:
        part = f" [{entry['partition']}]" if "partition" in entry else ""
        print(f"  {entry['id']:<12} {entry['category']:<21} {entry['anchor']}{part}")
    print(f"  over-draws: {len(result['overdraw'])}")


if __name__ == "__main__":
    main()
