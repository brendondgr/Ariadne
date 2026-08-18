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
    FEDERATED_BANK_PATH,
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
    if entry["assertions"].get("expect_boundary"):
        # Boundary entries deliberately name an entity the card doesn't model;
        # the specialist must refuse before the builder is ever consulted.
        assert entry["expected_template"] == "boundary_refusal"
        assert resolved.unknown_entities, (
            f"{entry['id']}: boundary entry but every entity resolved — "
            f"the refusal would never fire"
        )
        return
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
        "min_records", "max_records", "expect_empty", "expect_no_join", "expect_boundary",
        "must_include_ids", "must_include_related", "forbid_ids",
        "expect_names", "expect_properties",
    }
    for entry in _all_entries():
        assertions = entry["assertions"]
        assert assertions, f"{entry['id']}: no assertions"
        unknown = set(assertions) - allowed
        assert not unknown, f"{entry['id']}: unknown assertion keys {unknown}"
        if not any(
            assertions.get(key)
            for key in ("expect_empty", "expect_no_join", "expect_boundary")
        ):
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
    attack_bank, capec_bank, federated_bank = compile_banks()
    assert attack_bank == json.loads(ATTACK_BANK_PATH.read_text()), (
        "attack_questions.json is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.compile_banks`"
    )
    assert capec_bank == json.loads(CAPEC_BANK_PATH.read_text())
    assert federated_bank == json.loads(FEDERATED_BANK_PATH.read_text()), (
        "federated_questions.json is stale — regenerate with "
        "`uv run python -m utils.specialists.evalset.compile_banks`"
    )


def test_negative_anchor_capec_116_still_negative() -> None:
    # compile_banks raises if CAPEC-116 ever gains a mapping; the committed
    # bank must contain the abstention question.
    entries = {e["id"]: e for e in _bank_questions(CAPEC_BANK_PATH)}
    assert entries["C-MAP-NEG-01"]["assertions"] == {"expect_no_join": True}


# -- federated bank invariants (Slice A) ------------------------------------------

_FEDERATED = _bank_questions(FEDERATED_BANK_PATH)
_FED_SIDE_KEYS = {
    "min_records", "max_records", "expect_empty", "expect_no_join", "expect_boundary",
    "must_include_ids", "must_include_related", "forbid_ids",
    "expect_names", "expect_properties",
    # federated-only vocabulary:
    "expect_dependency_skip", "expect_skipped",
}


def test_federated_bank_census() -> None:
    ids = [e["id"] for e in _FEDERATED]
    assert len(ids) == len(set(ids))
    assert len(_FEDERATED) == 40
    # Full catalogue: 120 questions, exactly one third federated.
    total = len(_all_entries()) + len(_FEDERATED)
    assert total == 120, f"catalogue is {total}, expected exactly 120"


def test_catalogue_census_source_and_tier_split() -> None:
    """The Step 10 definition of done: exactly 120 entries with the recorded
    source and tier distribution. A drift here is a deliberate catalogue
    change and must update this census (and the docs) explicitly."""
    from collections import Counter

    attack = _bank_questions(ATTACK_BANK_PATH)
    capec = _bank_questions(CAPEC_BANK_PATH)
    assert len(attack) == 46
    assert len(capec) == 34
    assert len(_FEDERATED) == 40

    tiers = Counter(e["tier"] for e in attack + capec + _FEDERATED)
    assert tiers == {
        "easy": 22,
        "medium": 52,
        "hard": 24,
        "adversarial": 22,
    }, f"tier split drifted: {dict(tiers)}"
    # Federated tiers specifically: the hard/adversarial weighting is the point.
    fed_tiers = Counter(e["tier"] for e in _FEDERATED)
    assert fed_tiers == {"hard": 18, "medium": 12, "adversarial": 10}


def test_federated_entries_are_cross_source() -> None:
    for entry in _FEDERATED:
        assert sorted(entry["sources"]) == ["attack", "capec"], entry["id"]
        subs = entry["sub_questions"]
        assert {s["source"] for s in subs} == {"attack", "capec"}, entry["id"]
        assert entry["hops"] >= 1
        assert entry["gold_provenance"] == {
            "attack_version": "19.0", "capec_version": "3.9",
        }, entry["id"]


def test_federated_assertions_are_well_formed() -> None:
    for entry in _FEDERATED:
        assertions = entry["assertions"]
        assert "must_correlate" in assertions, entry["id"]
        if assertions.get("expect_no_correlation"):
            assert assertions["must_correlate"] == [], entry["id"]
        else:
            assert assertions["must_correlate"], (
                f"{entry['id']}: positive federated entry with empty must_correlate"
            )
        for side in ("capec", "attack"):
            block = assertions[side]
            unknown = set(block) - _FED_SIDE_KEYS
            assert not unknown, f"{entry['id']}.{side}: unknown keys {unknown}"


def test_federated_sequencing_declares_one_producer_one_consumer() -> None:
    for entry in _FEDERATED:
        subs = {s["id"]: s for s in entry["sub_questions"]}
        seeded = [s for s in subs.values() if s.get("seed_from")]
        if entry["sequenced"]:
            assert len(seeded) == 1, entry["id"]
            consumer = seeded[0]
            assert consumer["source"] == "attack", entry["id"]
            assert consumer["seed_from"] in subs, entry["id"]
            assert subs[consumer["seed_from"]]["source"] == "capec", entry["id"]
            # Sequenced consumers must not carry ids in text — their seeds are
            # harvested join values, never text extraction.
            producer_text_ids = [w for w in consumer["text"].split() if w.startswith("T")]
            assert not any(
                w.strip("?.,").replace(".", "").lstrip("T").isdigit()
                for w in producer_text_ids
            ), f"{entry['id']}: consumer text carries technique ids"
        else:
            assert not seeded, entry["id"]


def test_federated_must_correlate_is_the_computed_intersection() -> None:
    """Re-derive every must_correlate set from the gold bank maps: the
    CAPEC-side ATTACK-taxonomy mappings intersected with ATT&CK-side
    existence. Zero hand-keyed join values."""
    from utils.specialists.evalset.gold_bank import load_gold_bank

    gold = load_gold_bank()
    capec, attack = gold["capec"], gold["attack"]
    reverse: dict[str, list[str]] = {}
    for cid, t_ids in capec["attack_mappings"].items():
        for t in t_ids:
            reverse.setdefault(t, []).append(cid)

    for entry in _FEDERATED:
        want = entry["assertions"]["must_correlate"]
        prefix = entry["id"].rsplit("-", 1)[0]
        capec_text = next(
            s["text"] for s in entry["sub_questions"] if s["source"] == "capec"
        )
        if prefix in ("F-CTM", "F-CTT", "F-NEG", "F-FAN"):
            cids = [w.strip("?.,()") for w in capec_text.split() if w.startswith("CAPEC-")]
            derived = sorted(
                {
                    t
                    for c in cids
                    for t in capec["attack_mappings"].get(c, [])
                    if t in attack["objects"]
                }
            )
            assert want == derived, f"{entry['id']}: {want} != derived {derived}"
        elif prefix == "F-REV":
            tids = [w.strip("?.,()") for w in capec_text.split() if w.startswith("T")]
            assert len(tids) == 1 and want == tids, entry["id"]
            assert reverse.get(tids[0]), entry["id"]
        elif prefix == "F-CWE":
            cwes = [w.strip("?.,()") for w in capec_text.split() if w.startswith("CWE-")]
            assert len(cwes) == 1, entry["id"]
            derived = sorted(
                {
                    t
                    for c in capec["cwe_to_capec"].get(cwes[0], [])
                    for t in capec["attack_mappings"].get(c, [])
                    if t in attack["objects"]
                }
            )
            assert want == derived, f"{entry['id']}: {want} != derived {derived}"
        elif prefix == "F-PART":
            assert want == [], entry["id"]
        else:
            pytest.fail(f"unknown federated prefix {prefix}")


@pytest.mark.parametrize(
    "entry",
    [e for e in _FEDERATED],
    ids=lambda e: e["id"],
)
def test_federated_sub_questions_route_to_expected_templates(entry: dict) -> None:
    """Producers route from their own text; sequenced consumers route once the
    harvested seeds are injected (simulated here with the must_correlate set)."""
    for sub in entry["sub_questions"]:
        card = _CARDS[sub["source"]]
        seed_ids: tuple[str, ...] = ()
        if sub.get("seed_from"):
            seeds = entry["assertions"]["must_correlate"] or ["T1047"]
            seed_ids = tuple(seeds)
        task = SpecialistTask(
            sub_question_id=sub["id"],
            source=sub["source"],
            text=sub["text"],
            entities=tuple(sub["entities"]),
            seed_ids=seed_ids,
            join_key=sub.get("join_key"),
            limits=sub["limits"],
        )
        resolved = resolve(task, card)
        if sub["expected_template"] == "boundary_refusal":
            assert resolved.unknown_entities, entry["id"]
            continue
        draft = _BUILDERS[sub["source"]].build(resolved)
        assert draft.template == sub["expected_template"], (
            f"{entry['id']}/{sub['id']}: routed to {draft.template!r}, "
            f"bank expects {sub['expected_template']!r}"
        )
