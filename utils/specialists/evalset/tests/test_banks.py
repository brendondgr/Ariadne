#!/usr/bin/env python3
"""Bank integrity + routing tests — no database, no LLM.

Every committed bank entry must (a) deserialize into a valid SpecialistTask,
(b) resolve against a schema card, and (c) route to exactly the builder
template the bank says it exercises. A bank/builder drift fails here in
milliseconds instead of surfacing as a confusing live failure.
"""

from __future__ import annotations

import json

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    compile_banks,
    load_bank,
)
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve

# Schema stubs: resolve() only consults dataset/has_label/has_relationship/
# node_properties/provenance, so the routing tests stay hermetic (no data/
# artifacts needed). Label/relationship lists mirror the generated cards.
_ATTACK_LABELS = {
    "Technique", "SubTechnique", "Tactic", "Mitigation", "Group", "Software",
    "Campaign", "DataComponent", "DetectionStrategy", "Analytic", "Matrix",
}
_ATTACK_RELS = {"USES", "MITIGATES", "HAS_TECHNIQUE", "HAS_SUBTECHNIQUE",
                "ATTRIBUTED_TO", "DETECTS", "HAS_TACTIC", "HAS_ANALYTIC", "MONITORS"}
_CAPEC_LABELS = {
    "AttackPattern", "Category", "Consequence", "ExecutionStep", "ExternalReference",
    "Mitigation", "Skill", "TaxonomyEntry", "View", "Weakness",
}
_CAPEC_RELS = {
    "ChildOf", "ParentOf", "CanPrecede", "CanFollow", "CanAlsoBe", "PeerOf",
    "EXPLOITS_WEAKNESS", "HAS_MITIGATION", "HAS_EXECUTION_STEP", "HAS_CONSEQUENCE",
    "REQUIRES_SKILL", "MAPS_TO", "MEMBER_OF", "IN_VIEW", "HAS_REFERENCE", "NEXT_STEP",
}


class _SchemaCard:
    def __init__(self, dataset: str, labels: set[str], rels: set[str]) -> None:
        self.dataset = dataset
        self._labels = labels
        self._rels = rels
        self.node_properties: dict = {}
        self.provenance = {"id_scheme": f"{dataset}-id"}

    def has_label(self, name: str) -> bool:
        return name in self._labels

    def has_relationship(self, name: str) -> bool:
        return name in self._rels


_CARDS = {
    "attack": _SchemaCard("attack", _ATTACK_LABELS, _ATTACK_RELS),
    "capec": _SchemaCard("capec", _CAPEC_LABELS, _CAPEC_RELS),
}
_BUILDERS = {"attack": CypherQueryBuilder(), "capec": GremlinQueryBuilder()}


def _bank_questions(path) -> list[dict]:
    return load_bank(path)["questions"]


def _all_entries() -> list[dict]:
    return _bank_questions(ATTACK_BANK_PATH) + _bank_questions(CAPEC_BANK_PATH)


@pytest.mark.parametrize("entry", _all_entries(), ids=lambda e: e["id"])
def test_entry_resolves_and_routes_to_expected_template(entry: dict) -> None:
    task = SpecialistTask.from_dict(entry["task"])
    card = _CARDS[task.source]
    resolved = resolve(task, card)
    assert not resolved.unknown_entities, (
        f"{entry['id']}: entities unknown to the card: {resolved.unknown_entities}"
    )
    draft = _BUILDERS[task.source].build(resolved)
    assert draft.template == entry["expected_template"], (
        f"{entry['id']}: routed to {draft.template!r}, "
        f"bank expects {entry['expected_template']!r}"
    )
    # Every draft must parameterize its seeds — never inline concrete ids.
    for seed in task.seed_ids:
        assert seed not in draft.query


def test_assertions_are_well_formed() -> None:
    allowed = {
        "min_records", "max_records", "expect_empty", "must_include_ids",
        "must_include_related", "forbid_ids", "expect_names", "expect_properties",
    }
    for entry in _all_entries():
        assertions = entry["assertions"]
        assert assertions, f"{entry['id']}: no assertions"
        unknown = set(assertions) - allowed
        assert not unknown, f"{entry['id']}: unknown assertion keys {unknown}"
        if not assertions.get("expect_empty"):
            assert (
                "min_records" in assertions or "must_include_ids" in assertions
            ), f"{entry['id']}: non-negative entries need a records floor"


def test_bank_ids_unique_and_counts() -> None:
    entries = _all_entries()
    ids = [e["id"] for e in entries]
    assert len(ids) == len(set(ids))
    assert len(_bank_questions(ATTACK_BANK_PATH)) >= 20
    assert len(_bank_questions(CAPEC_BANK_PATH)) >= 18


def test_banks_are_fresh() -> None:
    attack_bank, capec_bank = compile_banks()
    assert attack_bank == json.loads(ATTACK_BANK_PATH.read_text()), (
        "attack_questions.json is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.compile_banks`"
    )
    assert capec_bank == json.loads(CAPEC_BANK_PATH.read_text())


def test_negative_anchor_capec_116_still_negative() -> None:
    # compile_banks raises if CAPEC-116 ever gains a mapping; the committed
    # bank must contain the abstention question.
    entries = {e["id"]: e for e in _bank_questions(CAPEC_BANK_PATH)}
    assert entries["C-MAP-NEG-01"]["assertions"] == {"expect_empty": True}
