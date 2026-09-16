"""Q59: an entity name is looked up before its dataset is chosen (EXP-2026-09-023, H2).

The fixture cards carry no name index, so the cross-source lookup is supplied
by monkeypatching ``exact_name_matches_all`` / ``exact_name_matches`` with the
hits a real index would return. What is under test is the *ordering* and the
*tie-break* in ``deterministic_fill``, not the matcher.
"""

from __future__ import annotations

import pytest

from utils.planner import canonical
from utils.planner.tests._fixtures import load_fixture_cards
from utils.specialists.schema import namesearch as ns

CARDS = load_fixture_cards()


def _cand(entity_id: str, label: str, name: str) -> ns.Candidate:
    return ns.Candidate(entity_id, label, name, float(len(name.split())))


@pytest.fixture
def names(monkeypatch):
    """Install a fake name index: dataset -> {question substring: candidate}."""
    table: dict[str, list[ns.Candidate]] = {"attack": [], "capec": []}

    def per_dataset(dataset, text, *, labels=None):
        low = " " + " ".join(ns._WORD_RE.findall(text.lower())) + " "  # noqa: SLF001
        return [
            c for c in table.get(dataset, [])
            if f" {' '.join(ns._WORD_RE.findall(c.name.lower()))} " in low  # noqa: SLF001
        ]

    def all_datasets(datasets, text, *, exclude=None):
        out = []
        for ds in datasets:
            for c in per_dataset(ds, text):
                if c.name.lower() in (exclude or {}).get(ds, set()):
                    continue
                out.append((ds, c))
        return out

    monkeypatch.setattr(ns, "exact_name_matches", per_dataset)
    monkeypatch.setattr(ns, "exact_name_matches_all", all_datasets)
    return table


def test_defaults_off_so_an_unrouted_name_stays_unbound(names, monkeypatch):
    monkeypatch.delenv("ARIADNE_ANCHOR_BEFORE_ROUTING", raising=False)
    names["attack"].append(_cand("T1047", "Technique", "Windows Management Instrumentation"))
    form = canonical.deterministic_fill(
        "Which countermeasures apply to Windows Management Instrumentation?", CARDS
    )
    assert canonical.SLOT_ANCHORS in form.unbound
    assert form.sources.get(canonical.SLOT_ANCHORS) is None


def test_a_name_chooses_its_dataset_when_the_router_chose_none(names):
    names["attack"].append(_cand("T1047", "Technique", "Windows Management Instrumentation"))
    form = canonical.deterministic_fill(
        "Which countermeasures apply to Windows Management Instrumentation?", CARDS,
        anchor_first=True,
    )
    assert form.anchors == ("T1047",)
    assert form.sources[canonical.SLOT_ANCHORS] == "exact-name"
    assert form.sources[canonical.SLOT_DATASETS] == "anchor-first"
    assert form.datasets[0] == "attack"


def test_the_router_keeps_its_choice_when_it_already_covers_the_owner(names):
    names["attack"].append(_cand("T1047", "Technique", "Windows Management Instrumentation"))
    form = canonical.deterministic_fill(
        "What mitigations does ATT&CK list for Windows Management Instrumentation?", CARDS,
        anchor_first=True,
    )
    assert form.anchors == ("T1047",)
    assert form.sources[canonical.SLOT_DATASETS] == "router"


def test_the_owner_leads_when_the_router_picked_a_source_that_lacks_the_entity(names):
    names["capec"].append(_cand("CAPEC-639", "AttackPattern", "Probe System Files"))
    form = canonical.deterministic_fill(
        "Which ATT&CK techniques does Probe System Files correspond to?", CARDS,
        anchor_first=True,
    )
    assert form.anchors == ("CAPEC-639",)
    assert form.datasets[0] == "capec"
    assert "attack" in form.datasets, "the routed source is kept behind the owner for the join"
    assert form.sources[canonical.SLOT_DATASETS] == "anchor-first"


def test_the_router_breaks_a_cross_source_collision(names):
    names["attack"].append(_cand("T1566", "Technique", "Phishing"))
    names["capec"].append(_cand("CAPEC-98", "AttackPattern", "Phishing"))
    form = canonical.deterministic_fill(
        "What mitigations does ATT&CK list for Phishing?", CARDS, anchor_first=True,
    )
    assert form.anchors == ("T1566",)
    assert form.sources[canonical.SLOT_DATASETS] == "router"


def test_an_unbroken_collision_is_reported_not_guessed(names):
    # A name that appears in no card gloss, so the router has nothing to say.
    names["attack"].append(_cand("T1999", "Technique", "Gilding"))
    names["capec"].append(_cand("CAPEC-999", "AttackPattern", "Gilding"))
    form = canonical.deterministic_fill("What is Gilding?", CARDS, anchor_first=True)
    assert form.anchors == ()
    assert form.sources[canonical.SLOT_ANCHORS].startswith("ambiguous:")
    assert set(form.datasets) == {"attack", "capec"}
    assert canonical.SLOT_ANCHORS in form.unbound


def test_an_identifier_owner_needs_no_routing_words(names):
    form = canonical.deterministic_fill("Tell me about T1047.", CARDS, anchor_first=True)
    assert form.anchors == ("T1047",)
    assert form.sources[canonical.SLOT_ANCHORS] == "exact-id"
    assert form.datasets[0] == "attack"


def test_the_flag_is_read_from_the_environment(names, monkeypatch):
    names["attack"].append(_cand("T1047", "Technique", "Windows Management Instrumentation"))
    monkeypatch.setenv("ARIADNE_ANCHOR_BEFORE_ROUTING", "1")
    form = canonical.deterministic_fill(
        "Which countermeasures apply to Windows Management Instrumentation?", CARDS
    )
    assert form.anchors == ("T1047",)


def test_config_reads_the_environment_flag(monkeypatch):
    from utils.planner.config import PlannerConfig

    monkeypatch.delenv("ARIADNE_ANCHOR_BEFORE_ROUTING", raising=False)
    assert PlannerConfig.from_env().anchor_before_routing is False
    monkeypatch.setenv("ARIADNE_ANCHOR_BEFORE_ROUTING", "1")
    assert PlannerConfig.from_env().anchor_before_routing is True
