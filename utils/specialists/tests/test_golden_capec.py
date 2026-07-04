#!/usr/bin/env python3
"""Golden live suite — every capec-bank question through the real Gremlin
specialist against the live Gremlin server. Skips when unreachable."""

from __future__ import annotations

import json
import os

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.compile_banks import CAPEC_BANK_PATH, load_bank
from utils.specialists.gremlin.specialist import build_gremlin_specialist
from utils.specialists.tests.golden_runner import check_assertions, check_traces
from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

_QUESTIONS = load_bank(CAPEC_BANK_PATH)["questions"]


@pytest.fixture(scope="module")
def live_specialist():
    from utils.config import load_env

    load_env()
    uri = os.environ.get("GREMLIN_URI", "ws://localhost:6455/gremlin")
    if not _gremlin_reachable(uri):
        pytest.skip(f"Gremlin not reachable at {uri} — skipping golden capec suite")

    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig

    with open("data/source_cards/capec.json") as f:
        card = SourceCardView.from_card_dict(json.load(f))
    return build_gremlin_specialist(card, SpecialistConfig.from_env())


@pytest.mark.live
@pytest.mark.integration
@pytest.mark.parametrize("entry", _QUESTIONS, ids=lambda e: e["id"])
def test_golden_capec_question(live_specialist, entry: dict) -> None:
    task = SpecialistTask.from_dict(entry["task"])
    result = live_specialist.run(task)

    problems = check_assertions(result, entry["assertions"])
    problems.extend(check_traces(result, entry["assertions"]))
    assert not problems, (
        f"{entry['id']} ({entry['question']}):\n  query: {result.query}\n  - "
        + "\n  - ".join(problems)
    )
