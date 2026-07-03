#!/usr/bin/env python3
"""Composite (attack_id, stix_type) join-key checks.

An ATT&CK ID is never an identity on its own: the same external ID can appear
under more than one STIX object type (e.g. T1055 is both the live Process
Injection attack-pattern and a deprecated pre-2019 course-of-action). The
identity is the pair ``(attack_id, stix_type)`` — equivalently the STIX UUID.

This module makes that rule mechanical:

* enumerate the collision set independently from the **raw bundle** (all
  objects, including revoked/deprecated, mirroring a plain ``jq`` recount) and
  from the **canonical artifact** (post exclude-at-load, expected empty), and
  compare both against a checked-in expected-value fixture;
* assert every canonical node carries the three identity properties
  (``id``, ``attack_id``, ``stix_type``) and that no two canonical nodes share
  a ``(attack_id, stix_type)`` pair;
* declare the constraint names the live database must expose so the harness
  can fail loudly if one silently disappears.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils.kg_builder.config import BuildConfig
from utils.kg_builder.io import load_json, read_jsonl

EXPECTED_DIR = Path(__file__).parent / "expected"

# Constraint names the live backend must report (empty tuple = backend has no
# constraint support, nothing to assert).
REQUIRED_CONSTRAINT_NAMES: dict[tuple[str, str], tuple[str, ...]] = {
    ("attack", "neo4j"): ("attack_stix_id_unique", "attack_id_type_unique"),
    ("capec", "neo4j"): ("capec_object_id_unique",),
    ("attack", "gremlin"): (),
    ("capec", "gremlin"): (),
}


def raw_collision_set(build_config: BuildConfig) -> dict[str, list[str]]:
    """Enumerate ATT&CK IDs mapped to >1 STIX type straight from the raw bundle.

    Deliberately re-derived with minimal logic (independent of the build
    preprocessors) and over **all** objects — revoked and deprecated included —
    so it matches an external ``jq`` recount of the pinned snapshot.
    """
    bundle: dict[str, Any] = load_json(build_config.paths().attack_raw_file)
    types_by_id: dict[str, set[str]] = defaultdict(set)
    for obj in bundle.get("objects", []):
        stix_type = obj.get("type")
        if not stix_type or stix_type == "relationship":
            continue
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack" and ref.get("external_id"):
                types_by_id[ref["external_id"]].add(stix_type)
                break
    return {
        attack_id: sorted(types)
        for attack_id, types in sorted(types_by_id.items())
        if len(types) > 1
    }


def canonical_collision_set(nodes_path: Path) -> dict[str, list[str]]:
    """Enumerate (attack_id -> stix types) collisions in the canonical artifact."""
    types_by_id: dict[str, set[str]] = defaultdict(set)
    for node in read_jsonl(nodes_path):
        props = node.get("properties", {})
        attack_id = props.get("attack_id")
        stix_type = props.get("stix_type")
        if attack_id and stix_type:
            types_by_id[attack_id].add(stix_type)
    return {
        attack_id: sorted(types)
        for attack_id, types in sorted(types_by_id.items())
        if len(types) > 1
    }


def identity_property_gaps(nodes_path: Path) -> dict[str, int]:
    """Count canonical nodes missing any of the three identity properties."""
    gaps = {"id": 0, "attack_id": 0, "stix_type": 0}
    for node in read_jsonl(nodes_path):
        props = node.get("properties", {})
        if not node.get("id"):
            gaps["id"] += 1
        if not props.get("attack_id"):
            gaps["attack_id"] += 1
        if not props.get("stix_type"):
            gaps["stix_type"] += 1
    return gaps


def duplicate_pairs(nodes_path: Path) -> list[str]:
    """Return (attack_id, stix_type) pairs claimed by more than one node."""
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for node in read_jsonl(nodes_path):
        props = node.get("properties", {})
        attack_id = props.get("attack_id")
        stix_type = props.get("stix_type")
        if attack_id and stix_type:
            counts[(attack_id, stix_type)] += 1
    return sorted(f"({aid}, {stype})" for (aid, stype), n in counts.items() if n > 1)


def load_expected_collisions(
    dataset: str, expected_dir: Path | None = None
) -> dict[str, Any]:
    path = (expected_dir or EXPECTED_DIR) / f"{dataset}_collisions.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Expected collision fixture missing: {path}. "
            "Regenerate it with utils/graph_loader/fixture_qa/composite_keys.py "
            "(build_expected_collisions) after a deliberate snapshot change."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_expected_collisions(
    build_config: BuildConfig, nodes_path: Path
) -> dict[str, Any]:
    """Compute the payload stored in the expected-value fixture."""
    raw = raw_collision_set(build_config)
    canonical = canonical_collision_set(nodes_path)
    return {
        "dataset": "attack",
        "raw_collision_count": len(raw),
        "raw_collisions": raw,
        "canonical_collision_count": len(canonical),
        "canonical_collisions": canonical,
    }


def composite_key_checks(
    build_config: BuildConfig,
    nodes_path: Path,
    expected_dir: Path | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Run the artifact-level composite-key checks for the attack dataset.

    Returns (CheckResult list, identity payload for the report). CheckResult is
    imported lazily to avoid a circular import with the harness module.
    """
    from .harness import CheckResult

    checks: list[CheckResult] = []

    gaps = identity_property_gaps(nodes_path)
    missing_total = sum(gaps.values())
    checks.append(
        CheckResult(
            "identity_properties_present",
            missing_total == 0,
            f"missing id={gaps['id']}, attack_id={gaps['attack_id']}, "
            f"stix_type={gaps['stix_type']} (expected all 0)",
        )
    )

    dupes = duplicate_pairs(nodes_path)
    checks.append(
        CheckResult(
            "composite_pair_unique_in_canonical",
            not dupes,
            "no duplicate (attack_id, stix_type) pairs"
            if not dupes
            else f"duplicate pairs: {', '.join(dupes[:5])}",
        )
    )

    actual = build_expected_collisions(build_config, nodes_path)
    try:
        expected = load_expected_collisions("attack", expected_dir)
    except FileNotFoundError as exc:
        checks.append(CheckResult("collision_set_matches_expected", False, str(exc)))
        return checks, actual
    exact = actual == expected
    checks.append(
        CheckResult(
            "collision_set_matches_expected",
            exact,
            (
                f"raw collisions={actual['raw_collision_count']}, "
                f"canonical collisions={actual['canonical_collision_count']} "
                "== expected fixture"
            )
            if exact
            else (
                f"collision set drifted: raw {actual['raw_collision_count']} vs "
                f"expected {expected.get('raw_collision_count')}, canonical "
                f"{actual['canonical_collision_count']} vs "
                f"expected {expected.get('canonical_collision_count')}"
            ),
        )
    )

    return checks, actual


def constraint_check(dataset: str, backend: str, live_names: list[str]) -> Any | None:
    """Assert the live backend exposes the required constraint names."""
    from .harness import CheckResult

    required = REQUIRED_CONSTRAINT_NAMES.get((dataset, backend))
    if not required:
        return None
    missing = sorted(set(required) - set(live_names))
    return CheckResult(
        f"constraints_exist[{backend}]",
        not missing,
        f"all required constraints present: {', '.join(required)}"
        if not missing
        else f"missing constraints: {', '.join(missing)}",
    )
