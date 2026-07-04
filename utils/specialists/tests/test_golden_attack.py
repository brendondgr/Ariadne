#!/usr/bin/env python3
"""Golden live suite — every attack-bank question through the real Cypher
specialist against live Neo4j. Skips when the stack is unreachable."""

from __future__ import annotations

import json

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.specialist import build_cypher_specialist
from utils.specialists.evalset.compile_banks import ATTACK_BANK_PATH, load_bank
from utils.specialists.tests.golden_runner import check_assertions, check_traces
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable

_QUESTIONS = load_bank(ATTACK_BANK_PATH)["questions"]


@pytest.fixture(scope="module")
def live_specialist():
    if not _neo4j_reachable():
        pytest.skip("Neo4j is not reachable — skipping golden attack suite")

    from utils.config import load_env
    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig

    load_env()
    with open("data/source_cards/attack.json") as f:
        card = SourceCardView.from_card_dict(json.load(f))
    return build_cypher_specialist(card, SpecialistConfig.from_env())


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("entry", _QUESTIONS, ids=lambda e: e["id"])
def test_golden_attack_question(live_specialist, entry: dict) -> None:
    task = SpecialistTask.from_dict(entry["task"])
    result = live_specialist.run(task)

    problems = check_assertions(result, entry["assertions"])
    problems.extend(check_traces(result, entry["assertions"]))
    assert not problems, (
        f"{entry['id']} ({entry['question']}):\n  query: {result.query}\n  - "
        + "\n  - ".join(problems)
    )
