#!/usr/bin/env python3

from __future__ import annotations

import pytest

from utils.planner.cards import load_source_cards
from utils.planner.evaluation.corpus import ExpectedCase, load_corpus, run_case, run_corpus
from utils.planner.evaluation.scorer import aggregate, score_plan
from utils.planner.schema import Limits, Plan, SubQuestion, UnsupportedPart
from utils.planner.tests._fixtures import load_fixture_cards, make_live_view

# Minimal committed fixtures for pure scorer-logic tests (hermetic).
CARDS = load_fixture_cards()

# The generated corpus is derived against the real data cards (richer vocabulary
# than the fixtures — e.g. Campaign), so corpus-regression tests score against
# those. Skip when they are not built, mirroring the live-suite skip pattern.
try:
    DATA_CARDS = load_source_cards("data")
except Exception:  # pragma: no cover - defensive
    DATA_CARDS = {}
_DATA_CARDS_READY = bool(DATA_CARDS) and "Campaign" in DATA_CARDS.get(
    "attack", load_fixture_cards()["attack"]
).node_labels
requires_data_cards = pytest.mark.skipif(
    not _DATA_CARDS_READY, reason="real data source cards not built — run --build"
)


# -- corpus loading ---------------------------------------------------------


def test_corpus_loads_with_both_splits_and_edge_cases() -> None:
    cases = load_corpus()
    # curated anchors + generated cases from the specialist banks
    assert len(cases) >= 25
    splits = {c.split for c in cases}
    assert {"dev", "holdout"} <= splits
    origins = {c.origin for c in cases}
    assert {"curated", "generated"} <= origins
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


# -- sub-question-quality decomposition -------------------------------------


def test_decomposition_rewards_correct_routing_count_dependency() -> None:
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "x", ["AttackPattern", "MAPS_TO"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(), CARDS, make_live_view())
    assert score.count_correct and score.routing_correct and score.dependency_correct
    assert score.decomposition_score == 1.0
    assert score.sub_question_count == 1
    assert score.expected_sub_question_count == 1  # defaults to len(expected_sources)
    assert score.sub_question_quality == 1.0


def test_decomposition_flags_wrong_routing() -> None:
    # routes to attack when only capec was expected
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "attack", "x", ["Technique"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(expected_sources=["capec"]), CARDS, make_live_view())
    assert not score.routing_correct
    assert score.decomposition_score < 1.0


def test_decomposition_flags_wrong_count_override() -> None:
    # one sub-question emitted but the case demands two
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "x", ["AttackPattern", "MAPS_TO"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(expected_sub_question_count=2), CARDS, make_live_view())
    assert not score.count_correct
    assert score.expected_sub_question_count == 2


def test_decomposition_flags_missing_multihop_dependency() -> None:
    # multi-hop question but the plan declared no join
    plan = Plan(
        request="r",
        sub_questions=[SubQuestion("q1", "capec", "x", ["AttackPattern", "MAPS_TO"], Limits(3, 1000, 5000))],
    )
    score = score_plan(plan, _case(expects_join=True), CARDS, make_live_view())
    assert not score.dependency_correct


def test_aggregate_reports_decomposition_metrics() -> None:
    # Shape test (hermetic, fixture cards): the new keys exist and are rates.
    results = run_corpus(CARDS)
    agg = aggregate([s for _c, _p, s in results])
    for key in (
        "mean_sub_question_quality",
        "mean_decomposition_score",
        "routing_accuracy_rate",
        "count_accuracy_rate",
        "dependency_accuracy_rate",
    ):
        assert key in agg
        assert 0.0 <= agg[key] <= 1.0


def test_expected_sub_question_count_roundtrips_through_dict() -> None:
    case = ExpectedCase.from_dict(
        {"name": "n", "request": "r", "expected_sources": ["capec"],
         "expected_sub_question_count": 3}
    )
    assert case.expected_sub_question_count == 3
    # absent -> None (scorer then defaults to len(expected_sources))
    case2 = ExpectedCase.from_dict({"name": "n", "request": "r", "expected_sources": ["capec"]})
    assert case2.expected_sub_question_count is None


# -- corpus regression ------------------------------------------------------


@requires_data_cards
def test_deterministic_agent_holds_hard_guarantees_corpuswide() -> None:
    results = run_corpus(DATA_CARDS)
    scores = [s for _c, _p, s in results]
    agg = aggregate(scores)
    # Hard guarantees hold across the whole expanded corpus by construction:
    # generated cases are only included when the gold source is selected and the
    # plan is schema-valid, and every case's honesty flags are right.
    assert agg["schema_adherence_rate"] == 1.0, [s.to_dict() for s in scores if not s.schema_adherent]
    assert agg["mean_source_recall"] == 1.0, [s.to_dict() for s in scores if s.source_recall < 1.0]
    assert agg["honesty_rate"] == 1.0
    # Sanity floor so a real routing regression trips, while honest precision /
    # entity-recall misses on the harder generated cases are reported, not gated.
    assert agg["pass_rate"] >= 0.6, [s.to_dict() for s in scores if not s.passed]


@requires_data_cards
def test_curated_anchors_all_pass() -> None:
    # The 7 hand-reviewed anchors are the strict regression: every one passes.
    results = run_corpus(DATA_CARDS)
    curated = [s for _c, _p, s in results if s.origin == "curated"]
    assert len(curated) >= 7
    for score in curated:
        assert score.passed, score.to_dict()


@requires_data_cards
def test_holdout_split_runs_and_holds_guarantees() -> None:
    results = run_corpus(DATA_CARDS, split="holdout")
    assert results, "no holdout cases"
    for _case, _plan, score in results:
        assert score.schema_adherent
        assert score.source_recall == 1.0, score.to_dict()
        assert score.unsupported_correct and score.partial_correct
        if score.origin == "curated":
            assert score.passed, score.to_dict()


@requires_data_cards
def test_generated_corpus_matches_committed() -> None:
    # Regenerating from the specialist banks reproduces exactly the committed
    # generated cases — the corpus is snapshot-derived, never hand-edited.
    from utils.planner.evaluation import build_corpus

    kept, _excluded = build_corpus.generate()
    committed = {
        p.name: __import__("json").loads(p.read_text(encoding="utf-8"))
        for p in build_corpus.GENERATED_DIR.glob("*.json")
    }
    regenerated = {f"{c['name']}.json": c for c in kept}
    assert set(regenerated) == set(committed), "generated file set drifted from committed"
    for name, case in regenerated.items():
        assert case == committed[name], f"{name} regenerated differently"


@requires_data_cards
def test_intent_is_scored_and_accurate_corpuswide() -> None:
    # Planner step one is measured: intent accuracy is reported, the classified
    # intent matches the independent template/curated ground truth on the vast
    # majority of cases, and every curated anchor that declares an intent is
    # classified correctly.
    scores = [s for _c, _p, s in run_corpus(DATA_CARDS)]
    agg = aggregate(scores)
    assert agg["intent_scored_cases"] >= 40
    assert agg["intent_accuracy_rate"] is not None and agg["intent_accuracy_rate"] >= 0.9
    curated = [s for s in scores if s.origin == "curated" and s.expected_intent]
    assert curated and all(s.intent_correct for s in curated), [
        s.to_dict() for s in curated if not s.intent_correct
    ]


def test_intent_accuracy_none_when_no_cases_scored() -> None:
    # A corpus with no expected_intent reports None, not a divide-by-zero.
    case = ExpectedCase(name="x", request="q", live=["capec"], expected_sources=["capec"])
    plan = Plan(request="q")
    score = score_plan(plan, case, CARDS, make_live_view())
    assert score.intent_correct  # unscored counts as correct (never drags pass)
    assert aggregate([score])["intent_accuracy_rate"] is None


def test_run_case_returns_plan_and_score() -> None:
    case = load_corpus("dev")[0]
    plan, score = run_case(case, CARDS)
    assert plan.request == case.request
    assert score.name == case.name
