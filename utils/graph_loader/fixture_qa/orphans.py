#!/usr/bin/env python3
"""Orphan / island checks.

Orphans come in two opposite kinds, and they demand opposite fixes:

* **Dead-object orphans (expected).** The node is revoked/deprecated; MITRE's
  data model kills every relationship whose endpoint is dead, so a correct
  loader leaves the object stranded. Both ATT&CK and CAPEC exclude these at load
  (ATT&CK via ``revoked``/``x_mitre_deprecated``, CAPEC via ``Status`` in
  {Deprecated, Obsolete}), so zero dead orphans are expected for either.
* **Live orphans (bugs, unless declared).** A live node with no edges means a
  connection mechanism the loader is not reading — or, rarely, an object the
  pinned snapshot genuinely never references, which must then be declared in
  the expected fixture (and the source card) as present-but-not-traversable.

Every orphan must land in exactly one bucket. The expected fixture is
exact-match: a fixed orphan that stays listed fails just as loudly as a new
one, so the allow-list can never go stale silently.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from utils.kg_builder.io import read_jsonl

from .composite_keys import EXPECTED_DIR

_CAPEC_DEAD_STATUSES = frozenset({"Deprecated", "Obsolete"})


def load_expected_orphans(dataset: str, expected_dir: Path | None = None) -> dict[str, Any]:
    path = (expected_dir or EXPECTED_DIR) / f"{dataset}_orphans.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Expected orphan fixture missing: {path}. Regenerate after a "
            "deliberate snapshot or loader-policy change."
        )
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _is_dead(dataset: str, node: dict[str, Any]) -> bool:
    props = node.get("properties", {})
    if dataset == "attack":
        return props.get("revoked") is True or props.get("x_mitre_deprecated") is True
    return props.get("Status") in _CAPEC_DEAD_STATUSES


def scan_canonical_orphans(
    dataset: str, nodes_path: Path, relationships_path: Path
) -> dict[str, Any]:
    """Zero-degree scan over the canonical artifacts, split dead vs live."""
    connected: set[str] = set()
    for edge in read_jsonl(relationships_path):
        connected.add(edge.get("source_id"))
        connected.add(edge.get("target_id"))

    dead_by_label: dict[str, int] = defaultdict(int)
    live_orphans: dict[str, dict[str, Any]] = {}
    orphan_ids: list[str] = []
    for node in read_jsonl(nodes_path):
        node_id = node.get("id")
        if node_id in connected:
            continue
        orphan_ids.append(node_id)
        label = node.get("label", "Unknown")
        if _is_dead(dataset, node):
            dead_by_label[label] += 1
        else:
            live_orphans[node_id] = {"label": label, "name": node.get("name")}

    return {
        "orphan_ids": sorted(orphan_ids),
        "dead_by_label": dict(sorted(dead_by_label.items())),
        "live_orphans": live_orphans,
    }


def orphan_checks(
    dataset: str,
    nodes_path: Path,
    relationships_path: Path,
    expected_dir: Path | None = None,
) -> tuple[list[Any], dict[str, Any]]:
    """Run the artifact-level orphan checks for one dataset."""
    from .harness import CheckResult

    checks: list[CheckResult] = []
    scan = scan_canonical_orphans(dataset, nodes_path, relationships_path)

    try:
        expected = load_expected_orphans(dataset, expected_dir)
    except FileNotFoundError as exc:
        checks.append(CheckResult("orphans_match_expected", False, str(exc)))
        return checks, scan

    # 1. Dead orphans match the recorded policy exactly (zero for both ATT&CK
    #    and CAPEC now that each excludes retired/revoked objects at load).
    expected_dead = dict(expected.get("expected_dead_orphans", {}))
    actual_dead = scan["dead_by_label"]
    checks.append(
        CheckResult(
            "dead_orphans_match_policy",
            actual_dead == expected_dead,
            f"dead orphans by label {actual_dead} == policy "
            f"({expected.get('policy', 'unset')}) expectation {expected_dead}"
            if actual_dead == expected_dead
            else f"dead orphans {actual_dead} != policy expectation {expected_dead}",
        )
    )

    # 2. Live orphans are exactly the declared allow-list: per-id entries plus
    #    per-label counts for classes of catalog entries (e.g. uncited
    #    ExternalReference records).
    allowed_ids = set(expected.get("allowed_live_orphans", {}))
    counted_labels = dict(expected.get("allowed_orphan_label_counts", {}))
    live = scan["live_orphans"]

    unexplained: list[str] = []
    live_label_counts: dict[str, int] = defaultdict(int)
    for node_id, info in live.items():
        if node_id in allowed_ids:
            continue
        if info["label"] in counted_labels:
            live_label_counts[info["label"]] += 1
            continue
        unexplained.append(f"{node_id} ({info['label']}: {info.get('name')})")

    stale_allowed = sorted(allowed_ids - set(live))
    label_mismatches = [
        f"{label}: live={live_label_counts.get(label, 0)} expected={count}"
        for label, count in counted_labels.items()
        if live_label_counts.get(label, 0) != count
    ]

    bug_free = not unexplained and not stale_allowed and not label_mismatches
    detail_parts: list[str] = []
    if unexplained:
        detail_parts.append(f"unexplained live orphans: {', '.join(unexplained[:5])}")
    if stale_allowed:
        detail_parts.append(
            f"stale allow-list entries (no longer orphaned): {', '.join(stale_allowed[:5])}"
        )
    if label_mismatches:
        detail_parts.append(f"label-count drift: {'; '.join(label_mismatches)}")
    checks.append(
        CheckResult(
            "bug_orphans_zero_or_declared",
            bug_free,
            f"{len(live)} live orphans, all declared "
            f"({len(allowed_ids)} by id, {sum(counted_labels.values())} by label count)"
            if bug_free
            else "; ".join(detail_parts),
        )
    )
    return checks, scan


def attack_named_regressions(
    nodes_path: Path,
    relationships_path: Path,
    expected: dict[str, Any],
) -> list[Any]:
    """The two named regressions Step 4 exists to prevent (ATT&CK)."""
    from .harness import CheckResult

    checks: list[CheckResult] = []

    has_tactic = sum(
        1 for edge in read_jsonl(relationships_path) if edge.get("type") == "HAS_TACTIC"
    )
    want = int(expected.get("matrix_tactic_count", -1))
    checks.append(
        CheckResult(
            "matrix_connects_all_tactics",
            has_tactic == want,
            f"HAS_TACTIC edges: {has_tactic} (expected {want} — Enterprise tactics)",
        )
    )

    connected: set[str] = set()
    for edge in read_jsonl(relationships_path):
        connected.add(edge.get("source_id"))
        connected.add(edge.get("target_id"))
    allowed_ids = set(expected.get("allowed_live_orphans", {}))
    disconnected = sorted(
        node.get("id")
        for node in read_jsonl(nodes_path)
        if node.get("label") == "DataComponent"
        and node.get("id") not in connected
        and node.get("id") not in allowed_ids
    )
    checks.append(
        CheckResult(
            "live_datacomponents_connected",
            not disconnected,
            "every live DataComponent has >=1 edge (or is a declared dead-end)"
            if not disconnected
            else f"disconnected DataComponents: {', '.join(disconnected[:5])}",
        )
    )
    return checks


def capec_hierarchy_checks(nodes_path: Path, relationships_path: Path) -> list[Any]:
    """CAPEC structural checks: ChildOf endpoints and acyclicity."""
    from .harness import CheckResult

    checks: list[CheckResult] = []
    labels: dict[str, str] = {}
    for node in read_jsonl(nodes_path):
        labels[node.get("id")] = node.get("label", "Unknown")

    bad_endpoints = 0
    children: dict[str, list[str]] = defaultdict(list)
    for edge in read_jsonl(relationships_path):
        if edge.get("type") != "ChildOf":
            continue
        source = edge.get("source_id")
        target = edge.get("target_id")
        if labels.get(source) != "AttackPattern" or labels.get(target) != "AttackPattern":
            bad_endpoints += 1
        children[source].append(target)

    checks.append(
        CheckResult(
            "childof_endpoints_are_attack_patterns",
            bad_endpoints == 0,
            f"{bad_endpoints} ChildOf edges with a non-AttackPattern endpoint (expected 0)",
        )
    )

    # Iterative three-color DFS: the hierarchy must be a DAG.
    state: dict[str, int] = {}
    cycle_found = False
    for start in list(children):
        if state.get(start) is not None:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        while stack and not cycle_found:
            node, index = stack.pop()
            if index == 0:
                state[node] = 1
            targets = children.get(node, [])
            if index < len(targets):
                stack.append((node, index + 1))
                nxt = targets[index]
                if state.get(nxt) == 1:
                    cycle_found = True
                elif state.get(nxt) is None:
                    stack.append((nxt, 0))
            else:
                state[node] = 2
        if cycle_found:
            break

    checks.append(
        CheckResult(
            "childof_hierarchy_acyclic",
            not cycle_found,
            "ChildOf hierarchy is a DAG"
            if not cycle_found
            else "cycle detected in ChildOf hierarchy",
        )
    )
    return checks


def live_orphan_check(
    backend: str, live_ids: list[str], canonical_ids: list[str]
) -> Any:
    """Live orphan set must equal the canonical orphan set exactly."""
    from .harness import CheckResult

    live_set = set(live_ids)
    canonical_set = set(canonical_ids)
    extra = sorted(live_set - canonical_set)
    missing = sorted(canonical_set - live_set)
    ok = not extra and not missing
    detail_parts = []
    if extra:
        detail_parts.append(f"live-only orphans: {', '.join(extra[:5])}")
    if missing:
        detail_parts.append(f"canonical-only orphans: {', '.join(missing[:5])}")
    return CheckResult(
        f"live_orphans_match_canonical[{backend}]",
        ok,
        f"{len(live_set)} live orphans == canonical scan"
        if ok
        else "; ".join(detail_parts),
    )
