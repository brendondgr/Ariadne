#!/usr/bin/env python3
"""Holdout bank integrity — no database, no LLM.

The holdout bank is compiled rather than authored, so these tests check the two
things a compiler can get wrong: that the entries are the same *shape* the
harness already runs (so the 30 questions execute unmodified), and that the gold
really is a recomputation from the raw snapshot rather than anything that leaked
in from the question text.

One thing deliberately NOT tested: that each entry routes to its
``expected_template``. That field is derived by the Compiler from the anchor's
type and category, because the Author never saw the template inventory. Asserting
on it would turn a derived value into a ground truth, which is exactly what
``expected_template_is_derived`` exists to prevent.
"""

from __future__ import annotations

import json

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset import holdout_protocol as hp
from utils.specialists.evalset.gold_bank import load_gold_bank
from utils.specialists.evalset.tests.test_banks import _CARDS
from utils.specialists.resolve import resolve

_ALL_TEMPLATES = {
    "technique_mitigations", "group_techniques", "software_techniques",
    "technique_detection", "technique_tactics", "subtechnique_parent",
    "tactic_techniques", "tactic_technique_mitigations", "campaign_techniques",
    "campaign_attribution", "datacomponent_analytics", "label_scan",
    "capec_maps_to", "capec_reverse_maps", "capec_neighbors",
    "capec_hierarchy_chain", "capec_scan", "capec_facets",
    "cwe_chain", "describe", "describe_by_name", "expand",
    "generic_neighbors",
}


@pytest.fixture(scope="module")
def bank() -> dict:
    return json.loads(hp.BANK_PATH.read_text())


@pytest.fixture(scope="module")
def gold() -> dict:
    return load_gold_bank()


def _single(bank: dict) -> list[dict]:
    return [q for q in bank["questions"] if "task" in q]


def _federated(bank: dict) -> list[dict]:
    return [q for q in bank["questions"] if "sub_questions" in q]


# -- shape ------------------------------------------------------------------


def test_bank_has_thirty_entries(bank: dict) -> None:
    assert len(bank["questions"]) == 30
    assert len(_single(bank)) == 20
    assert len(_federated(bank)) == 10


def test_every_entry_is_marked_holdout(bank: dict) -> None:
    for entry in bank["questions"]:
        assert entry["split"] == "holdout"
        assert entry["id"].startswith("H-")
        assert entry["holdout_meta"]["expected_template_is_derived"] is True
        assert entry["holdout_meta"]["author_model"] == "claude-fable-5 (high effort)"


def test_ids_are_unique(bank: dict) -> None:
    ids = [e["id"] for e in bank["questions"]]
    assert len(set(ids)) == 30


def test_derived_templates_name_real_identifiers(bank: dict) -> None:
    for entry in _single(bank):
        assert entry["expected_template"] in _ALL_TEMPLATES
    for entry in _federated(bank):
        for sub in entry["sub_questions"]:
            assert sub["expected_template"] in _ALL_TEMPLATES


def test_single_source_tasks_deserialize_and_resolve(bank: dict) -> None:
    for entry in _single(bank):
        task = SpecialistTask.from_dict(entry["task"])
        resolved = resolve(task, _CARDS[task.source])
        assert not resolved.unknown_entities, (
            f"{entry['id']}: entities unknown to the card: {resolved.unknown_entities}"
        )


def test_federated_sub_questions_deserialize_and_resolve(bank: dict) -> None:
    for entry in _federated(bank):
        assert entry["sources"] == ["capec", "attack"]
        for sub in entry["sub_questions"]:
            payload = {k: v for k, v in sub.items() if k not in ("expected_template", "seed_from")}
            payload["sub_question_id"] = payload.pop("id")
            payload["seed_ids"] = [entry["holdout_meta"]["anchor"]] if sub["id"] == "q1" else []
            task = SpecialistTask.from_dict(payload)
            resolved = resolve(task, _CARDS[task.source])
            assert not resolved.unknown_entities, (
                f"{entry['id']}/{sub['id']}: {resolved.unknown_entities}"
            )


# -- the question text is the Author's, unedited -----------------------------


def test_questions_are_byte_identical_to_the_authored_returns(bank: dict) -> None:
    authored = json.loads(hp.AUTHORED_PATH.read_text())["questions"]
    for entry in bank["questions"]:
        assert entry["question"] == authored[entry["id"]], f"{entry['id']} was edited"


def test_no_entry_leaks_the_answer_into_the_question(bank: dict) -> None:
    """A negative entry must not be signposted the way the dev bank's are.

    `F-NEG-01` carries "(verified: NO mapping …)" in its text. Copying that here
    would tell the system the answer.
    """
    for entry in bank["questions"]:
        assert "verified:" not in entry["question"].lower()


# -- gold is a recomputation -------------------------------------------------


def test_single_source_gold_matches_a_fresh_recomputation(bank: dict, gold: dict) -> None:
    for entry in _single(bank):
        meta = entry["holdout_meta"]
        anchor, category = meta["anchor"], meta["category"]
        assert entry["assertions"]["must_include_ids"] == [anchor]
        if category == "lookup":
            assert entry["assertions"]["expect_names"][anchor] == hp.entity_name(gold, anchor)
            continue
        assert entry["assertions"]["must_include_related"] == hp.neighbours(gold, category, anchor)
        assert entry["ex_gold"]["expected"] == hp.neighbours(gold, category, anchor)


def test_federated_correlation_matches_a_fresh_recomputation(bank: dict, gold: dict) -> None:
    for entry in _federated(bank):
        meta = entry["holdout_meta"]
        expected = hp.federated_correlation(gold, meta["category"], meta["anchor"])
        assert entry["assertions"]["must_correlate"] == (expected if expected else [])


def test_abstention_entries_assert_abstention_not_content(bank: dict) -> None:
    negatives = [
        e for e in _federated(bank)
        if e["holdout_meta"]["federated_partition"] == "abstention-expected"
    ]
    assert len(negatives) == hp.FEDERATED_ABSTENTION
    for entry in negatives:
        assert entry["assertions"]["expect_no_correlation"] is True
        assert entry["assertions"]["must_correlate"] == []


def test_answerable_entries_carry_a_non_empty_join(bank: dict) -> None:
    answerable = [
        e for e in _federated(bank)
        if e["holdout_meta"]["federated_partition"] == "answerable"
    ]
    assert len(answerable) == hp.FEDERATED_ANSWERABLE
    for entry in answerable:
        assert entry["assertions"]["must_correlate"]
        assert not entry["assertions"].get("expect_no_correlation")


def test_gold_provenance_pins_the_snapshot(bank: dict, gold: dict) -> None:
    for entry in bank["questions"]:
        assert entry["gold_provenance"] == {
            "attack_version": gold["meta"]["attack_version"],
            "capec_version": gold["meta"]["capec_version"],
        }
