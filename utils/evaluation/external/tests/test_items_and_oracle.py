#!/usr/bin/env python3
"""Item construction and the oracle ceiling (EXP-2026-08-010).

Two properties carry the experiment. The plan derived for an external item must
contain nothing the benchmark did not supply -- otherwise this repository is
quietly answering its own question again, which is the exact bias under test.
And the oracle must be a *bound*: it reads the canonical files, so if it ever
started going through retrieval it would stop bounding it.

The whole-benchmark checks are pinned to the reconnaissance numbers recorded in
PROTOCOL.md section 2. They are skipped rather than failed when the cache is
cold, because a missing download is not a defect in this code.
"""

from __future__ import annotations

import pytest

from utils.evaluation.external import fetch, items, oracle
from utils.evaluation.external.families import FAMILIES
from utils.evaluation.external.graph import load_attack


@pytest.fixture(scope="module")
def index():
    return load_attack()


def _item(**kw):
    base = dict(
        item_id="X-1", benchmark="attackqa",
        family="relationships_techniques_for_software", anchor="S0066",
        question="What attack techniques are used by software 'S0066: 3PARA RAT'?",
        gold=frozenset({"T1083"}), anchor_present=True, gold_present=True,
    )
    base.update(kw)
    return items.Item(**base)


# -- what a derived plan is allowed to contain -------------------------------


def test_a_plan_given_entry_matches_the_shape_this_projects_own_banks_use() -> None:
    """Two endpoint labels and the relationship type, as `H-SUB-01` carries.

    Withholding the relationship name looked like the purer control and was the
    opposite: it handed external questions a weaker plan than internal ones get,
    and zeroed two families outright (ISSUES.md I9).
    """
    task = _item().entry(plan_given=True)["task"]
    assert task["seed_ids"] == ["S0066"]
    assert task["source"] == "attack"
    assert task["entities"] == ["Software", "Technique", "USES"]
    assert task["join_key"] is None


def test_a_plan_given_entry_never_carries_the_gold() -> None:
    """The bank format has an `assertions` block and an `ex_gold` block.

    Both exist in this project's own banks. Either one here would hand the
    answer to the arm being measured.
    """
    entry = _item().entry(plan_given=True)
    assert "assertions" not in entry and "ex_gold" not in entry
    assert "T1083" not in str(entry)


def test_a_plan_free_entry_is_the_question_and_nothing_else() -> None:
    assert set(_item().entry(plan_given=False)) == {"id", "question"}


# -- the oracle bounds retrieval, it does not perform it ---------------------


def test_the_oracle_reads_the_graph_for_a_known_anchor(index) -> None:
    assert oracle.answer(_item(), index) == {
        "T1070.006", "T1071.001", "T1083", "T1573.001"}


def test_the_oracle_follows_a_family_in_the_direction_it_declares(index) -> None:
    """`campaigns_for_group` traverses ATTRIBUTED_TO backwards, not forwards."""
    got = oracle.answer(_item(
        family="relationships_campaigns_for_group", anchor="G0034"), index)
    assert got == {"C0025", "C0028", "C0034"}


def test_the_oracle_answer_survives_the_shared_extractor(index) -> None:
    """The ceiling is read by the same regex as every arm, so it carries any
    defect the extractor has instead of being advantaged by avoiding it."""
    from utils.evaluation.external.score import extract_ids

    item = _item()
    text = oracle.as_text(item, index)
    assert {i for i in extract_ids(text) if index.label_of.get(i) in
            FAMILIES[item.family].target_labels} == oracle.answer(item, index)


def test_an_anchor_the_graph_does_not_hold_yields_nothing(index) -> None:
    assert oracle.answer(_item(anchor="S9999"), index) == set()


def test_every_declared_family_resolves_against_the_real_graph(index) -> None:
    """A typo in a relationship name or a direction would silently score zero.

    Each family must return something for an anchor of its own kind. The anchors
    are chosen for connectivity rather than convenience: an isolated one proves
    nothing, and the first draft of this test failed on T1548 and S0066 -- both
    real entries that simply have no campaigns -- which is the reading error the
    test exists to prevent, not a defect in the mapping.
    """
    anchors = {
        "Software": ("S0089",), "Group": ("G0034",), "Campaign": ("C0028",),
        # Two techniques, because no single one is well connected in every
        # direction: T1105 is widely used but has no sub-techniques, and T1548
        # has six sub-techniques but no campaign uses it.
        "Technique": ("T1105", "T1548"), "SubTechnique": ("T1548.002",),
    }
    empty = []
    for family in FAMILIES.values():
        candidates = [a for label in family.anchor_labels
                      for a in anchors.get(label, ())]
        if not candidates:
            continue
        if not any(oracle.answer(_item(family=family.name, anchor=a), index)
                   for a in candidates):
            empty.append(family.name)
    assert empty == []


# -- the benchmarks as they actually are -------------------------------------


@pytest.fixture(scope="module")
def cti_ate(index):
    path = fetch.CACHE / fetch.CTI_ATE.filename
    if not path.is_file():
        pytest.skip("benchmark not fetched — run scripts/external_validation.py")
    return items.cti_ate_items(fetch.read_cti_ate(path), index)


def test_cti_ate_coverage_matches_what_the_protocol_recorded(cti_ate) -> None:
    """PROTOCOL.md section 2: 60 rows, 46 anchors present, 291/292 gold on those."""
    cov = items.coverage(cti_ate)
    assert cov["items"] == 60
    assert cov["anchor_present"] == 46
    present = [i for i in cti_ate if i.anchor_present]
    assert sum(len(i.gold) for i in present) == 292
    assert sum(len({g for g in i.gold if load_attack().has(g)})
               for i in present) == 291


def test_the_absent_rows_are_mobile_plus_one_retired_enterprise_entry(cti_ate) -> None:
    """Ariadne loads Enterprise only. The exclusion is a scope fact, not a bug,
    and it is counted rather than quietly dropped (D-021)."""
    absent = [i for i in cti_ate if not i.anchor_present]
    assert len(absent) == 14
    mobile = [i for i in absent if i.notes["platform"] == "Mobile"]
    assert len(mobile) == 13
    assert [i.anchor for i in absent if i.notes["platform"] == "Enterprise"] == ["S0440"]


def test_cti_ate_gold_is_parent_techniques_and_is_rolled_to_match(cti_ate) -> None:
    assert all(i.roll_to_parents for i in cti_ate)
    assert not any("." in g for i in cti_ate for g in i.gold)
