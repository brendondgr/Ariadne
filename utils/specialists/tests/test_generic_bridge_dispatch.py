"""The generic Gremlin path chooses the cross-source bridge by seed origin, not vocabulary (EXP-2026-09-026).

Three shapes the template cascade answers and the generic path lost:

* a **reverse mapping** — a seed no label of this source admits ("which
  CAPEC items line up with T1040") is a join-key value, and the bridge's
  reverse shape is the only query that can answer it;
* a **paraphrased mapping** — a joined sub-question that names no native
  relation ("which ATT&CK techniques correspond to CAPEC-555") must project
  the key for its consumer, whatever verb the analyst used;
* a **native walk** — a joined sub-question that names a native relation on
  a native seed keeps walking it; the bridge is not forced on it.
"""

from __future__ import annotations

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card

_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}


def _task(text: str, entities: tuple[str, ...], seeds: tuple[str, ...]) -> SpecialistTask:
    return SpecialistTask(sub_question_id="q2", source="capec", text=text, entities=entities,
                          limits=_LIMITS, seed_ids=seeds, join_key="attack-technique-id")


@pytest.fixture(autouse=True)
def generic_only(monkeypatch):
    monkeypatch.setenv("SPECIALIST_GENERIC_ONLY", "true")
    monkeypatch.setenv("ARIADNE_EXACT_NAME_DISTINCT", "1")


def test_a_foreign_seed_takes_the_reverse_bridge():
    task = _task("In capec, identify AlternateTerm relevant to: Which CAPEC items line up with T1040?",
                 ("AlternateTerm",), ("T1040",))
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template == "generic_bridge"
    assert "entryIds" in draft.params and draft.params["entryIds"] == ["1040"]
    # the reverse walk lands on the label that owns the mapping edge, not on the plan's entity
    assert 'hasLabel("AttackPattern").as("ap")' in draft.query and "AlternateTerm" not in draft.query


def test_a_paraphrased_mapping_with_no_native_relation_takes_the_bridge():
    task = _task("In capec, identify AttackPattern relevant to: Which ATT&CK techniques correspond to CAPEC-555?",
                 ("AttackPattern",), ("CAPEC-555",))
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template == "generic_bridge"
    assert "MAPS_TO" in draft.query


def test_a_native_relation_on_a_native_seed_still_walks():
    task = _task("In capec, identify AttackPattern, ChildOf relevant to: which patterns is CAPEC-98 a child of?",
                 ("AttackPattern", "ChildOf"), ("CAPEC-98",))
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template != "generic_bridge"
