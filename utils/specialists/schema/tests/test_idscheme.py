#!/usr/bin/env python3
"""Identifier-scheme learning, and the three-valued verdict built on it.

Two fixtures carry the weight here, and the second is the point of the module.
``_MITRE_NODES`` is ATT&CK-shaped and proves the learner recovers the identifier
families the hand-written regexes in ``resolve/resolver.py`` currently hardcode.
``_OCSF_NODES`` is shaped like normalised security telemetry — devices, users,
processes, findings — and shares no prefix, separator or convention with MITRE.
Nothing in ``idscheme.py`` is told which fixture it is reading.

The opaque-identifier case is tested deliberately rather than tolerated: a label
keyed by UUID must come back *undetermined*, never mismatched, because a
mismatch reported from an unlearnable property is a false accusation against
data the system does not understand.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from utils.specialists.schema import build_registry, get_registry
from utils.specialists.schema.idscheme import (
    CONSISTENT,
    MAX_SCHEMES,
    MISMATCH,
    UNDETERMINED,
    PropertySchemes,
    combine_verdicts,
    learn_schemes,
    scheme_of,
)


# -- fixtures ----------------------------------------------------------------

# ATT&CK-shaped: the analyst identifier lives in a property, the node id is an
# opaque STIX UUID.
_MITRE_NODES = [
    {"id": "attack-pattern--0042a9f5-f053-4769-b3ef-9ad018dfa298", "label": "Technique",
     "properties": {"attack_id": "T1047", "name": "WMI"}},
    {"id": "attack-pattern--1142a9f5-f053-4769-b3ef-9ad018dfa299", "label": "SubTechnique",
     "properties": {"attack_id": "T1055.011", "name": "EWM Injection"}},
    {"id": "intrusion-set--00f67a77-86a4-4adf-be26-1a54fc713340", "label": "Group",
     "properties": {"attack_id": "G0082", "name": "Sandworm"}},
    {"id": "malware--007b44b6-e4c5-480b-b5b9-56f2081b1b7b", "label": "Software",
     "properties": {"attack_id": "S0061", "name": "HDoor"}},
    {"id": "x-mitre-tactic--2558fd61-8c75-4730-94c4-11926db2a263", "label": "Tactic",
     "properties": {"attack_id": "TA0006", "name": "Credential Access"}},
]

def _uuid(index: int) -> str:
    """A stable UUID-shaped identifier — deterministic, so the fixture is too."""
    digest = hashlib.md5(f"process-{index}".encode()).hexdigest()
    return f"{digest[:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:]}"


# OCSF-shaped: nothing here resembles MITRE. ``Process`` is keyed by UUID and is
# the deliberately unlearnable label.
_OCSF_NODES = [
    {"id": "dev-1001", "label": "Device",
     "properties": {"uid": "dev-1001", "hostname": "fs-finance-01", "type_id": "3"}},
    {"id": "dev-1002", "label": "Device",
     "properties": {"uid": "dev-1002", "hostname": "wks-analyst-07", "type_id": "1"}},
    {"id": "usr-88", "label": "User",
     "properties": {"uid": "usr-88", "principal": "j.doe@example.test"}},
    {"id": "usr-91", "label": "User",
     "properties": {"uid": "usr-91", "principal": "a.roe@example.test"}},
    {"id": "finding:2026:0001", "label": "Finding",
     "properties": {"uid": "finding:2026:0001", "attack_technique": "T1047",
                    "title": "Suspicious WMI execution"}},
    {"id": "finding:2026:0002", "label": "Finding",
     "properties": {"uid": "finding:2026:0002", "attack_technique": "T1003",
                    "title": "Credential dumping attempt"}},
] + [
    # Real UUIDs, deterministically generated: enough distinct digit/letter
    # layouts to blow past MAX_SCHEMES and mark the property open.
    {"id": _uuid(i), "label": "Process",
     "properties": {"uid": _uuid(i), "cmd_line_id": f"c{i}"}}
    for i in range(120)
]

_OCSF_RELS = [
    {"id": "e1", "type": "RAN_ON", "source_id": "finding:2026:0001", "target_id": "dev-1001"},
    {"id": "e2", "type": "ATTRIBUTED_TO", "source_id": "finding:2026:0001", "target_id": "usr-88"},
]


def _write_canonical(data_dir: Path, dataset: str, nodes, rels) -> None:
    canonical = data_dir / "graphs" / dataset / "canonical"
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "nodes.jsonl").write_text(
        "\n".join(json.dumps(n) for n in nodes) + "\n", encoding="utf-8"
    )
    (canonical / "relationships.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rels) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def ocsf_schema(tmp_path: Path):
    _write_canonical(tmp_path, "telemetry", _OCSF_NODES, _OCSF_RELS)
    schema = build_registry(tmp_path).dataset("telemetry")
    assert schema is not None
    return schema


# -- scheme_of ---------------------------------------------------------------


def test_digit_runs_collapse_regardless_of_length() -> None:
    # The whole point: CAPEC-9 and CAPEC-1000 are one kind of identifier.
    assert scheme_of("CAPEC-9") == scheme_of("CAPEC-1000") == "capec-#"


def test_non_digits_survive_verbatim_and_case_folds() -> None:
    assert scheme_of("T1550.002") == "t#.#"
    assert scheme_of("t1550.002") == "t#.#"
    assert scheme_of("TA0006") == "ta#"
    assert scheme_of("capec:attack-pattern:1") == "capec:attack-pattern:#"


def test_prose_and_non_strings_are_not_identifiers() -> None:
    assert scheme_of("Credential Access") is None  # whitespace
    assert scheme_of("") is None
    assert scheme_of(None) is None
    assert scheme_of(1047) is None
    assert scheme_of("x" * 200) is None


# -- learning ----------------------------------------------------------------


def test_mitre_families_are_learned_without_naming_them() -> None:
    learned = learn_schemes(_MITRE_NODES)
    assert learned["Group"]["attack_id"].schemes == frozenset({"g#"})
    assert learned["Technique"]["attack_id"].schemes == frozenset({"t#"})
    assert learned["SubTechnique"]["attack_id"].schemes == frozenset({"t#.#"})
    assert learned["Tactic"]["attack_id"].schemes == frozenset({"ta#"})
    # T and TA are distinguished by the literal prefix, not by a rule about MITRE.
    assert learned["Tactic"]["attack_id"].admits("T1047") == MISMATCH


def test_the_defect_is_expressible_as_a_verdict() -> None:
    # This is the blind-holdout failure, stated as data rather than as a bug
    # report: the query filtered Group.attack_id against a technique id.
    learned = learn_schemes(_MITRE_NODES)
    assert learned["Group"]["attack_id"].admits("T1550.002") == MISMATCH
    assert learned["Group"]["attack_id"].admits("G0082") == CONSISTENT


def test_a_foreign_dataset_learns_the_same_way(ocsf_schema) -> None:
    assert ocsf_schema.id_schemes("Device", "uid").schemes == frozenset({"dev-#"})
    assert ocsf_schema.id_schemes("User", "uid").schemes == frozenset({"usr-#"})
    assert ocsf_schema.id_schemes("Finding", "uid").schemes == frozenset({"finding:#:#"})
    assert ocsf_schema.value_verdict("Device", "uid", "usr-88") == MISMATCH
    assert ocsf_schema.value_verdict("Device", "uid", "dev-1003") == CONSISTENT


def test_opaque_identifiers_are_undetermined_never_mismatched(ocsf_schema) -> None:
    uid = ocsf_schema.id_schemes("Process", "uid")
    assert uid.is_open
    assert uid.schemes == frozenset()
    # Any value at all, including one that plainly belongs to another label.
    assert ocsf_schema.value_verdict("Process", "uid", "dev-1001") == UNDETERMINED
    assert ocsf_schema.value_verdict("Process", "uid", "anything") == UNDETERMINED


def test_an_unobserved_pair_is_undetermined(ocsf_schema) -> None:
    assert ocsf_schema.value_verdict("Device", "no_such_property", "dev-1001") == UNDETERMINED
    assert ocsf_schema.value_verdict("NoSuchLabel", "uid", "dev-1001") == UNDETERMINED


def test_prose_properties_learn_nothing_at_all(ocsf_schema) -> None:
    # A whitespace-bearing property is never learned, so it cannot be judged
    # against and cannot vote on a label.
    assert ocsf_schema.id_schemes("Finding", "title") is None
    assert ocsf_schema.value_verdict("Finding", "title", "anything") == UNDETERMINED
    # A hostname has no digits and no whitespace, so it does learn — the rule is
    # about shape, not about a property being "an id".
    assert ocsf_schema.id_schemes("Device", "hostname").schemes == frozenset(
        {"fs-finance-#", "wks-analyst-#"}
    )


# -- label inference ---------------------------------------------------------


def test_labels_for_id_infers_one_label(ocsf_schema) -> None:
    assert ocsf_schema.labels_for_id("dev-1001") == frozenset({"Device"})
    assert ocsf_schema.labels_for_id("usr-88") == frozenset({"User"})


def test_labels_for_id_returns_nothing_for_an_unknown_shape(ocsf_schema) -> None:
    assert ocsf_schema.labels_for_id("T1047") != frozenset({"Device"})
    assert ocsf_schema.labels_for_id("no-such-scheme-@@") == frozenset()


def test_open_properties_contribute_no_labels(ocsf_schema) -> None:
    # Process.uid admits everything; if open properties voted, every lookup
    # would return Process and the inference would be worthless.
    assert "Process" not in ocsf_schema.labels_for_id("dev-1001")


def test_a_shared_scheme_is_an_ambiguity_not_a_guess(tmp_path: Path) -> None:
    nodes = [
        {"id": "x-1", "label": "Alpha", "properties": {"uid": "x-1"}},
        {"id": "x-2", "label": "Beta", "properties": {"uid": "x-2"}},
    ]
    _write_canonical(tmp_path, "ambig", nodes, [])
    schema = build_registry(tmp_path).dataset("ambig")
    assert schema.labels_for_id("x-3") == frozenset({"Alpha", "Beta"})


# -- verdict folding ---------------------------------------------------------


def test_combine_verdicts_prefers_a_fit_and_needs_unanimity_to_accuse() -> None:
    assert combine_verdicts([]) == UNDETERMINED
    assert combine_verdicts([MISMATCH, CONSISTENT]) == CONSISTENT
    assert combine_verdicts([MISMATCH, UNDETERMINED]) == UNDETERMINED
    assert combine_verdicts([MISMATCH, MISMATCH]) == MISMATCH


def test_empty_scheme_set_admits_nothing_confidently() -> None:
    assert PropertySchemes("L", "p").admits("anything") == UNDETERMINED


# -- opt-in cross-check against the real canonical artifacts -----------------


def _real_data_present() -> bool:
    return Path("data/graphs/attack/canonical/nodes.jsonl").is_file()


@pytest.mark.skipif(not _real_data_present(), reason="real canonical artifacts not present")
def test_real_attack_and_capec_schemes() -> None:
    get_registry.cache_clear()
    registry = build_registry("data")

    attack = registry.dataset("attack")
    assert attack.id_schemes("Group", "attack_id").schemes == frozenset({"g#"})
    assert attack.value_verdict("Group", "attack_id", "T1550.002") == MISMATCH
    assert attack.value_verdict("Group", "attack_id", "G0082") == CONSISTENT
    # The STIX node id is a UUID: opaque, so it must not judge anything.
    assert attack.id_schemes("Group", "id").is_open
    assert attack.labels_for_id("G0082") == frozenset({"Group"})

    capec = registry.dataset("capec")
    # CAPEC's analyst identifier *is* the node id, so the same machinery reads a
    # different location without being told.
    assert capec.labels_for_id("capec:attack-pattern:116") == frozenset({"AttackPattern"})
    assert capec.labels_for_id("cwe:1243") == frozenset({"Weakness"})
