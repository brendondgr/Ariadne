#!/usr/bin/env python3
"""Authored federated question archetypes (Slice A of the Step 10 catalogue).

Every entry crosses BOTH pinned sources. The defining assertion is
``must_correlate``: the set of ATT&CK technique ids that must appear on both
sides of the federation's join index, computed here at compile time as the
*intersection* of the CAPEC-side snapshot map (ATTACK-taxonomy ``MAPS_TO``
only) and ATT&CK-side existence — never hand-keyed, mirroring the ``REF:``
discipline of the single-source banks.

Entry shape (a superset of the single-source shape):

  id / tier / question        — as in the single-source banks
  hops                        — reasoning depth for the difficulty matrix
  sources                     — always ["capec", "attack"] here
  sequenced                   — True when the attack sub-question is seeded
                                from the capec producer's harvested join
                                values (the dependent-sequencing path);
                                False = both sides run independently
  partial_mode                — None | "boundary" | "attack_down" | "capec_down"
  sub_questions               — planner SubQuestion dicts (id/source/text/
                                entities/limits/join_key) plus two authoring
                                extras the runner strips: ``expected_template``
                                and ``seed_from``
  assertions.must_correlate   — computed intersection (see above)
  assertions.expect_no_correlation — adversarial entries: the join must be
                                honestly empty, never fabricated
  assertions.capec / .attack  — per-side blocks in the golden-runner
                                vocabulary, plus two federated-only keys:
                                ``expect_dependency_skip`` (consumer skipped
                                because its producer yielded no join values /
                                was not run) and ``expect_skipped`` (the
                                sub-question never ran: specialist absent)
  gold_provenance             — pinned snapshot versions

Regenerate via ``uv run python -m utils.specialists.evalset.compile_banks``.
"""

from __future__ import annotations

from typing import Any

from .questions import ATTACK_LIMITS, CAPEC_LIMITS

JOIN_KEY = "attack-technique-id"

# -- Anchor choices (ids only — every gold value is resolved from the bank) -----
# CAPEC pattern -> mapped techniques -> mitigations (the credential-theft
# archetype generalised): patterns chosen for rich, stable mapping sets.
CTM_ANCHORS = (
    "CAPEC-150", "CAPEC-555", "CAPEC-593", "CAPEC-639", "CAPEC-21",
    "CAPEC-665", "CAPEC-600", "CAPEC-644", "CAPEC-645", "CAPEC-652",
)
# CAPEC pattern -> mapped technique -> tactic rollup.
CTT_ANCHORS = ("CAPEC-98", "CAPEC-49", "CAPEC-565", "CAPEC-633", "CAPEC-13", "CAPEC-37")
# Reverse joins: ATT&CK technique -> the CAPEC patterns that map to it.
REV_ANCHORS = ("T1040", "T1566", "T1110.001", "T1021", "T1133", "T1114.002")
# CWE -> CAPEC -> ATT&CK 3-hop chains (CWEs whose bridged patterns carry
# ATTACK-taxonomy mappings — many famous web CWEs bridge only to unmapped
# patterns and would be empty chains).
CWE_ANCHORS = ("CWE-522", "CWE-287", "CWE-294", "CWE-308", "CWE-521")
# Cross-source negatives: live patterns verified to carry NO ATTACK mapping.
NEG_ANCHORS = ("CAPEC-116", "CAPEC-66", "CAPEC-3", "CAPEC-7", "CAPEC-16", "CAPEC-18")
# Partials: boundary refusals on the attack side (Assets are ICS-only) and
# staged single-source outages.
PART_BOUNDARY_ANCHORS = ("T1021", "T1566")
PART_DOWN_ANCHOR = "CAPEC-555"
# Multi-pattern fan-in: pattern groups with verified overlapping T-ids.
FAN_ANCHORS = (
    ("CAPEC-19", "CAPEC-35", "CAPEC-448"),
    ("CAPEC-13", "CAPEC-640"),
    ("CAPEC-37", "CAPEC-639"),
)


def _sub(
    qid: str,
    source: str,
    text: str,
    entities: tuple[str, ...],
    expected_template: str,
    *,
    join_key: str | None = None,
    seed_from: str | None = None,
) -> dict[str, Any]:
    limits = ATTACK_LIMITS if source == "attack" else CAPEC_LIMITS
    sub: dict[str, Any] = {
        "id": qid,
        "source": source,
        "text": text,
        "entities": list(entities),
        "limits": dict(limits),
        "join_key": join_key,
        "rationale": "federated golden evalset",
        "expected_template": expected_template,
    }
    if seed_from:
        sub["seed_from"] = seed_from
    return sub


def _live_mappings(gold: dict[str, Any], cid: str) -> list[str]:
    """The pattern's ATTACK-taxonomy T-ids that exist on the ATT&CK side."""
    capec, attack = gold["capec"], gold["attack"]
    return [t for t in capec["attack_mappings"].get(cid, []) if t in attack["objects"]]


def _mitigation_union(gold: dict[str, Any], t_ids: list[str]) -> list[str]:
    tm = gold["attack"]["technique_mitigations"]
    return sorted({m for t in t_ids for m in tm.get(t, [])})


def _tactic_union(gold: dict[str, Any], t_ids: list[str]) -> list[str]:
    tt = gold["attack"]["technique_tactics"]
    return sorted({ta for t in t_ids for ta in tt.get(t, [])})


def _provenance(gold: dict[str, Any]) -> dict[str, str]:
    return {
        "attack_version": gold["meta"]["attack_version"],
        "capec_version": gold["meta"]["capec_version"],
    }


def build_federated_questions(gold: dict[str, Any]) -> list[dict[str, Any]]:
    capec, attack = gold["capec"], gold["attack"]
    prov = _provenance(gold)
    questions: list[dict[str, Any]] = []

    # -- F-CTM: CAPEC pattern -> mapped techniques -> mitigations (Hard, 2-hop) --
    for i, cid in enumerate(CTM_ANCHORS, start=1):
        correlate = _live_mappings(gold, cid)
        if not correlate:
            raise ValueError(f"{cid} has no live ATT&CK mappings — CTM anchor invalid")
        name = capec["patterns"][cid]["name"]
        questions.append(
            {
                "id": f"F-CTM-{i:02d}",
                "tier": "hard",
                "hops": 2,
                "sources": ["capec", "attack"],
                "sequenced": True,
                "partial_mode": None,
                "question": (
                    f"Which ATT&CK techniques does {cid} ({name}) map to, "
                    f"and what mitigations apply to those techniques?"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which ATT&CK techniques does {cid} map to?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        "What mitigations does ATT&CK list for those mapped techniques?",
                        ("Technique", "Mitigation"), "technique_mitigations",
                        join_key=JOIN_KEY, seed_from="q1",
                    ),
                ],
                "assertions": {
                    "must_correlate": list(correlate),
                    "capec": {
                        "min_records": 1,
                        "must_include_ids": [cid],
                        "must_include_related": list(correlate),
                    },
                    "attack": {
                        "min_records": len(correlate),
                        "max_records": len(correlate),
                        "must_include_ids": list(correlate),
                        "must_include_related": _mitigation_union(gold, correlate),
                    },
                },
                "gold_provenance": prov,
            }
        )

    # -- F-CTT: CAPEC pattern -> mapped technique -> tactic rollup (Medium) ------
    for i, cid in enumerate(CTT_ANCHORS, start=1):
        correlate = _live_mappings(gold, cid)
        if not correlate:
            raise ValueError(f"{cid} has no live ATT&CK mappings — CTT anchor invalid")
        name = capec["patterns"][cid]["name"]
        questions.append(
            {
                "id": f"F-CTT-{i:02d}",
                "tier": "medium",
                "hops": 2,
                "sources": ["capec", "attack"],
                "sequenced": True,
                "partial_mode": None,
                "question": (
                    f"Which ATT&CK tactics do the techniques mapped from "
                    f"{cid} ({name}) belong to?"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which ATT&CK techniques does {cid} map to?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        "Which tactics do those techniques belong to?",
                        ("Tactic", "Technique"), "technique_tactics",
                        join_key=JOIN_KEY, seed_from="q1",
                    ),
                ],
                "assertions": {
                    "must_correlate": list(correlate),
                    "capec": {
                        "min_records": 1,
                        "must_include_ids": [cid],
                        "must_include_related": list(correlate),
                    },
                    "attack": {
                        "min_records": len(correlate),
                        "max_records": len(correlate),
                        "must_include_ids": list(correlate),
                        "must_include_related": _tactic_union(gold, correlate),
                    },
                },
                "gold_provenance": prov,
            }
        )

    # -- F-REV: reverse joins — technique -> the patterns that map to it ---------
    reverse: dict[str, list[str]] = {}
    for cid, t_ids in capec["attack_mappings"].items():
        for t in t_ids:
            reverse.setdefault(t, []).append(cid)
    for i, tid in enumerate(REV_ANCHORS, start=1):
        patterns = sorted(reverse.get(tid, []), key=lambda c: int(c.split("-")[1]))
        if not patterns:
            raise ValueError(f"{tid} has no reverse CAPEC mappings — REV anchor invalid")
        obj = attack["objects"][tid]
        questions.append(
            {
                "id": f"F-REV-{i:02d}",
                "tier": "medium",
                "hops": 1,
                "sources": ["capec", "attack"],
                "sequenced": False,
                "partial_mode": None,
                "question": (
                    f"Which CAPEC patterns map to ATT&CK technique {tid} "
                    f"({obj['name']}), and what is that technique?"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which CAPEC patterns map to ATT&CK technique {tid}?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_reverse_maps",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        f"What is ATT&CK technique {tid}?",
                        (obj["label"],), "describe",
                    ),
                ],
                "assertions": {
                    "must_correlate": [tid],
                    "capec": {
                        "min_records": len(patterns),
                        "must_include_ids": list(patterns),
                        "must_include_related": [tid],
                    },
                    "attack": {
                        "min_records": 1,
                        "max_records": 1,
                        "must_include_ids": [tid],
                        "expect_names": {tid: obj["name"]},
                    },
                },
                "gold_provenance": prov,
            }
        )

    # -- F-CWE: CWE -> CAPEC -> ATT&CK 3-hop chains (Hard) -----------------------
    for i, cwe in enumerate(CWE_ANCHORS, start=1):
        bridged = capec["cwe_to_capec"].get(cwe, [])
        mapped_patterns = [c for c in bridged if _live_mappings(gold, c)]
        correlate = sorted(
            {t for c in mapped_patterns for t in _live_mappings(gold, c)}
        )
        if not correlate:
            raise ValueError(f"{cwe} bridges to no mapped patterns — CWE anchor invalid")
        questions.append(
            {
                "id": f"F-CWE-{i:02d}",
                "tier": "hard",
                "hops": 3,
                "sources": ["capec", "attack"],
                "sequenced": True,
                "partial_mode": None,
                "question": (
                    f"Which CAPEC patterns exploit weakness {cwe}, which ATT&CK "
                    f"techniques do they map to, and what mitigations apply?"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which attack patterns exploit {cwe} and which ATT&CK "
                        f"techniques do they map to?",
                        ("Weakness", "AttackPattern", "TaxonomyEntry"), "cwe_chain",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        "What mitigations does ATT&CK list for those mapped techniques?",
                        ("Technique", "Mitigation"), "technique_mitigations",
                        join_key=JOIN_KEY, seed_from="q1",
                    ),
                ],
                "assertions": {
                    "must_correlate": list(correlate),
                    "capec": {
                        "min_records": 1,
                        "must_include_ids": list(mapped_patterns),
                        "must_include_related": [cwe],
                    },
                    "attack": {
                        "min_records": len(correlate),
                        "max_records": len(correlate),
                        "must_include_ids": list(correlate),
                        "must_include_related": _mitigation_union(gold, correlate),
                    },
                },
                "gold_provenance": prov,
            }
        )

    # -- F-NEG: cross-source negatives — no mapping, honest empty join -----------
    for i, cid in enumerate(NEG_ANCHORS, start=1):
        if cid in capec["attack_mappings"]:
            raise ValueError(f"{cid} gained an ATT&CK mapping — NEG anchor invalid")
        if cid not in capec["patterns"]:
            raise ValueError(f"{cid} is not a live pattern — NEG anchor invalid")
        name = capec["patterns"][cid]["name"]
        questions.append(
            {
                "id": f"F-NEG-{i:02d}",
                "tier": "adversarial",
                "hops": 2,
                "sources": ["capec", "attack"],
                "sequenced": True,
                "partial_mode": None,
                "question": (
                    f"Which ATT&CK techniques does {cid} ({name}) map to, and what "
                    f"mitigations apply? (verified: NO mapping — the join must be an "
                    f"honest empty, never a fabricated correlation)"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which ATT&CK techniques does {cid} map to?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        "What mitigations does ATT&CK list for those mapped techniques?",
                        ("Technique", "Mitigation"), "technique_mitigations",
                        join_key=JOIN_KEY, seed_from="q1",
                    ),
                ],
                "assertions": {
                    "must_correlate": [],
                    "expect_no_correlation": True,
                    "capec": {"expect_empty": True},
                    "attack": {"expect_dependency_skip": True},
                },
                "gold_provenance": prov,
            }
        )

    # -- F-PART: partial degradation — answerable side must stay intact ----------
    for i, tid in enumerate(PART_BOUNDARY_ANCHORS, start=1):
        patterns = sorted(reverse.get(tid, []), key=lambda c: int(c.split("-")[1]))
        if not patterns:
            raise ValueError(f"{tid} has no reverse CAPEC mappings — PART anchor invalid")
        questions.append(
            {
                "id": f"F-PART-{i:02d}",
                "tier": "adversarial",
                "hops": 2,
                "sources": ["capec", "attack"],
                "sequenced": False,
                "partial_mode": "boundary",
                "question": (
                    f"Which CAPEC patterns map to {tid}, and what assets does it "
                    f"target? (Assets are ICS-only: the attack side must refuse "
                    f"honestly while the CAPEC side stays intact)"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which CAPEC patterns map to ATT&CK technique {tid}?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_reverse_maps",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        f"What assets does technique {tid} target?",
                        ("Technique", "Asset"), "boundary_refusal",
                    ),
                ],
                "assertions": {
                    "must_correlate": [],
                    "expect_no_correlation": True,
                    "capec": {
                        "min_records": len(patterns),
                        "must_include_ids": list(patterns),
                        "must_include_related": [tid],
                    },
                    "attack": {"expect_boundary": True},
                },
                "gold_provenance": prov,
            }
        )
    down_correlate = _live_mappings(gold, PART_DOWN_ANCHOR)
    questions.append(
        {
            "id": "F-PART-03",
            "tier": "adversarial",
            "hops": 2,
            "sources": ["capec", "attack"],
            "sequenced": True,
            "partial_mode": "attack_down",
            "question": (
                f"With the ATT&CK source down: {PART_DOWN_ANCHOR} mappings must "
                f"still answer; the mitigation side degrades to an honest skip."
            ),
            "sub_questions": [
                _sub(
                    "q1", "capec",
                    f"Which ATT&CK techniques does {PART_DOWN_ANCHOR} map to?",
                    ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                    join_key=JOIN_KEY,
                ),
                _sub(
                    "q2", "attack",
                    "What mitigations does ATT&CK list for those mapped techniques?",
                    ("Technique", "Mitigation"), "technique_mitigations",
                    join_key=JOIN_KEY, seed_from="q1",
                ),
            ],
            "assertions": {
                "must_correlate": [],
                "expect_no_correlation": True,
                "expect_partial": True,
                "capec": {
                    "min_records": 1,
                    "must_include_ids": [PART_DOWN_ANCHOR],
                    "must_include_related": list(down_correlate),
                },
                "attack": {"expect_skipped": True},
            },
            "gold_provenance": prov,
        }
    )
    questions.append(
        {
            "id": "F-PART-04",
            "tier": "adversarial",
            "hops": 2,
            "sources": ["capec", "attack"],
            "sequenced": True,
            "partial_mode": "capec_down",
            "question": (
                f"With the CAPEC source down: the {PART_DOWN_ANCHOR} producer never "
                f"runs, so the seeded ATT&CK side must degrade to a dependency "
                f"abstention — no broad unseeded query."
            ),
            "sub_questions": [
                _sub(
                    "q1", "capec",
                    f"Which ATT&CK techniques does {PART_DOWN_ANCHOR} map to?",
                    ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                    join_key=JOIN_KEY,
                ),
                _sub(
                    "q2", "attack",
                    "What mitigations does ATT&CK list for those mapped techniques?",
                    ("Technique", "Mitigation"), "technique_mitigations",
                    join_key=JOIN_KEY, seed_from="q1",
                ),
            ],
            "assertions": {
                "must_correlate": [],
                "expect_no_correlation": True,
                "expect_partial": True,
                "capec": {"expect_skipped": True},
                "attack": {"expect_dependency_skip": True},
            },
            "gold_provenance": prov,
        }
    )

    # -- F-FAN: multi-pattern fan-in — union + dedup correctness (Hard) ----------
    for i, group in enumerate(FAN_ANCHORS, start=1):
        per_pattern = {cid: set(_live_mappings(gold, cid)) for cid in group}
        union = sorted(set().union(*per_pattern.values()))
        overlap = set.intersection(*per_pattern.values()) if len(group) > 1 else set()
        if not overlap:
            raise ValueError(f"fan-in group {group} has no overlapping T-ids — anchor invalid")
        id_list = ", ".join(group)
        questions.append(
            {
                "id": f"F-FAN-{i:02d}",
                "tier": "hard",
                "hops": 2,
                "sources": ["capec", "attack"],
                "sequenced": True,
                "partial_mode": None,
                "question": (
                    f"Which ATT&CK techniques do {id_list} map to (they overlap), "
                    f"and what mitigations apply to the deduplicated union?"
                ),
                "sub_questions": [
                    _sub(
                        "q1", "capec",
                        f"Which ATT&CK techniques do {id_list} map to?",
                        ("AttackPattern", "TaxonomyEntry"), "capec_maps_to",
                        join_key=JOIN_KEY,
                    ),
                    _sub(
                        "q2", "attack",
                        "What mitigations does ATT&CK list for those mapped techniques?",
                        ("Technique", "Mitigation"), "technique_mitigations",
                        join_key=JOIN_KEY, seed_from="q1",
                    ),
                ],
                "assertions": {
                    "must_correlate": list(union),
                    "capec": {
                        "min_records": len(group),
                        "must_include_ids": list(group),
                        "must_include_related": list(union),
                    },
                    "attack": {
                        "min_records": len(union),
                        "max_records": len(union),
                        "must_include_ids": list(union),
                        "must_include_related": _mitigation_union(gold, union),
                    },
                },
                "gold_provenance": prov,
            }
        )

    return questions
