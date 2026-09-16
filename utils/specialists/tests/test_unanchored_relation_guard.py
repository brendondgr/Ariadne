"""A relation template with no anchor abstains instead of scanning (EXP-2026-09-023, Step 3).

Off by default (``ARIADNE_UNANCHORED_RELATION_ABSTAINS``), so the shipped
baseline reproduces byte for byte; the ``hygiene`` harness arm turns it on
with the exact-name rule, because the false anchor that rule removes is what
used to keep these questions off the seedless branch.
"""

from __future__ import annotations

import pytest

from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.builder import CypherQueryBuilder
from utils.specialists.gremlin.builder import GremlinQueryBuilder
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card

_LIMITS = {"max_traversal_depth": 3, "max_result_rows": 300, "query_timeout_ms": 5000}


def _task(source: str, text: str, entities: tuple[str, ...], seeds: tuple[str, ...] = (), **kw) -> SpecialistTask:
    return SpecialistTask(sub_question_id="q1", source=source, text=text, entities=entities,
                          limits=_LIMITS, seed_ids=seeds, **kw)


@pytest.fixture
def guard_on(monkeypatch):
    """The ``hygiene`` arm: the guard *and* the exact-name rule.

    They travel together on purpose. With the rule off, "come after
    persistence" binds the tactic named "Persistence" through the builder's own
    exact-name seeding, the task is no longer seedless, and the guard never
    sees it — which is the false anchor that hid these scans in the first place.
    """
    monkeypatch.setenv("ARIADNE_UNANCHORED_RELATION_ABSTAINS", "1")
    monkeypatch.setenv("ARIADNE_EXACT_NAME_DISTINCT", "1")
    monkeypatch.setenv("ARIADNE_LEXICON", "1")


# -- cypher --------------------------------------------------------------------

def test_a_seedless_group_technique_task_scans_by_default(monkeypatch):
    monkeypatch.delenv("ARIADNE_UNANCHORED_RELATION_ABSTAINS", raising=False)
    task = _task("attack", "which behaviours does the crew behind the botnet rely on", ("Group", "USES", "Technique"))
    draft = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    assert draft.template == "group_techniques" and "IN $ids" not in draft.query


def test_a_seedless_group_technique_task_abstains_under_the_guard(guard_on):
    task = _task("attack", "which behaviours does the crew behind the botnet rely on", ("Group", "USES", "Technique"))
    draft = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    assert draft.template == "unanchored"


def test_a_seeded_group_technique_task_is_untouched(guard_on):
    task = _task("attack", "which techniques does G0016 use", ("Group", "USES", "Technique"), seeds=("G0016",))
    draft = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    assert draft.template == "group_techniques" and "$ids" in draft.query


def test_an_explicit_bulk_scan_still_scans(guard_on):
    task = _task("attack", "List every ATT&CK group and the techniques each uses.", ("Group", "USES", "Technique"))
    draft = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    assert draft.template != "unanchored"


def test_a_seedless_tactic_technique_task_abstains_under_the_guard(guard_on):
    task = _task("attack", "which low-likelihood behaviours tend to come after persistence", ("Tactic", "HAS_TECHNIQUE", "Technique"))
    draft = CypherQueryBuilder().build(resolve(task, fixture_card("attack")))
    # Not the 222-row tactic→technique scan. With the rule on, "persistence"
    # (lower case) no longer binds the tactic, and the hyphenated token
    # "low-likelihood" is read as a name term, so the task lands on the
    # bounded describe-by-name lookup — which finds nothing and abstains.
    assert draft.template in {"unanchored", "describe_by_name"}


# -- gremlin -------------------------------------------------------------------

def test_a_seedless_unscoped_bridge_abstains_under_the_guard(guard_on):
    task = _task("capec", "which broader items cover capturing from a target's microphone",
                 ("AttackPattern", "MAPS_TO", "TaxonomyEntry"), join_key="attack-technique-id")
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template == "unanchored"


def test_a_concept_scoped_bridge_is_not_a_scan_and_survives(guard_on):
    task = _task("capec", "find credential theft patterns and mapped ATT&CK ids",
                 ("AttackPattern", "MAPS_TO", "TaxonomyEntry"), join_key="attack-technique-id")
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template == "capec_maps_to" and "TextP.regex" in draft.query


def test_a_seeded_bridge_is_untouched(guard_on):
    task = _task("capec", "which ATT&CK techniques does CAPEC-98 map to",
                 ("AttackPattern", "MAPS_TO", "TaxonomyEntry"), seeds=("CAPEC-98",), join_key="attack-technique-id")
    draft = GremlinQueryBuilder().build(resolve(task, fixture_card("capec")))
    assert draft.template == "capec_maps_to" and "within(ids)" in draft.query
