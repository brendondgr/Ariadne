#!/usr/bin/env python3
"""Golden live suite for the federated bank (Slice A of the 120-question
catalogue).

Each entry's authored sub-questions are assembled into a real planner ``Plan``
and driven through the committed federation path — ``SpecialistRouter`` with
dependency sequencing, join-value harvesting, and ``bundle_evidence`` — then
through deterministic synthesis. The defining check is ``must_correlate``: the
compile-time snapshot intersection must equal the cross-source join values the
LIVE stack produces. Negatives must yield honest empties and dependency
abstentions, partials must keep the answerable side intact, and no entry may
ever fabricate a correlation.

Skips cleanly when either backend is down — federated questions need both.
"""

from __future__ import annotations

import json
import os

import pytest

from utils.planner.schema import JoinDeclaration, Plan, SubQuestion
from utils.specialists.evalset.compile_banks import FEDERATED_BANK_PATH, load_bank
from utils.specialists.tests.golden_runner import check_assertions, check_traces
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

_ENTRIES = load_bank(FEDERATED_BANK_PATH)["questions"]

_JOIN_KEY = "attack-technique-id"
# Authoring-only keys the planner contract does not carry.
_AUTHORING_KEYS = ("expected_template", "seed_from")


@pytest.fixture(scope="module")
def routers():
    from utils.config import load_env

    load_env()
    uri = os.environ.get("GREMLIN_URI", "ws://localhost:6455/gremlin")
    if not _neo4j_reachable() or not _gremlin_reachable(uri):
        pytest.skip("federated golden suite needs BOTH backends live")

    from utils.specialists.config import SpecialistConfig
    from utils.specialists.federation import SpecialistRouter

    config = SpecialistConfig.from_env()
    full = SpecialistRouter(config)
    return {
        None: full,
        "boundary": full,
        "attack_down": SpecialistRouter(
            config, cards=full.cards, specialists={"attack": None}
        ),
        "capec_down": SpecialistRouter(
            config, cards=full.cards, specialists={"capec": None}
        ),
    }


def _build_plan(entry: dict) -> Plan:
    subs = []
    for sub in entry["sub_questions"]:
        data = {k: v for k, v in sub.items() if k not in _AUTHORING_KEYS}
        subs.append(SubQuestion.from_dict(data))
    joins = []
    if entry["sequenced"]:
        joins.append(
            JoinDeclaration.from_dict(
                {"key": _JOIN_KEY, "sources": ["capec", "attack"], "on": _JOIN_KEY}
            )
        )
    return Plan(request=entry["question"], sub_questions=subs, joins=joins)


def _check_side(entry: dict, source: str, evidence) -> list[str]:
    """Apply one side's assertion block, including the federated-only keys."""
    problems: list[str] = []
    block = entry["assertions"][source]
    sub_id = next(s["id"] for s in entry["sub_questions"] if s["source"] == source)
    by_id = {r.task.sub_question_id: r for r in evidence.results}
    result = by_id.get(sub_id)

    if block.get("expect_skipped"):
        skipped_ids = {s["sub_question"] for s in evidence.skipped}
        if sub_id not in skipped_ids:
            problems.append(f"{source}/{sub_id}: expected skip, not in skipped list")
        if result is not None:
            problems.append(f"{source}/{sub_id}: expected skip but a result exists")
        return problems

    if result is None:
        return [f"{source}/{sub_id}: no result and no skip expectation"]

    if block.get("expect_dependency_skip"):
        if not result.ok:
            problems.append(f"{source}/{sub_id}: dependency skip must stay ok")
        if result.records:
            problems.append(
                f"{source}/{sub_id}: dependency skip returned {len(result.records)} records"
            )
        if result.query:
            problems.append(
                f"{source}/{sub_id}: dependency skip must not execute a query "
                f"(got {result.query!r})"
            )
        seq = [s for s in evidence.sequencing if s["consumer"] == sub_id]
        if not (seq and seq[0]["skipped"]):
            problems.append(f"{source}/{sub_id}: no sequencing skip reason recorded")
        return problems

    problems.extend(f"{source}: {p}" for p in check_assertions(result, block))
    problems.extend(f"{source} trace: {p}" for p in check_traces(result, block))
    return problems


def _check_correlation(entry: dict, evidence) -> list[str]:
    problems: list[str] = []
    asserts = entry["assertions"]
    live_join = evidence.cross_source_join_values()
    if asserts.get("expect_no_correlation"):
        if live_join:
            problems.append(
                f"fabricated correlation: expected NO cross-source join values, "
                f"got {live_join}"
            )
        return problems
    want = sorted(asserts["must_correlate"])
    if live_join != want:
        problems.append(
            f"correlation mismatch: live {live_join} != snapshot gold {want}"
        )
    return problems


def _check_sequencing(entry: dict, evidence) -> list[str]:
    problems: list[str] = []
    if not entry["sequenced"] or entry["partial_mode"] == "attack_down":
        # attack_down: the consumer's specialist is absent, so the skip is
        # recorded in evidence.skipped before sequencing is ever reached.
        if evidence.sequencing:
            problems.append(f"unexpected sequencing rows: {evidence.sequencing}")
        return problems
    if len(evidence.sequencing) != 1:
        return [f"expected exactly 1 sequencing row, got {evidence.sequencing}"]
    row = evidence.sequencing[0]
    if row["consumer"] != "q2" or row["producer"] != "q1":
        problems.append(f"sequencing row misdirected: {row}")
    asserts = entry["assertions"]
    if asserts.get("expect_no_correlation"):
        if row["skipped"] is None and entry["partial_mode"] is None:
            problems.append(
                f"negative entry seeded its consumer anyway: {row} — the join "
                f"must degrade to a dependency abstention"
            )
    elif row["skipped"] is not None:
        problems.append(f"positive entry skipped its consumer: {row}")
    elif row["seed_count"] < len(asserts["must_correlate"]):
        problems.append(
            f"seed_count {row['seed_count']} < |must_correlate| "
            f"{len(asserts['must_correlate'])}"
        )
    return problems


def _check_synthesis(entry: dict, evidence) -> list[str]:
    from utils.synthesis.config import SynthesisConfig
    from utils.synthesis.factory import synthesize

    problems: list[str] = []
    answer = synthesize(evidence, SynthesisConfig())
    report = answer.verification
    if report.unsupported_claim_rate != 0.0:
        problems.append(
            f"unsupported-claim rate {report.unsupported_claim_rate:.0%} != 0%"
        )
    for claim, verdict in answer.flagged_claims():
        problems.append(f"unsupported claim survived: {claim.text!r} — {verdict.reasons}")

    mode = entry["partial_mode"]
    negative = entry["assertions"].get("expect_no_correlation", False)

    if not negative:
        rendered = answer.rendered_claims()
        if not rendered:
            problems.append("no rendered claims for a positive federated question")
        for claim in rendered:
            if not claim.citations:
                problems.append(f"rendered claim without citations: {claim.text!r}")
        if answer.abstentions:
            problems.append(
                f"unexpected abstentions: {[a.statement for a in answer.abstentions]}"
            )
        return problems

    if mode is None:  # F-NEG: double abstention — query proof on capec, none on attack
        if answer.claims:
            problems.append(f"negative produced {len(answer.claims)} claim(s)")
        if len(answer.abstentions) != 2:
            problems.append(f"expected 2 abstentions, got {len(answer.abstentions)}")
        else:
            with_query = [a for a in answer.abstentions if a.query]
            without = [a for a in answer.abstentions if not a.query]
            if len(with_query) != 1 or len(without) != 1:
                problems.append(
                    "expected exactly one query-proof abstention (producer) and one "
                    "no-query abstention (consumer)"
                )
            else:
                capec_result = next(
                    r for r in evidence.results if r.task.source == "capec"
                )
                if with_query[0].query != capec_result.query:
                    problems.append(
                        "producer abstention proof is not the executed query"
                    )
        return problems

    if mode == "boundary":
        rendered = answer.rendered_claims()
        if not rendered:
            problems.append("boundary partial lost its answerable (capec) side")
        if len(answer.abstentions) != 1:
            problems.append(f"expected 1 boundary abstention, got {len(answer.abstentions)}")
        elif answer.abstentions[0].query:
            problems.append("boundary abstention invented a query proof")
        return problems

    if mode == "attack_down":
        rendered = answer.rendered_claims()
        if not rendered:
            problems.append("attack-down partial lost its answerable (capec) side")
        return problems

    if mode == "capec_down":
        if answer.claims:
            problems.append("capec-down partial fabricated claims with no source")
        for abst in answer.abstentions:
            if abst.query:
                problems.append(
                    f"no query ever executed, yet an abstention carries one: {abst.query!r}"
                )
        return problems

    return [f"unknown partial_mode {mode!r}"]


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("entry", _ENTRIES, ids=lambda e: e["id"])
def test_golden_federated_question(routers, entry: dict) -> None:
    router = routers[entry["partial_mode"]]
    plan = _build_plan(entry)
    evidence = router.run_plan(plan)

    problems: list[str] = []
    problems.extend(_check_correlation(entry, evidence))
    problems.extend(_check_sequencing(entry, evidence))
    for source in ("capec", "attack"):
        problems.extend(_check_side(entry, source, evidence))
    if entry["assertions"].get("expect_partial"):
        if not evidence.partial:
            problems.append("expected partial evidence bundle")
    problems.extend(_check_synthesis(entry, evidence))

    assert not problems, f"{entry['id']}: " + "; ".join(problems)
