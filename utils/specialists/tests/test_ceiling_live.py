"""Era 2 Step 5, live: a result cut at its row ceiling comes back partial, with a ceiling trace."""

from __future__ import annotations

import json

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable

pytestmark = [pytest.mark.live, pytest.mark.integration]


@pytest.fixture(scope="module")
def attack():
    if not _neo4j_reachable():
        pytest.skip("Neo4j is not reachable")
    from utils.config import load_env
    from utils.planner.cards import SourceCardView
    from utils.specialists.config import SpecialistConfig
    from utils.specialists.cypher.specialist import build_cypher_specialist

    load_env()
    with open("data/source_cards/attack.json") as f:
        card = SourceCardView.from_card_dict(json.load(f))
    return build_cypher_specialist(card, SpecialistConfig.from_env())


def _task(rows: int) -> SpecialistTask:
    return SpecialistTask(sub_question_id="q1", source="attack",
                          text="Which techniques does the group APT29 (G0016) use?",
                          entities=("Group", "USES", "Technique"), seed_ids=("G0016",),
                          limits={"max_result_rows": rows, "max_traversal_depth": 3})


def _ceiling(result):
    return [t for t in result.traces if t.step == "ceiling"]


def test_a_small_ceiling_is_reported_not_hidden(attack):
    full = attack.run(_task(20000))
    n = len(full.records)
    assert n > 5 and not _ceiling(full)
    cut = attack.run(_task(5))
    assert cut.partial and _ceiling(cut)
    assert _ceiling(cut)[0].detail["row_ceiling"] == 5
    execute = [t for t in cut.traces if t.step == "execute"][0]
    assert execute.detail["truncated"] is True


def test_a_ceiling_the_result_fits_inside_is_not_partial(attack):
    full = attack.run(_task(20000))
    rows = [t for t in full.traces if t.step == "execute"][0].detail["row_count"]
    exact = attack.run(_task(rows))             # the result fills the ceiling exactly: probed, complete
    assert not _ceiling(exact) and [t for t in exact.traces if t.step == "execute"][0].detail["truncated"] is False
