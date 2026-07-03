#!/usr/bin/env python3
"""Cross-database join-key resolution: CAPEC -> ATT&CK.

This is where the composite key earns its keep across databases: every ATT&CK
technique referenced by CAPEC's ``ATTACK`` taxonomy mappings must resolve to an
ATT&CK record under the pair ``(attack_id, stix_type = 'attack-pattern')`` —
never to anything that merely shares the digits (e.g. a deprecated
course-of-action carrying the same ID).

A small number of legitimate misses is expected (CAPEC sometimes maps to
techniques ATT&CK has since revoked, or outside Enterprise); the exact
unresolved set is baselined in the expected fixture so a drop in resolution
rate between builds is a drift alarm, not a silent regression.

The named regression: CAPEC-555 maps to T1021, T1114.002 and T1133 (not
T1021.001, even though the ATT&CK T1021.001 page lists CAPEC-555). Asserting
the mapping direction directly catches a whole class of inversion bugs.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils.kg_builder.io import read_jsonl

from .composite_keys import EXPECTED_DIR

CAPEC_555_EXPECTED = ("T1021", "T1114.002", "T1133")


def capec_attack_mappings(
    capec_nodes_path: Path, capec_relationships_path: Path
) -> dict[str, list[str]]:
    """Return {capec_id: sorted ATT&CK technique ids} from MAPS_TO edges."""
    capec_id_by_node: dict[str, str] = {}
    attack_entry_by_node: dict[str, str] = {}
    for node in read_jsonl(capec_nodes_path):
        props = node.get("properties", {})
        if node.get("label") == "AttackPattern":
            # Canonical node ids are "capec:attack-pattern:<num>"; the numeric
            # CAPEC id is the last segment (no capec_id property is emitted).
            node_id = str(node.get("id", ""))
            capec_id_by_node[node_id] = str(
                props.get("capec_id") or node_id.rsplit(":", 1)[-1]
            )
        elif (
            node.get("label") == "TaxonomyEntry"
            and props.get("taxonomy_name") == "ATTACK"
            and props.get("entry_id")
        ):
            attack_entry_by_node[node.get("id")] = f"T{props['entry_id']}"

    mappings: dict[str, set[str]] = defaultdict(set)
    for edge in read_jsonl(capec_relationships_path):
        if edge.get("type") != "MAPS_TO":
            continue
        capec_id = capec_id_by_node.get(edge.get("source_id"))
        technique_id = attack_entry_by_node.get(edge.get("target_id"))
        if capec_id and technique_id:
            mappings[capec_id].add(technique_id)
    return {capec_id: sorted(ids) for capec_id, ids in sorted(mappings.items())}


def attack_technique_ids(attack_nodes_path: Path) -> set[str]:
    """ATT&CK ids that resolve under (attack_id, stix_type='attack-pattern')."""
    ids: set[str] = set()
    for node in read_jsonl(attack_nodes_path):
        props = node.get("properties", {})
        if props.get("stix_type") == "attack-pattern" and props.get("attack_id"):
            ids.add(props["attack_id"])
    return ids


def build_resolution_summary(
    capec_nodes_path: Path,
    capec_relationships_path: Path,
    attack_nodes_path: Path,
) -> dict[str, Any]:
    """Compute the payload stored in / compared against the expected fixture."""
    mappings = capec_attack_mappings(capec_nodes_path, capec_relationships_path)
    resolvable = attack_technique_ids(attack_nodes_path)

    referenced = sorted({tid for ids in mappings.values() for tid in ids})
    unresolved = sorted(tid for tid in referenced if tid not in resolvable)
    total = len(referenced)
    resolved = total - len(unresolved)
    return {
        "dataset": "capec",
        "mapping_count": sum(len(ids) for ids in mappings.values()),
        "unique_technique_ids": total,
        "resolved": resolved,
        "resolution_rate": round(resolved / total, 4) if total else 0.0,
        "unresolved": unresolved,
        "capec_555": mappings.get("555", []),
    }


def load_expected_resolution(expected_dir: Path | None = None) -> dict[str, Any]:
    path = (expected_dir or EXPECTED_DIR) / "capec_attack_resolution.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Expected resolution fixture missing: {path}. Regenerate after a "
            "deliberate snapshot change."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def cross_db_resolution_checks(
    capec_nodes_path: Path,
    capec_relationships_path: Path,
    attack_nodes_path: Path,
    expected_dir: Path | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Run the CAPEC->ATT&CK composite-key resolution checks."""
    from .harness import CheckResult

    checks: list[CheckResult] = []
    actual = build_resolution_summary(
        capec_nodes_path, capec_relationships_path, attack_nodes_path
    )

    try:
        expected = load_expected_resolution(expected_dir)
    except FileNotFoundError as exc:
        checks.append(CheckResult("capec_attack_resolution_baseline", False, str(exc)))
        return checks, actual

    exact = actual == expected
    checks.append(
        CheckResult(
            "capec_attack_resolution_baseline",
            exact,
            (
                f"{actual['resolved']}/{actual['unique_technique_ids']} technique ids "
                f"resolve under (attack_id, attack-pattern) "
                f"(rate {actual['resolution_rate']}), unresolved set matches baseline"
            )
            if exact
            else (
                f"resolution drifted: rate {actual['resolution_rate']} vs "
                f"{expected.get('resolution_rate')}, unresolved "
                f"{len(actual['unresolved'])} vs {len(expected.get('unresolved', []))}"
            ),
        )
    )

    capec_555 = tuple(actual.get("capec_555", []))
    checks.append(
        CheckResult(
            "capec_555_maps_to_expected_techniques",
            capec_555 == CAPEC_555_EXPECTED,
            f"CAPEC-555 -> {list(capec_555)} (expected {list(CAPEC_555_EXPECTED)})",
        )
    )
    return checks, actual
