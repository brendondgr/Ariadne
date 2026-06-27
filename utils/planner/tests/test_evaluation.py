#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.evaluation.corpus import ExpectedCase, load_corpus, run_case, run_corpus
from utils.planner.evaluation.scorer import aggregate, score_plan
from utils.planner.schema import Limits, Plan, SubQuestion, UnsupportedPart
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

CARDS = load_fixture_cards()


# -- corpus loading ---------------------------------------------------------


def test_corpus_loads_with_both_splits_and_edge_cases() -> None:
    cases = load_corpus()
    assert len(cases) >= 6
    splits = {c.split for c in cases}
    assert {"dev", "holdout"} <= splits
    # out-of-scope and down-source cases are present (mark-unsupported coverage)
    assert any(c.expects_unsupported and not c.live or c.name == "out_of_scope_k8s" for c in cases)
    assert any(c.expects_partial for c in cases)


# -- scorer behaviour -------------------------------------------------------


def _case(**over) -> ExpectedCase:
    base = dict(
        name="t", request="r", live=["attack", "capec"], expected_sources=["capec"],
        expected_entities={"capec": ["AttackPattern", "MAPS_TO"]},
        expects_join=False, expects_unsupported=False, expects_partial=False, split="dev",
    )
    base.update(over)
    return ExpectedCase(**base)  # type: ignore[arg-type]


def test_scorer_rewards_correct_plan() -> None:
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "x", ["AttackPattern", "MAPS_TO"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(), CARDS, make_live_view())
    assert score.source_recall == 1.0
    assert score.entity_recall == 1.0
    assert score.schema_adherent
    assert score.passed


def test_scorer_flags_wrong_source() -> None:
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "attack", "x", ["Technique"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(expected_sources=["capec"]), CARDS, make_live_view())
    assert score.source_recall < 1.0
    assert "capec" in score.missing_sources
    assert not score.passed


def test_scorer_flags_schema_violation() -> None:
    # missing limits ⇒ gate rejects ⇒ not schema-adherent
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "x", ["AttackPattern"], Limits())],
    )
    score = score_plan(plan, _case(), CARDS, make_live_view())
    assert not score.schema_adherent
    assert not score.passed


def test_scorer_counts_unnecessary_calls() -> None:
    plan = Plan(
        request="r",
        sub_questions=[
            SubQuestion("q1", "capec", "x", ["AttackPattern", "MAPS_TO"], Limits(3, 1000, 5000)),
            SubQuestion("q2", "attack", "y", ["Technique"], Limits(3, 1000, 5000)),
        ],
    )
    score = score_plan(plan, _case(expected_sources=["capec"]), CARDS, make_live_view())
    assert score.unnecessary_source_calls == 1  # attack was not expected


def test_scorer_checks_honesty_flags() -> None:
    plan = Plan(request="r", unsupported=[UnsupportedPart("x", "no source")], partial=True)
    score = score_plan(plan, _case(expected_sources=[], expects_unsupported=True, expects_partial=True),
                       CARDS, make_live_view())
    assert score.unsupported_correct and score.partial_correct


# -- corpus regression ------------------------------------------------------


def test_deterministic_agent_passes_corpus_regression() -> None:
    results = run_corpus(CARDS)
    scores = [s for _c, _p, s in results]
    agg = aggregate(scores)
    # hard guarantees: every plan is schema-valid, no needed source missed,
    # and the honesty flags are always right.
    assert agg["schema_adherence_rate"] == 1.0, [s.to_dict() for s in scores if not s.schema_adherent]
    assert agg["mean_source_recall"] == 1.0
    assert agg["honesty_rate"] == 1.0
    # the deterministic drafter clears the corpus pass bar.
    assert agg["pass_rate"] >= 0.85, [s.to_dict() for s in scores if not s.passed]


def test_holdout_split_runs_and_passes() -> None:
    results = run_corpus(CARDS, split="holdout")
    assert results, "no holdout cases"
    for _case, _plan, score in results:
        assert score.schema_adherent
        assert score.passed, score.to_dict()


def test_run_case_returns_plan_and_score() -> None:
    case = load_corpus("dev")[0]
    plan, score = run_case(case, CARDS)
    assert plan.request == case.request
    assert score.name == case.name
