"""Hermetic tests for the Query Validity (VA) scorer.

No database is touched: VA stops at the pre-execution gate. The tests need the
built source cards (like the golden suites read data/source_cards/*.json); they
skip when those are absent, mirroring the live-suite skip pattern.
"""

from __future__ import annotations

import os

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.score_validity import (
    GateOutcome,
    build_specialists,
    gate_task,
    score_source,
    score_validity,
)

_CARDS_READY = os.path.exists("data/source_cards/attack.json") and os.path.exists(
    "data/source_cards/capec.json"
)
requires_cards = pytest.mark.skipif(_CARDS_READY is False, reason="source cards not built")


@pytest.fixture(scope="module")
def specialists():
    return build_specialists()


@requires_cards
def test_va_is_at_ceiling_for_deterministic_builder(specialists) -> None:
    report = score_validity()
    assert set(report) == {"attack", "capec"}
    for source in ("attack", "capec"):
        overall = report[source]["overall"]
        # The deterministic builder never free-generates, so every drafted query
        # clears the gate — VA at the ceiling is the headline safety property.
        assert overall["first_pass_va"]["rate"] == 1.0
        assert overall["post_retry_va"]["rate"] == 1.0
        assert overall["first_pass_va"]["n"] > 0


@requires_cards
def test_va_reports_tiers_and_cis(specialists) -> None:
    report = score_validity()
    tiers = report["attack"]["by_tier"]
    assert {"easy", "medium", "adversarial"} <= set(tiers)
    fp = report["attack"]["overall"]["first_pass_va"]
    assert 0.0 <= fp["ci_low"] <= fp["rate"] <= fp["ci_high"] <= 1.0


@requires_cards
def test_boundary_questions_excluded_from_denominator(specialists) -> None:
    # The two Asset questions draft no query — counted as boundary, not VA.
    attack = score_validity()["attack"]
    assert attack["overall"]["first_pass_va"]["n"] == 44  # 46 bank - 2 boundary
    assert attack["by_tier"]["adversarial"]["boundary"] == 2


@requires_cards
def test_gate_task_boundary_vs_normal(specialists) -> None:
    attack = specialists["attack"]
    # A normal technique->mitigations task drafts a query that clears the gate.
    normal = SpecialistTask.from_dict({
        "sub_question_id": "t", "source": "attack",
        "text": "mitigations for T1047", "entities": ["Technique", "Mitigation"],
        "limits": {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000},
        "seed_ids": ["T1047"],
    })
    out = gate_task(attack, normal)
    assert isinstance(out, GateOutcome)
    assert not out.boundary and out.final_ok and out.first_pass_ok
    assert out.query and out.attempts == 1

    # An Asset entity is not modeled by Enterprise ATT&CK — boundary, no query.
    boundary = SpecialistTask.from_dict({
        "sub_question_id": "t2", "source": "attack",
        "text": "which assets are affected by T1047", "entities": ["Asset", "Technique"],
        "limits": {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000},
        "seed_ids": ["T1047"],
    })
    out2 = gate_task(attack, boundary)
    assert out2.boundary and not out2.final_ok and out2.query == ""


@requires_cards
def test_score_source_shape(specialists) -> None:
    from utils.specialists.evalset.compile_banks import CAPEC_BANK_PATH, load_bank

    questions = load_bank(CAPEC_BANK_PATH)["questions"]
    rep = score_source(specialists["capec"], questions)
    assert "overall" in rep and "by_tier" in rep
    assert rep["overall"]["first_pass_va"]["n"] == len(questions)  # capec has no boundary Qs
