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
    # Direction matters here and it was wrong until 2026-08-19. The anchor in
    # this stratum is always a Technique and the gold is always the *software*
    # ids that implement it, but this text asked for the opposite and produced
    # questions like "What techniques does T1555.005 (Password Managers)
    # implement?" — unanswerable, and scored against a software gold. `groups`
    # escaped the same trap only by naming both directions.
    "software": "The software observed implementing a technique",
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


class DrawExhausted(RuntimeError):
    """No un-drawn anchor remains for a category.

    Reached only when the exclusion set has eaten a category's feasible
    sub-population. Raised rather than silently returning a short bank, because
    a bank that is quietly smaller than asked for is a bank whose figures are
    not comparable to the last one.
    """


#: Safety net on the rejection-sampling loops. Only fires if the exclusion set
#: has made a category effectively undrawable; at 1x scale with no exclusions
#: the loops settle in a handful of iterations.
_MAX_DRAW_ATTEMPTS = 100_000


def _feasible(
    gold: dict[str, Any],
    population: list[str],
    category: str,
    exclude: frozenset[str] = frozenset(),
) -> list[str]:
    """Anchors for which this category resolves to a non-empty neighbour set.

    Category is drawn first and the anchor uniformly *within* the category's
    feasible sub-population. This is the one place the draw is conditioned on
    the data, and it is conditioned only on "the relation exists at all" — never
    on how many neighbours there are. Asking for the mitigations of a technique
    that has none is not a hard question, it is a malformed one, and the two
    federated strata are where honest-empty behaviour is measured instead.
    """
    if category == "lookup":
        candidates = list(population)
    else:
        candidates = [a for a in population if neighbours(gold, category, a)]
    # Guarded so that an empty exclusion set is a no-op on the returned list —
    # `draw(seed=HOLDOUT_SEED)` must stay byte-identical to the committed v1
    # draw, and that identity is pinned by a test.
    if not exclude:
        return candidates
    return [a for a in candidates if a not in exclude]


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
    exclude: frozenset[str] = frozenset(),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    drawn: list[dict[str, Any]] = []
    overdraw: list[dict[str, Any]] = []
    used: set[str] = set()
    for category in _category_allocation(count, list(categories), rng):
        feasible = _feasible(gold, population, category, exclude)
        # Checked before the loop so it consumes no randomness: the draw for a
        # given seed must not depend on whether this guard exists.
        if not [a for a in feasible if a not in used]:
            raise DrawExhausted(
                f"{stratum}/{category}: no un-drawn anchor remains "
                f"({len(feasible)} feasible, {len(exclude)} excluded)"
            )
        attempts = 0
        while True:
            attempts += 1
            if attempts > _MAX_DRAW_ATTEMPTS:
                raise DrawExhausted(f"{stratum}/{category}: rejection sampling did not settle")
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
    exclude: frozenset[str] = frozenset(),
    scale: int = 1,
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
    # Ratios are unchanged by scale — only the absolute targets grow — so the
    # answerable/abstention balance of a scaled bank matches a 1x one.
    quota = {
        cat: {
            "answerable": round(FEDERATED_ANSWERABLE * n / STRATA["federated"]) * scale,
            "abstention-expected": round(FEDERATED_ABSTENTION * n / STRATA["federated"]) * scale,
        }
        for cat, n in FEDERATED_SPLIT.items()
    }
    drawn: list[dict[str, Any]] = []
    overdraw: list[dict[str, Any]] = []
    used: set[str] = set()
    for category, wanted in quota.items():
        population = populations[source_of[category]]
        if exclude:
            population = [a for a in population if a not in exclude]
            if not population:
                raise DrawExhausted(
                    f"federated/{category}: the exclusion set covers the whole population"
                )
        filled = {"answerable": 0, "abstention-expected": 0}
        attempts = 0
        while sum(filled.values()) < FEDERATED_SPLIT[category] * scale:
            attempts += 1
            if attempts > _MAX_DRAW_ATTEMPTS:
                raise DrawExhausted(
                    f"federated/{category}: could not fill both partitions "
                    f"({filled}, {len(population)} available)"
                )
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


def draw(
    gold: dict[str, Any] | None = None,
    *,
    seed: int = HOLDOUT_SEED,
    exclude: set[str] | frozenset[str] | None = None,
    scale: int = 1,
) -> dict[str, Any]:
    """The full seeded draw. Deterministic: same seed, same bank, same anchors.

    ``exclude`` removes anchors from every population before drawing, which is
    what makes successive banks genuinely disjoint rather than merely differently
    seeded. A fresh seed alone does *not* guarantee non-overlap, and the effect
    is not marginal: over 59 reseeds against the v1 draw, **30 (51%) shared at
    least one anchor**, mean overlap 0.73, max 3. The single-source strata draw
    from 697 and 558, but categories partition those into far smaller feasible
    sub-populations and the federated partitions are tighter still. Pass the
    union of every previously-drawn anchor here to get a genuinely fresh bank.

    ``scale`` multiplies every stratum and both federated partition targets, so
    ``scale=2`` draws 60 questions in the same proportions.

    Both parameters default to a no-op: ``draw(seed=HOLDOUT_SEED)`` reproduces
    the committed v1 anchors byte for byte, and a test pins that.
    """
    gold = gold if gold is not None else load_gold_bank()
    exclude = frozenset(exclude or ())
    if scale < 1:
        raise ValueError(f"scale must be >= 1, got {scale}")
    populations = {
        "attack": attack_population(gold),
        "capec": capec_population(gold),
        "cwe": cwe_population(gold),
    }
    rng = random.Random(seed)

    attack_drawn, attack_over = _draw_single_source(
        gold, stratum="attack", population=populations["attack"],
        categories=ATTACK_CATEGORIES, count=STRATA["attack"] * scale, rng=rng,
        exclude=exclude,
    )
    capec_drawn, capec_over = _draw_single_source(
        gold, stratum="capec", population=populations["capec"],
        categories=CAPEC_CATEGORIES, count=STRATA["capec"] * scale, rng=rng,
        exclude=exclude,
    )
    fed_drawn, fed_over = _draw_federated(
        gold, populations=populations, rng=rng, exclude=exclude, scale=scale,
    )

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
        "strata": {k: v * scale for k, v in STRATA.items()},
        "scale": scale,
        "excluded": {"size": len(exclude), "sha256": _sha256_of(sorted(exclude))},
        "federated_targets": {
            "answerable": FEDERATED_ANSWERABLE * scale,
            "abstention-expected": FEDERATED_ABSTENTION * scale,
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


# ---------------------------------------------------------------------------
# the Compiler — gold is computed, never authored
# ---------------------------------------------------------------------------

BANK_PATH = REPO_ROOT / "utils" / "specialists" / "tests" / "golden" / "holdout_questions.json"
AUTHORED_PATH = REPO_ROOT / "docs" / "evaluation" / "holdout-v1" / "authored.json"

LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}
JOIN_KEY = "attack-technique-id"

#: Entity scope per category — the shape the schema card resolves against.
#: Taken from the equivalent entries in the three committed banks so the
#: holdout routes through the same builders rather than a parallel path.
ENTITIES: dict[str, list[str]] = {
    "mitigations": ["Technique", "Mitigation"],
    "groups": ["Group", "Technique"],
    "software": ["Software", "Technique"],
    "detection": ["Technique", "DetectionStrategy", "Analytic"],
    "tactics": ["Tactic", "Technique"],
    "subtechnique": ["Technique", "SubTechnique", "HAS_SUBTECHNIQUE"],
    "mapping": ["AttackPattern", "TaxonomyEntry"],
    "weakness": ["AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"],
    "hierarchy": ["AttackPattern", "ChildOf", "ChildOf"],
    "execution": ["AttackPattern", "HAS_EXECUTION_STEP", "ExecutionStep"],
    "consequence": ["AttackPattern", "HAS_CONSEQUENCE", "Consequence"],
    "prerequisite": ["AttackPattern", "REQUIRES_SKILL", "Skill"],
}

#: `expected_template` is DERIVED from the anchor's type and category, because
#: the Author never saw the template inventory and so could not supply it. It is
#: therefore **not a scoring signal** — template-routing accuracy may not be
#: reported from this holdout. `expected_template_is_derived: true` on every
#: entry records that so nobody later mistakes it for ground truth.
DERIVED_TEMPLATE: dict[str, str] = {
    "mitigations": "technique_mitigations",
    "groups": "group_techniques",
    "software": "software_techniques",
    "detection": "technique_detection",
    "tactics": "technique_tactics",
    "subtechnique": "subtechnique_parent",
    "mapping": "capec_maps_to",
    "weakness": "capec_neighbors",
    "hierarchy": "capec_hierarchy_chain",
    "execution": "capec_neighbors",
    "consequence": "capec_neighbors",
    "prerequisite": "capec_neighbors",
}

#: Federated sub-question templates, likewise derived.
FEDERATED_TEMPLATES: dict[str, tuple[str, str]] = {
    "pattern-to-mitigation": ("capec_maps_to", "technique_mitigations"),
    "reverse-mapping": ("capec_reverse_maps", "describe"),
    "cwe-chain": ("cwe_chain", "technique_mitigations"),
}


class GoldComputationError(RuntimeError):
    """Raised when an anchor cannot be given gold — §6 says discard, never repair."""


def _sub(sub_id: str, source: str, text: str, entities: list[str], template: str,
         *, join_key: str | None = None, seed_from: str | None = None) -> dict[str, Any]:
    sub = {
        "id": sub_id,
        "source": source,
        "text": text,
        "entities": entities,
        "limits": dict(LIMITS),
        "join_key": join_key,
        "rationale": "holdout-v1 seeded draw",
        "expected_template": template,
    }
    if seed_from:
        sub["seed_from"] = seed_from
    return sub


def _meta(entry: dict[str, Any]) -> dict[str, Any]:
    meta = {
        "anchor": entry["anchor"],
        "anchor_draw_index": entry["draw_index"],
        "category": entry["category"],
        "author_model": AUTHOR_MODEL,
        "expected_template_is_derived": True,
    }
    if "partition" in entry:
        meta["federated_partition"] = entry["partition"]
    return meta


def _compile_single(gold: dict[str, Any], entry: dict[str, Any], question: str) -> dict[str, Any]:
    anchor, category = entry["anchor"], entry["category"]
    source = "capec" if anchor.startswith("CAPEC-") else "attack"
    scheme = source

    if category == "lookup":
        assertions = {
            "min_records": 1,
            "max_records": 1,
            "must_include_ids": [anchor],
            "expect_names": {anchor: entry["name"]},
        }
        ex_gold = {"pool": "node", "expected": [anchor], "scheme": scheme}
        entities, template = [entity_type(gold, anchor)], "describe"
    else:
        related = neighbours(gold, category, anchor)
        if not related:
            raise GoldComputationError(
                f"{anchor}: category {category!r} resolved to an empty neighbour set"
            )
        assertions = {
            "min_records": 1,
            "must_include_ids": [anchor],
            "must_include_related": related,
        }
        pool = "join" if category == "mapping" else "neighbors"
        ex_gold = {"pool": pool, "expected": related, "scheme": scheme}
        entities, template = ENTITIES[category], DERIVED_TEMPLATE[category]

    # The CAPEC `mapping` category is the one single-source shape that declares a
    # cross-source join: the Gremlin builder gates `capec_maps_to` on the join,
    # and without it the same question falls through to `describe` and returns
    # facet counts instead of the mapped techniques. The three committed
    # `C-MAP-*` entries all carry it. Omitting it here would have compared the
    # holdout against a *different plan* than the development set gets for the
    # same category, which is not the comparison this experiment is making.
    join_key = JOIN_KEY if category == "mapping" else None

    return {
        "id": entry["id"],
        "tier": "easy" if category == "lookup" else "medium",
        "split": "holdout",
        "question": question,
        "expected_template": template,
        "task": {
            "sub_question_id": entry["id"],
            "source": source,
            "text": question,
            "entities": entities,
            "limits": dict(LIMITS),
            "join_key": join_key,
            "seed_ids": [anchor],
            "rationale": "holdout-v1 seeded draw",
        },
        "assertions": assertions,
        "ex_gold": ex_gold,
        "gold_provenance": {
            "attack_version": gold["meta"]["attack_version"],
            "capec_version": gold["meta"]["capec_version"],
        },
        "holdout_meta": _meta(entry),
    }


def _compile_federated(gold: dict[str, Any], entry: dict[str, Any], question: str) -> dict[str, Any]:
    anchor, category = entry["anchor"], entry["category"]
    correlate = federated_correlation(gold, category, anchor)
    negative = not correlate
    t1, t2 = FEDERATED_TEMPLATES[category]
    capec_gold, attack_gold = gold["capec"], gold["attack"]

    if category == "pattern-to-mitigation":
        subs = [
            _sub("q1", "capec", f"Which ATT&CK techniques does {anchor} map to?",
                 ["AttackPattern", "TaxonomyEntry"], t1, join_key=JOIN_KEY),
            _sub("q2", "attack", "What mitigations does ATT&CK list for those mapped techniques?",
                 ["Technique", "Mitigation"], t2, join_key=JOIN_KEY, seed_from="q1"),
        ]
        hops, sequenced = 2, True
        capec_ids, capec_related = [anchor], correlate
        attack_related = sorted({
            m for t in correlate for m in attack_gold["technique_mitigations"].get(t, [])
        })
    elif category == "reverse-mapping":
        patterns = sorted(
            (cid for cid in capec_gold["patterns"] if anchor in live_mappings(gold, cid)),
            key=lambda c: int(c.split("-")[1]),
        )
        subs = [
            _sub("q1", "capec", f"Which CAPEC patterns map to ATT&CK technique {anchor}?",
                 ["AttackPattern", "TaxonomyEntry"], t1, join_key=JOIN_KEY),
            _sub("q2", "attack", f"What is ATT&CK technique {anchor}?",
                 [entity_type(gold, anchor)], t2),
        ]
        hops, sequenced = 1, False
        capec_ids, capec_related = patterns, [anchor] if patterns else []
        attack_related = []
    else:  # cwe-chain
        patterns = capec_gold["cwe_to_capec"].get(anchor, [])
        subs = [
            _sub("q1", "capec",
                 f"Which attack patterns exploit {anchor} and which ATT&CK techniques do they map to?",
                 ["Weakness", "AttackPattern", "TaxonomyEntry"], t1, join_key=JOIN_KEY),
            _sub("q2", "attack", "What mitigations does ATT&CK list for those mapped techniques?",
                 ["Technique", "Mitigation"], t2, join_key=JOIN_KEY, seed_from="q1"),
        ]
        hops, sequenced = 3, True
        capec_ids, capec_related = list(patterns), [anchor] if patterns else []
        attack_related = sorted({
            m for t in correlate for m in attack_gold["technique_mitigations"].get(t, [])
        })

    if negative:
        # The abstention-expected partition. The correct behaviour is an honest
        # empty carrying the executed query — never a fabricated correlation —
        # so the assertions say exactly that and nothing about answer content.
        assertions: dict[str, Any] = {
            "must_correlate": [],
            "expect_no_correlation": True,
            "capec": {"expect_empty": True} if not capec_ids else {
                "min_records": 1, "must_include_ids": capec_ids,
            },
            "attack": {"expect_dependency_skip": True},
        }
    else:
        assertions = {
            "must_correlate": correlate,
            "capec": {
                "min_records": 1,
                "must_include_ids": capec_ids,
                "must_include_related": capec_related,
            },
            "attack": {
                "min_records": 1,
                "must_include_ids": correlate,
                **({"must_include_related": attack_related} if attack_related else {}),
            },
        }

    return {
        "id": entry["id"],
        "tier": "hard",
        "split": "holdout",
        "hops": hops,
        "sources": ["capec", "attack"],
        "sequenced": sequenced,
        "partial_mode": None,
        "question": question,
        "sub_questions": subs,
        "assertions": assertions,
        "gold_provenance": {
            "attack_version": gold["meta"]["attack_version"],
            "capec_version": gold["meta"]["capec_version"],
        },
        "holdout_meta": _meta(entry),
    }


def compile_bank(
    anchors: dict[str, Any],
    authored: dict[str, str],
    gold: dict[str, Any] | None = None,
    *,
    author_model: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Assemble the holdout bank. Returns ``(bank, discards)``.

    Gold comes only from ``gold_bank.py``'s parse of the raw snapshot. An anchor
    whose gold cannot be computed is **discarded, not repaired** (§6); the
    discard and its reason are returned for the anchors.json log, because a high
    discard rate is itself a finding about the join surface.
    """
    gold = gold if gold is not None else load_gold_bank()
    questions: list[dict[str, Any]] = []
    discards: list[dict[str, Any]] = []
    for entry in anchors["anchors"]:
        question = authored.get(entry["id"])
        if not question:
            discards.append({**_meta(entry), "reason": "no authored question returned"})
            continue
        try:
            if entry["stratum"] == "federated":
                questions.append(_compile_federated(gold, entry, question))
            else:
                questions.append(_compile_single(gold, entry, question))
        except (GoldComputationError, KeyError) as exc:
            discards.append({**_meta(entry), "reason": f"{type(exc).__name__}: {exc}"})
    bank = {
        "meta": {
            "attack_version": gold["meta"]["attack_version"],
            "capec_version": gold["meta"]["capec_version"],
            "gold_bank": "gold_bank.json",
            "generator": "utils/specialists/evalset/holdout_protocol.py",
            "split": "holdout",
            "seed": anchors["seed"],
            # Defaults to v1's hand-driven author so recompiling the committed
            # bank is unchanged; a generated bank passes its own model through,
            # because "who wrote these questions" is provenance, not decoration.
            "author_model": author_model or AUTHOR_MODEL,
            "scale": anchors.get("scale", 1),
            "excluded_anchors": (anchors.get("excluded") or {}).get("size", 0),
        },
        "questions": questions,
    }
    return bank, discards


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
