#!/usr/bin/env python3
"""Synthesis golden suite — the Step 5 banks through specialist + synthesis.

Every bank question runs through the real specialist against the live stack,
the result is bundled as ``FederatedEvidence``, and the synthesis agent's
verified answer is checked at the *answer* layer:

- every rendered claim is verified-supported (unsupported-claim rate == 0),
- non-empty questions produce at least one cited claim,
- every ``expect_empty`` negative produces an abstention that carries the
  executed query as proof — and no claims at all,
- every ``expect_boundary`` negative (Step 7: e.g. ICS-only Assets) produces a
  boundary abstention — no claims, no invented query proof, the statement
  naming what the source doesn't model.

This measures the goals.md synthesis metrics (faithfulness, groundedness,
unsupported-claim rate) over the same AI-verified questions that gate the
specialists (53 as of Step 7). Skips when the live stack is unreachable.
"""

from __future__ import annotations

import json
import os

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize

_ATTACK_QUESTIONS = load_bank(ATTACK_BANK_PATH)["questions"]
_CAPEC_QUESTIONS = load_bank(CAPEC_BANK_PATH)["questions"]


@pytest.fixture(scope="module")
def attack_specialist():
    from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable

    if not _neo4j_reachable():
        pytest.skip("Neo4j is not reachable — skipping synthesis golden suite")

    from utils.config import load_env
    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig
    from utils.specialists.cypher.specialist import build_cypher_specialist

    load_env()
    with open("data/source_cards/attack.json") as f:
        card = SourceCardView.from_card_dict(json.load(f))
    return build_cypher_specialist(card, SpecialistConfig.from_env())


@pytest.fixture(scope="module")
def capec_specialist():
    from utils.config import load_env

    load_env()
    from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

    uri = os.environ.get("GREMLIN_URI", "ws://localhost:6455/gremlin")
    if not _gremlin_reachable(uri):
        pytest.skip(f"Gremlin not reachable at {uri} — skipping synthesis golden suite")

    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig
    from utils.specialists.gremlin.specialist import build_gremlin_specialist

    with open("data/source_cards/capec.json") as f:
        card = SourceCardView.from_card_dict(json.load(f))
    return build_gremlin_specialist(card, SpecialistConfig.from_env())


def _synthesize_entry(specialist, entry: dict):
    task = SpecialistTask.from_dict(entry["task"])
    result = specialist.run(task)
    evidence = FederatedEvidence(request=entry["question"], results=[result])
    answer = synthesize(evidence, SynthesisConfig())  # deterministic path
    return result, answer


def _check_answer(entry: dict, result, answer) -> list[str]:
    problems: list[str] = []
    report = answer.verification
    assert report is not None  # synthesize always verifies

    for claim, verdict in answer.flagged_claims():
        problems.append(f"unsupported claim survived drafting: {claim.text!r} — {verdict.reasons}")
    if report.unsupported_claim_rate != 0.0:
        problems.append(f"unsupported-claim rate {report.unsupported_claim_rate:.0%} != 0%")

    if entry["assertions"].get("expect_boundary"):
        # Honest schema-boundary refusal: abstain without inventing proof.
        if answer.claims:
            problems.append(f"expected boundary abstention, got {len(answer.claims)} claim(s)")
        if len(answer.abstentions) != 1:
            problems.append(f"expected 1 abstention, got {len(answer.abstentions)}")
        else:
            abst = answer.abstentions[0]
            if abst.query:
                problems.append(f"boundary abstention invented a query proof: {abst.query!r}")
            if "doesn't establish" not in abst.statement:
                problems.append(f"abstention statement not honest-form: {abst.statement!r}")
            if "no query was executed" not in abst.statement:
                problems.append(f"statement does not name the boundary: {abst.statement!r}")
        return problems

    if entry["assertions"].get("expect_empty"):
        if answer.claims:
            problems.append(f"expected pure abstention, got {len(answer.claims)} claim(s)")
        if len(answer.abstentions) != 1:
            problems.append(f"expected 1 abstention, got {len(answer.abstentions)}")
        else:
            abst = answer.abstentions[0]
            if not abst.query:
                problems.append("abstention carries no executed query as proof")
            elif abst.query != result.query:
                problems.append(
                    f"abstention query {abst.query!r} is not the executed query {result.query!r}"
                )
            if "doesn't establish" not in abst.statement:
                problems.append(f"abstention statement not honest-form: {abst.statement!r}")
    else:
        rendered = answer.rendered_claims()
        if not rendered:
            problems.append("no rendered claims for a non-empty question")
        for claim in rendered:
            if not claim.citations:
                problems.append(f"rendered claim without citations: {claim.text!r}")
        if answer.abstentions:
            problems.append(f"unexpected abstention(s): {[a.statement for a in answer.abstentions]}")
        if report.repaired_abstentions:
            problems.append(
                f"deterministic composer needed {report.repaired_abstentions} abstention repair(s)"
            )
    return problems


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("entry", _ATTACK_QUESTIONS, ids=lambda e: f"synth-{e['id']}")
def test_synthesis_golden_attack(attack_specialist, entry: dict) -> None:
    result, answer = _synthesize_entry(attack_specialist, entry)
    problems = _check_answer(entry, result, answer)
    assert not problems, (
        f"{entry['id']} ({entry['question']}):\n  query: {result.query}\n  - "
        + "\n  - ".join(problems)
    )


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("entry", _CAPEC_QUESTIONS, ids=lambda e: f"synth-{e['id']}")
def test_synthesis_golden_capec(capec_specialist, entry: dict) -> None:
    result, answer = _synthesize_entry(capec_specialist, entry)
    problems = _check_answer(entry, result, answer)
    assert not problems, (
        f"{entry['id']} ({entry['question']}):\n  query: {result.query}\n  - "
        + "\n  - ".join(problems)
    )
