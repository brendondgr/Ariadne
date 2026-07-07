#!/usr/bin/env python3
"""Authored question archetypes for the single-source golden banks.

Every entry here is single-source and restricted to intents the deterministic
builders can express today (Cypher: technique_mitigations, technique_detection,
campaign_techniques, campaign_attribution, group_techniques, software_techniques,
subtechnique_parent, tactic_technique_mitigations, technique_tactics,
tactic_techniques, datacomponent_analytics, node_lookup, label_scan; Gremlin:
capec_lookup, capec_neighbors, capec_maps_to, capec_reverse_maps, cwe_chain,
capec_hierarchy_chain, capec_scan). Federated entries live in
``federated_questions.py``. Gold IDs are resolved from the committed gold bank
at compile time — never typed by hand (Step 7 discipline).

Assertion vocabulary (consumed by the golden live-test runner):
  min_records / max_records  — bounds on len(result.records)
  expect_empty               — records must be empty AND result.ok True
  expect_boundary            — schema-boundary refusal: empty, ok, NO query
                               executed, summary names the unmodeled entity
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
CAMPAIGN_ANCHORS = ("C0027", "C0001")  # lookups; relationship coverage below (Step 7)
CAMPAIGN_TECH_ANCHORS = ("C0027", "C0024", "C0001")  # C0027, SolarWinds, Frankenstein
CAMPAIGN_ATTR_ANCHORS = ("C0027", "C0028")  # → G1015, → G0034 (web-verified anchors)
ASSET_BOUNDARY_ANCHORS = ("T1047", "T1490")  # Assets are ICS-only: honest refusal due
# CAPEC-557 is Deprecated -> excluded at load; it is exercised as a negative
# (C-NEG-02, expect-empty) rather than a positive lookup.
CAPEC_LOOKUP_ANCHORS = ("CAPEC-555", "CAPEC-116", "CAPEC-98", "CAPEC-163", "CAPEC-70")
CAPEC_CWE_ANCHORS = ("CAPEC-555", "CAPEC-98", "CAPEC-66")
CAPEC_PARENT_ANCHORS = ("CAPEC-98", "CAPEC-564", "CAPEC-555")
CAPEC_PRECEDE_ANCHORS = ("CAPEC-98", "CAPEC-555")
CAPEC_MAPS_ANCHORS = ("CAPEC-555", "CAPEC-98", "CAPEC-564", "CAPEC-70")

# -- Step 10 anchors (Slices B + C) --------------------------------------------
# ATT&CK: v19 detection remodel, software usage, hierarchy, 2-predicate, DC.
DETECTION_ANCHORS = ("T1047", "T1110", "T1566")
SOFTWARE_ANCHORS = ("S0002", "S0154", "S0266")  # Mimikatz, Cobalt Strike, TrickBot
SUBTECH_DOWN_ANCHOR = "T1021"       # parent -> its sub-techniques
SUBTECH_UP_ANCHOR = "T1055.012"     # sub-technique -> its parent
MULTI_CONSTRAINT_ANCHORS = (        # (tactic, mitigation): techniques in BOTH
    ("TA0006", "M1027"),
    ("TA0002", "M1038"),
    ("TA0006", "M1041"),
)
DATACOMPONENT_ANCHOR = "DC0084"
ATTACK_EXCLUDED_ANCHORS = ("T1002", "T1004")  # deprecated / revoked in v19
# CAPEC: execution flow, consequences/skills, abstraction chains, extra CWE
# coverage, extra deprecated negatives.
CAPEC_EXEC_ANCHORS = ("CAPEC-66", "CAPEC-98", "CAPEC-163")
CAPEC_CONSEQUENCE_ANCHORS = ("CAPEC-66", "CAPEC-98")
CAPEC_SKILL_ANCHOR = "CAPEC-163"
CAPEC_ABSTRACTION_CHAINS = (        # Detailed -> Standard -> Meta via ChildOf x2
    ("CAPEC-7", "CAPEC-66", "CAPEC-248"),
    ("CAPEC-16", "CAPEC-49", "CAPEC-112"),
    ("CAPEC-13", "CAPEC-77", "CAPEC-22"),
)
CAPEC_CWE_EXTRA_ANCHORS = ("CAPEC-600", "CAPEC-640")
CAPEC_DEPRECATED_ANCHORS = ("CAPEC-91", "CAPEC-106")


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

    # -- campaign -> techniques used (Step 7: relationship coverage) ---------------
    for i, cid in enumerate(CAMPAIGN_TECH_ANCHORS, start=1):
        top5 = _top_level_techniques(gold, attack["campaign_techniques"][cid], 5)
        cname = attack["objects"][cid]["name"]
        questions.append(
            {
                "id": f"A-CMP-TEC-{i:02d}",
                "tier": "medium",
                "question": f"Which techniques did campaign {cid} ({cname}) use?",
                "expected_template": "campaign_techniques",
                "task": _task(
                    f"A-CMP-TEC-{i:02d}", "attack",
                    f"Which techniques did ATT&CK campaign {cid} use?",
                    ("Campaign", "Technique"), (cid,),
                ),
                "assertions": {"min_records": 5, "must_include_ids": top5},
            }
        )

    # -- campaign -> attributed group (Step 7: relationship coverage) --------------
    for i, cid in enumerate(CAMPAIGN_ATTR_ANCHORS, start=1):
        groups = attack["campaign_attribution"][cid]
        cname = attack["objects"][cid]["name"]
        questions.append(
            {
                "id": f"A-CMP-ATT-{i:02d}",
                "tier": "medium",
                "question": f"Which group is campaign {cid} ({cname}) attributed to?",
                "expected_template": "campaign_attribution",
                "task": _task(
                    f"A-CMP-ATT-{i:02d}", "attack",
                    f"Which group is ATT&CK campaign {cid} attributed to?",
                    ("Campaign", "Group"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "max_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": list(groups),
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
    questions.append(
        {
            "id": "A-CMP-NEG-01",
            "tier": "adversarial",
            "question": "Techniques for nonexistent campaign C9999 — must return empty.",
            "expected_template": "campaign_techniques",
            "task": _task(
                "A-CMP-NEG-01", "attack",
                "Which techniques did ATT&CK campaign C9999 use?",
                ("Campaign", "Technique"), ("C9999",),
            ),
            "assertions": {"expect_empty": True},
        }
    )

    # -- negative Asset questions (Step 7): Assets exist only in ICS ATT&CK, so the
    # right answer is an honest schema-boundary refusal — no substitute query, no
    # invented asset list. These double as a live test of Step 6 abstention.
    for i, tid in enumerate(ASSET_BOUNDARY_ANCHORS, start=1):
        name = attack["objects"][tid]["name"]
        questions.append(
            {
                "id": f"A-AST-{i:02d}",
                "tier": "adversarial",
                "question": (
                    f"What assets does {tid} ({name}) target? "
                    f"(ICS-only concept — must refuse honestly, not invent)"
                ),
                "expected_template": "boundary_refusal",
                "task": _task(
                    f"A-AST-{i:02d}", "attack",
                    f"What assets does technique {tid} target?",
                    ("Technique", "Asset"), (tid,),
                ),
                "assertions": {"expect_boundary": True},
            }
        )

    # -- Step 10: technique -> detection strategy -> analytic (v19 remodel) -------
    for i, tid in enumerate(DETECTION_ANCHORS, start=1):
        dets = attack["technique_detections"][tid]
        analytics = sorted({an for det in dets for an in attack["detection_analytics"][det]})
        name = attack["objects"][tid]["name"]
        questions.append(
            {
                "id": f"A-DET-{i:02d}",
                "tier": "medium",
                "question": f"How is {tid} ({name}) detected, and via which analytics?",
                "expected_template": "technique_detection",
                "task": _task(
                    f"A-DET-{i:02d}", "attack",
                    f"Which detection strategies and analytics detect technique {tid}?",
                    ("Technique", "DetectionStrategy", "Analytic"), (tid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [tid],
                    "must_include_related": [*dets, *analytics],
                },
            }
        )

    # -- Step 10: software -> techniques used --------------------------------------
    for i, sid in enumerate(SOFTWARE_ANCHORS, start=1):
        t_ids = attack["software_techniques"][sid]
        sname = attack["objects"][sid]["name"]
        questions.append(
            {
                "id": f"A-SW-{i:02d}",
                "tier": "medium",
                "question": f"Which techniques does software {sid} ({sname}) use?",
                "expected_template": "software_techniques",
                "task": _task(
                    f"A-SW-{i:02d}", "attack",
                    f"Which ATT&CK techniques does software {sid} use?",
                    ("Software", "Technique"), (sid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [sid],
                    "must_include_related": list(t_ids),
                },
            }
        )

    # -- Step 10: sub-technique <-> parent hierarchy --------------------------------
    subs = attack["subtechniques"][SUBTECH_DOWN_ANCHOR]
    questions.append(
        {
            "id": "A-SUB-01",
            "tier": "medium",
            "question": f"What are the sub-techniques of {SUBTECH_DOWN_ANCHOR}?",
            "expected_template": "subtechnique_parent",
            "task": _task(
                "A-SUB-01", "attack",
                f"List the sub-techniques of ATT&CK technique {SUBTECH_DOWN_ANCHOR}.",
                ("Technique", "SubTechnique", "HAS_SUBTECHNIQUE"), (SUBTECH_DOWN_ANCHOR,),
            ),
            "assertions": {
                "min_records": 1,
                "must_include_ids": [SUBTECH_DOWN_ANCHOR],
                "must_include_related": list(subs),
            },
        }
    )
    parents = [p for p, kids in attack["subtechniques"].items() if SUBTECH_UP_ANCHOR in kids]
    if len(parents) != 1:
        raise ValueError(f"{SUBTECH_UP_ANCHOR} must have exactly one parent, got {parents}")
    questions.append(
        {
            "id": "A-SUB-02",
            "tier": "medium",
            "question": f"Which technique is {SUBTECH_UP_ANCHOR} a sub-technique of?",
            "expected_template": "subtechnique_parent",
            "task": _task(
                "A-SUB-02", "attack",
                f"Which parent technique does sub-technique {SUBTECH_UP_ANCHOR} belong to?",
                ("Technique", "SubTechnique", "HAS_SUBTECHNIQUE"), (SUBTECH_UP_ANCHOR,),
            ),
            "assertions": {
                "min_records": 1,
                "must_include_ids": [parents[0]],
                "must_include_related": [SUBTECH_UP_ANCHOR],
            },
        }
    )

    # -- Step 10: multi-constraint (technique in tactic X mitigated by Y) — Hard ---
    for i, (ta, m) in enumerate(MULTI_CONSTRAINT_ANCHORS, start=1):
        expected = [
            t
            for t in attack["tactic_techniques"][ta]
            if attack["objects"].get(t, {}).get("label") == "Technique"
            and m in attack["technique_mitigations"].get(t, [])
        ]
        if not expected:
            raise ValueError(f"multi-constraint anchor ({ta}, {m}) selects nothing")
        questions.append(
            {
                "id": f"A-MC-{i:02d}",
                "tier": "hard",
                "question": f"Which techniques in tactic {ta} are mitigated by {m}?",
                "expected_template": "tactic_technique_mitigations",
                "task": _task(
                    f"A-MC-{i:02d}", "attack",
                    f"Which techniques under tactic {ta} are mitigated by mitigation {m}?",
                    ("Tactic", "Technique", "Mitigation"), (ta, m),
                ),
                "assertions": {
                    "min_records": len(expected),
                    "max_records": len(expected),
                    "must_include_ids": list(expected),
                    "must_include_related": [ta, m],
                },
            }
        )

    # -- Step 10: data component -> analytics that monitor it ----------------------
    dc_analytics = attack["datacomponent_analytics"][DATACOMPONENT_ANCHOR]
    questions.append(
        {
            "id": "A-DCA-01",
            "tier": "easy",
            "question": f"Which analytics monitor data component {DATACOMPONENT_ANCHOR}?",
            "expected_template": "datacomponent_analytics",
            "task": _task(
                "A-DCA-01", "attack",
                f"Which analytics monitor data component {DATACOMPONENT_ANCHOR}?",
                ("DataComponent", "Analytic"), (DATACOMPONENT_ANCHOR,),
            ),
            "assertions": {
                "min_records": 1,
                "max_records": 1,
                "must_include_ids": [DATACOMPONENT_ANCHOR],
                "must_include_related": list(dc_analytics),
            },
        }
    )

    # -- Step 10: retired ids are excluded at load — honest empty, never invented --
    for i, tid in enumerate(ATTACK_EXCLUDED_ANCHORS, start=1):
        if tid not in attack["excluded_ids"]:
            raise ValueError(f"{tid} is no longer excluded — retired-id anchor invalid")
        if tid in attack["objects"]:
            raise ValueError(f"{tid} is live — retired-id anchor invalid")
        questions.append(
            {
                "id": f"A-EXC-{i:02d}",
                "tier": "adversarial",
                "question": f"Look up retired technique {tid} — excluded at load, must be empty.",
                "expected_template": "node_lookup",
                "task": _task(
                    f"A-EXC-{i:02d}", "attack",
                    f"What is ATT&CK technique {tid}?",
                    ("Technique",), (tid,),
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

    # -- retired id: excluded at load, must not be retrievable ---------------------------
    if "CAPEC-557" not in capec["deprecated"]:
        raise ValueError("CAPEC-557 is no longer retired — deprecated-exclusion anchor invalid")
    questions.append(
        {
            "id": "C-NEG-02",
            "tier": "adversarial",
            "question": "Look up deprecated CAPEC-557 — excluded at load, must return empty.",
            "expected_template": "capec_lookup",
            "task": _task(
                "C-NEG-02", "capec",
                "What is CAPEC pattern CAPEC-557?",
                ("AttackPattern",), ("CAPEC-557",),
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

    # -- Step 10: pattern -> execution steps (ordered flow) -------------------------
    for i, cid in enumerate(CAPEC_EXEC_ANCHORS, start=1):
        steps = capec["execution_steps"][cid]
        node_ids = list(dict.fromkeys(s["node_id"] for s in steps))
        questions.append(
            {
                "id": f"C-EXE-{i:02d}",
                "tier": "medium",
                "question": f"What are the execution steps of {cid}?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-EXE-{i:02d}", "capec",
                    f"What are the execution steps of {cid}?",
                    ("AttackPattern", "HAS_EXECUTION_STEP", "ExecutionStep"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": node_ids,
                },
            }
        )

    # -- Step 10: pattern -> consequences / skills (sub-element retrieval) ----------
    for i, cid in enumerate(CAPEC_CONSEQUENCE_ANCHORS, start=1):
        cons = [c["node_id"] for c in capec["consequences"][cid]]
        questions.append(
            {
                "id": f"C-CSQ-{i:02d}",
                "tier": "medium",
                "question": f"What consequences does {cid} have?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-CSQ-{i:02d}", "capec",
                    f"What are the consequences of attack pattern {cid}?",
                    ("AttackPattern", "HAS_CONSEQUENCE", "Consequence"), (cid,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [cid],
                    "must_include_related": cons,
                },
            }
        )
    skill_ids = [s["node_id"] for s in capec["skills"][CAPEC_SKILL_ANCHOR]]
    questions.append(
        {
            "id": "C-SKL-01",
            "tier": "medium",
            "question": f"What skills does {CAPEC_SKILL_ANCHOR} require?",
            "expected_template": "capec_neighbors",
            "task": _task(
                "C-SKL-01", "capec",
                f"What skills are required for attack pattern {CAPEC_SKILL_ANCHOR}?",
                ("AttackPattern", "REQUIRES_SKILL", "Skill"), (CAPEC_SKILL_ANCHOR,),
            ),
            "assertions": {
                "min_records": 1,
                "must_include_ids": [CAPEC_SKILL_ANCHOR],
                "must_include_related": skill_ids,
            },
        }
    )

    # -- Step 10: abstraction hierarchy 2-hop (Detailed -> Standard -> Meta) — Hard --
    for i, (detailed, standard, meta) in enumerate(CAPEC_ABSTRACTION_CHAINS, start=1):
        if standard not in capec["hierarchy"][detailed]["ChildOf"]:
            raise ValueError(f"{detailed} is not ChildOf {standard} — chain anchor invalid")
        if meta not in capec["hierarchy"][standard]["ChildOf"]:
            raise ValueError(f"{standard} is not ChildOf {meta} — chain anchor invalid")
        for cid, want in ((detailed, "Detailed"), (standard, "Standard"), (meta, "Meta")):
            got = capec["patterns"][cid]["abstraction"]
            if got != want:
                raise ValueError(f"{cid} abstraction {got!r} != {want!r} — chain anchor invalid")
        questions.append(
            {
                "id": f"C-ABS-{i:02d}",
                "tier": "hard",
                "question": (
                    f"Walk the abstraction hierarchy up from {detailed}: "
                    f"what are its standard and meta ancestors?"
                ),
                "expected_template": "capec_hierarchy_chain",
                "task": _task(
                    f"C-ABS-{i:02d}", "capec",
                    f"Which standard pattern is {detailed} a child of, and which meta "
                    f"pattern does that standard pattern belong to?",
                    ("AttackPattern", "ChildOf", "ChildOf"), (detailed,),
                ),
                "assertions": {
                    "min_records": 1,
                    "must_include_ids": [detailed],
                    "must_include_related": [standard, meta],
                },
            }
        )

    # -- Step 10: extra CWE-edge coverage --------------------------------------------
    for i, cid in enumerate(CAPEC_CWE_EXTRA_ANCHORS, start=1):
        cwes = capec["related_weaknesses"][cid]
        questions.append(
            {
                "id": f"C-CWE2-{i:02d}",
                "tier": "medium",
                "question": f"Which CWE weaknesses does {cid} target?",
                "expected_template": "capec_neighbors",
                "task": _task(
                    f"C-CWE2-{i:02d}", "capec",
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

    # -- Step 10: more deprecated-pattern negatives (exclude-at-load) -----------------
    for i, cid in enumerate(CAPEC_DEPRECATED_ANCHORS, start=1):
        if cid not in capec["deprecated"]:
            raise ValueError(f"{cid} is no longer retired — deprecated anchor invalid")
        questions.append(
            {
                "id": f"C-DEP-{i:02d}",
                "tier": "adversarial",
                "question": f"Look up deprecated {cid} — excluded at load, must return empty.",
                "expected_template": "capec_lookup",
                "task": _task(
                    f"C-DEP-{i:02d}", "capec",
                    f"What is CAPEC pattern {cid}?",
                    ("AttackPattern",), (cid,),
                ),
                "assertions": {"expect_empty": True},
            }
        )
    return questions
