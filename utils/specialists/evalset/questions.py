#!/usr/bin/env python3
"""Authored question archetypes for the Step 5 golden banks.

Every entry here is single-source and restricted to intents the deterministic
builders can express today (Cypher: technique_mitigations, group_techniques,
tactic_techniques, node_lookup, label_scan; Gremlin: capec_lookup,
capec_neighbors, capec_maps_to, capec_scan). Gold IDs are resolved from the
committed gold bank at compile time — never typed by hand (Step 7 discipline).

Assertion vocabulary (consumed by the golden live-test runner):
  min_records / max_records  — bounds on len(result.records)
  expect_empty               — records must be empty AND result.ok True
  must_include_ids           — subset of the returned primary-id pool
  must_include_related       — subset of the related/join-value id pool
  forbid_ids                 — must NOT appear anywhere in the id pool
  expect_names               — {id: exact name} checked against records
  expect_properties          — {id: {property: value}} checked against records

Known coverage gaps recorded deliberately (do NOT silently work around them):
  * CAPEC Typical_Severity / Likelihood_Of_Attack are in the gold bank but NOT
    in the loaded graph (the ingest carries only Abstraction/Status), so no
    live question asserts severity — that is an ingest gap, tracked separately.
  * ParentOf / CanFollow questions are inverse traversals the builder cannot
    route yet; the gold `children` map exists for when it can.
"""

from __future__ import annotations

from typing import Any

ATTACK_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}
CAPEC_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}

# Anchor choices (ids only — every gold value is resolved from the bank).
MITIGATION_ANCHORS = ("T1047", "T1021.001", "T1110", "T1566", "T1003", "T1055", "T1078", "T1490")
GROUP_ANCHORS = ("G0016", "G0032", "G0007", "G1039")
TACTIC_ANCHORS = ("TA0001", "TA0006", "TA0112")  # TA0112 = v19 Defense Impairment
# Note: Group/Tactic name-lookups are unroutable today — any task carrying a
# Group or Tactic entity routes to group_techniques/tactic_techniques before
# node_lookup is considered. Known builder limitation, recorded in VERIFICATION.
LOOKUP_ANCHORS = (
    ("T1021.001", "SubTechnique"),
    ("M1038", "Mitigation"),
    ("T1566", "Technique"),
    ("S0154", "Software"),
)
CAMPAIGN_ANCHORS = ("C0027", "C0001")  # Step 7 gap: Campaign coverage
CAPEC_LOOKUP_ANCHORS = ("CAPEC-555", "CAPEC-116", "CAPEC-98", "CAPEC-163", "CAPEC-70", "CAPEC-557")
CAPEC_CWE_ANCHORS = ("CAPEC-555", "CAPEC-98", "CAPEC-66")
CAPEC_PARENT_ANCHORS = ("CAPEC-98", "CAPEC-564", "CAPEC-555")
CAPEC_PRECEDE_ANCHORS = ("CAPEC-98", "CAPEC-555")
CAPEC_MAPS_ANCHORS = ("CAPEC-555", "CAPEC-98", "CAPEC-564", "CAPEC-70")


def _task(
    qid: str,
    source: str,
    text: str,
    entities: tuple[str, ...],
    seed_ids: tuple[str, ...] = (),
    join_key: str | None = None,
) -> dict[str, Any]:
    limits = ATTACK_LIMITS if source == "attack" else CAPEC_LIMITS
    return {
        "sub_question_id": qid,
        "source": source,
        "text": text,
        "entities": list(entities),
        "limits": dict(limits),
        "join_key": join_key,
        "seed_ids": list(seed_ids),
        "rationale": "golden evalset",
    }


def _top_level_techniques(gold: dict[str, Any], ids: list[str], count: int) -> list[str]:
    objects = gold["attack"]["objects"]
    top = [i for i in ids if objects.get(i, {}).get("label") == "Technique"]
    if len(top) < count:
        raise ValueError(f"expected at least {count} top-level techniques, got {top}")
    return top[:count]


def build_attack_questions(gold: dict[str, Any]) -> list[dict[str, Any]]:
    attack = gold["attack"]
    questions: list[dict[str, Any]] = []

    # -- technique -> mitigations ------------------------------------------------
    for i, tid in enumerate(MITIGATION_ANCHORS, start=1):
        mits = attack["technique_mitigations"][tid]
        name = attack["objects"][tid]["name"]
        questions.append(
            {
                "id": f"A-MIT-{i:02d}",
                "tier": "easy",
                "question": f"What mitigations does ATT&CK list for {tid} ({name})?",
                "expected_template": "technique_mitigations",
                "task": _task(
                    f"A-MIT-{i:02d}", "attack",
                    f"What mitigations does ATT&CK list for technique {tid}?",
                    ("Technique", "Mitigation"), (tid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [tid],
                    "must_include_related": list(mits),
                },
            }
        )

    # -- group -> techniques -------------------------------------------------------
    for i, gid in enumerate(GROUP_ANCHORS, start=1):
        top5 = _top_level_techniques(gold, attack["group_techniques"][gid], 5)
        gname = attack["objects"][gid]["name"]
        questions.append(
            {
                "id": f"A-GRP-{i:02d}",
                "tier": "medium",
                "question": f"Which techniques does group {gid} ({gname}) use?",
                "expected_template": "group_techniques",
                "task": _task(
                    f"A-GRP-{i:02d}", "attack",
                    f"Which techniques does group {gid} use according to ATT&CK?",
                    ("Group", "Technique"), (gid,),
                ),
                "assertions": {"min_records": 5, "must_include_ids": top5},
            }
        )

    # -- tactic -> techniques ------------------------------------------------------
    for i, taid in enumerate(TACTIC_ANCHORS, start=1):
        top5 = _top_level_techniques(gold, attack["tactic_techniques"][taid], 5)
        taname = attack["objects"][taid]["name"]
        questions.append(
            {
                "id": f"A-TAC-{i:02d}",
                "tier": "medium",
                "question": f"Which techniques belong to tactic {taid} ({taname})?",
                "expected_template": "tactic_techniques",
                "task": _task(
                    f"A-TAC-{i:02d}", "attack",
                    f"List the techniques under tactic {taid}.",
                    ("Tactic", "Technique"), (taid,),
                ),
                "assertions": {"min_records": 5, "must_include_ids": top5},
            }
        )

    # -- node lookups (incl. the T1055/M1055 collision pair) -----------------------
    for i, (aid, label) in enumerate(LOOKUP_ANCHORS, start=1):
        name = attack["objects"][aid]["name"]
        questions.append(
            {
                "id": f"A-LKP-{i:02d}",
                "tier": "easy",
                "question": f"Look up {aid} — what is it called?",
                "expected_template": "node_lookup",
                "task": _task(
                    f"A-LKP-{i:02d}", "attack",
                    f"What is the name of ATT&CK object {aid}?",
                    (label,), (aid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "max_records": 1,
                    "must_include_ids": [aid],
                    "expect_names": {aid: name},
                },
            }
        )

    # -- Campaign coverage (Step 7 gap) --------------------------------------------
    for i, cid in enumerate(CAMPAIGN_ANCHORS, start=1):
        name = attack["objects"][cid]["name"]
        questions.append(
            {
                "id": f"A-CMP-{i:02d}",
                "tier": "easy",
                "question": f"Look up ATT&CK campaign {cid}.",
                "expected_template": "node_lookup",
                "task": _task(
                    f"A-CMP-{i:02d}", "attack",
                    f"What is campaign {cid} in ATT&CK?",
                    ("Campaign",), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "max_records": 1,
                    "must_include_ids": [cid],
                    "expect_names": {cid: name},
                },
            }
        )

    # -- label scan (cap check: LIMIT must bound the result) ----------------------
    questions.append(
        {
            "id": "A-SCN-01",
            "tier": "easy",
            "question": "List ATT&CK software entries (bounded scan).",
            "expected_template": "label_scan",
            "task": _task(
                "A-SCN-01", "attack",
                "List software tracked in ATT&CK.",
                ("Software",),
            ),
            "assertions": {"min_records": 250, "max_records": 300},
        }
    )

    # -- negatives: honest empties, not fabrications (Step 6/7 groundwork) --------
    questions.append(
        {
            "id": "A-NEG-01",
            "tier": "adversarial",
            "question": "Look up nonexistent technique T9999 — must return empty, not invent.",
            "expected_template": "node_lookup",
            "task": _task(
                "A-NEG-01", "attack",
                "What is the name of ATT&CK technique T9999?",
                ("Technique",), ("T9999",),
            ),
            "assertions": {"expect_empty": True},
        }
    )
    questions.append(
        {
            "id": "A-NEG-02",
            "tier": "adversarial",
            "question": "Techniques for nonexistent group G9999 — must return empty.",
            "expected_template": "group_techniques",
            "task": _task(
                "A-NEG-02", "attack",
                "Which techniques does group G9999 use?",
                ("Group", "Technique"), ("G9999",),
            ),
            "assertions": {"expect_empty": True},
        }
    )
    return questions


def build_capec_questions(gold: dict[str, Any]) -> list[dict[str, Any]]:
    capec = gold["capec"]
    questions: list[dict[str, Any]] = []

    # -- pattern lookups (Abstraction/Status are the graph-carried properties) ----
    for i, cid in enumerate(CAPEC_LOOKUP_ANCHORS, start=1):
        p = capec["patterns"][cid]
        questions.append(
            {
                "id": f"C-LKP-{i:02d}",
                "tier": "easy",
                "question": f"Look up {cid} ({p['name']}) — abstraction and status.",
                "expected_template": "capec_lookup",
                "task": _task(
                    f"C-LKP-{i:02d}", "capec",
                    f"What is CAPEC pattern {cid}?",
                    ("AttackPattern",), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "max_records": 1,
                    "must_include_ids": [cid],
                    "expect_names": {cid: p["name"]},
                    "expect_properties": {
                        cid: {"Abstraction": p["abstraction"], "Status": p["status"]}
                    },
                },
            }
        )

    # -- CWE weaknesses -------------------------------------------------------------
    for i, cid in enumerate(CAPEC_CWE_ANCHORS, start=1):
        cwes = capec["related_weaknesses"][cid]
        questions.append(
            {
                "id": f"C-CWE-{i:02d}",
                "tier": "medium",
                "question": f"Which CWE weaknesses does {cid} exploit?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-CWE-{i:02d}", "capec",
                    f"Which weaknesses does {cid} exploit?",
                    ("AttackPattern", "EXPLOITS_WEAKNESS", "Weakness"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": list(cwes),
                },
            }
        )

    # -- hierarchy: declared ChildOf (out-edge = "who is my parent") ----------------
    for i, cid in enumerate(CAPEC_PARENT_ANCHORS, start=1):
        parents = capec["hierarchy"][cid]["ChildOf"]
        questions.append(
            {
                "id": f"C-HIE-{i:02d}",
                "tier": "medium",
                "question": f"What is the parent (ChildOf) of {cid}?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-HIE-{i:02d}", "capec",
                    f"What pattern is {cid} a child of?",
                    ("AttackPattern", "ChildOf"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": list(parents),
                },
            }
        )

    # -- sequencing: declared CanPrecede ---------------------------------------------
    for i, cid in enumerate(CAPEC_PRECEDE_ANCHORS, start=1):
        nxt = capec["hierarchy"][cid]["CanPrecede"]
        questions.append(
            {
                "id": f"C-PRE-{i:02d}",
                "tier": "medium",
                "question": f"Which patterns can {cid} precede?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-PRE-{i:02d}", "capec",
                    f"Which attack patterns can {cid} precede?",
                    ("AttackPattern", "CanPrecede"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": list(nxt),
                },
            }
        )

    # -- ATT&CK taxonomy mappings (join surface) --------------------------------------
    for i, cid in enumerate(CAPEC_MAPS_ANCHORS, start=1):
        t_ids = capec["attack_mappings"][cid]
        questions.append(
            {
                "id": f"C-MAP-{i:02d}",
                "tier": "medium",
                "question": f"Which ATT&CK techniques does {cid} map to?",
                "expected_template": "capec_maps_to",
                "task": _task(
                    f"C-MAP-{i:02d}", "capec",
                    f"Which ATT&CK techniques does {cid} map to?",
                    ("AttackPattern", "TaxonomyEntry"), (cid,),
                    join_key="attack-technique-id",
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": list(t_ids),
                },
            }
        )

    # -- verified negative: CAPEC-116 has NO ATT&CK mapping -----------------------------
    if "CAPEC-116" in capec["attack_mappings"]:
        raise ValueError("CAPEC-116 gained an ATT&CK mapping — negative anchor invalid")
    questions.append(
        {
            "id": "C-MAP-NEG-01",
            "tier": "adversarial",
            "question": "ATT&CK mappings for CAPEC-116 (Excavation) — verified none; must be empty.",
            "expected_template": "capec_maps_to",
            "task": _task(
                "C-MAP-NEG-01", "capec",
                "Which ATT&CK techniques does CAPEC-116 map to?",
                ("AttackPattern", "TaxonomyEntry"), ("CAPEC-116",),
                join_key="attack-technique-id",
            ),
            "assertions": {"expect_empty": True},
        }
    )

    # -- nonexistent id ------------------------------------------------------------------
    questions.append(
        {
            "id": "C-NEG-01",
            "tier": "adversarial",
            "question": "Look up nonexistent CAPEC-99999 — must return empty, not invent.",
            "expected_template": "capec_lookup",
            "task": _task(
                "C-NEG-01", "capec",
                "What is CAPEC pattern CAPEC-99999?",
                ("AttackPattern",), ("CAPEC-99999",),
            ),
            "assertions": {"expect_empty": True},
        }
    )

    # -- bounded scan ----------------------------------------------------------------------
    questions.append(
        {
            "id": "C-SCN-01",
            "tier": "easy",
            "question": "Scan CAPEC attack patterns (bounded).",
            "expected_template": "capec_scan",
            "task": _task(
                "C-SCN-01", "capec",
                "List CAPEC attack patterns.",
                ("AttackPattern",),
            ),
            "assertions": {"min_records": 250, "max_records": 300},
        }
    )
    return questions
