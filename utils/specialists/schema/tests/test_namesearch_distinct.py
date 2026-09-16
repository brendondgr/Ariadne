"""The exact-name matcher's distinctiveness rules and cross-source nesting (EXP-2026-09-023).

Everything here runs on a made-up "library" corpus so the rule is shown to be a
function of the question's own writing and the corpus's own text — no
catalogue word appears in these fixtures. One test at the end touches the real
snapshot to pin the named cases the rule exists for.

Two modes exist. ``df`` is H1, falsified and kept for the record; ``struct``
(selected by ``1``) is AMENDMENT A-1 and the one that ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.specialists.schema import namesearch as ns


def _doc(entity_id: str, name: str, description: str, label: str = "Book"):
    toks = ns._tokens(name) * ns._NAME_WEIGHT + ns._tokens(description)  # noqa: SLF001
    return (entity_id, label, name, toks)


def _library() -> ns.NameIndex:
    # "watch" appears in most descriptions, so a node *named* "Watch" is an
    # ordinary word; "Orrery" appears nowhere else. "Night Watch" is multi-word
    # and never subject to either rule. "at" is shorter than a token.
    docs = [
        _doc("b1", "Night Watch", "A novel about the city watch keeping watch at night."),
        _doc("b2", "Watch", "A field guide to how people watch birds and watch the sky."),
        _doc("b3", "Orrery", "A clockwork model of the planets."),
        _doc("b4", "Day Watch", "The sequel; the watch returns by day."),
        _doc("b5", "Tides", "Why people watch the sea and the moon."),
        _doc("b6", "Almanac", "Tables people watch through the year."),
        _doc("b7", "at", "A tiny book about a tiny word."),
    ]
    return ns.NameIndex(docs)


def _archive() -> ns.NameIndex:
    return ns.NameIndex([
        _doc("a1", "Night Watch Restoration Notes", "Conservation record.", "Record"),
        _doc("a2", "Gilding", "Notes on gold leaf.", "Record"),
        _doc("a3", "Orrery", "The same instrument, catalogued twice.", "Record"),
    ])


@pytest.fixture
def indexes(monkeypatch):
    fixtures = {"library": _library(), "archive": _archive()}
    monkeypatch.setattr(ns, "index_for", lambda ds: fixtures[ds])
    return fixtures


def _mode(monkeypatch, value: str) -> None:
    monkeypatch.setenv("ARIADNE_EXACT_NAME_DISTINCT", value)


def _ids(dataset: str, text: str) -> list[str]:
    return [c.entity_id for c in ns.exact_name_matches(dataset, text)]


# -- default ------------------------------------------------------------------

def test_rules_are_off_by_default_and_an_ordinary_word_binds(indexes, monkeypatch):
    monkeypatch.delenv("ARIADNE_EXACT_NAME_DISTINCT", raising=False)
    assert _ids("library", "what should I watch") == ["b2"]
    assert _ids("library", "look at this") == ["b7"]


# -- struct (A-1, ships) --------------------------------------------------------

def test_struct_a_lower_cased_occurrence_is_a_word_not_a_name(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "what should I watch") == []
    assert _ids("library", "tell me about the orrery") == []


def test_struct_a_standalone_proper_noun_binds(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "tell me about the Orrery") == ["b3"]
    assert _ids("library", "is Watch worth reading") == ["b2"]


def test_struct_sentence_initial_capital_is_not_a_run(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "Orrery models are fun") == ["b3"]
    assert _ids("library", "Browsing Orrery as a starting point") == ["b3"]


def test_struct_a_name_inside_a_longer_capitalised_run_is_part_of_something_else(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "the Orrery Society meets on Tuesdays") == []
    assert _ids("library", "I read Crimson Orrery last week") == []


def test_struct_a_name_shorter_than_a_token_never_binds(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "look at this") == []


def test_struct_a_multi_word_name_is_never_subject_to_the_rule(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    assert _ids("library", "is night watch any good") == ["b1"]


# -- df (H1, falsified, kept for the record) -----------------------------------

def test_df_is_a_corpus_frequency_cut_and_reads_casing_not_at_all(indexes, monkeypatch):
    _mode(monkeypatch, "df")
    # In a seven-document corpus every token clears 1 %, so *every* one-word
    # name is dropped — including the rare "Orrery". That corpus-size
    # sensitivity is one of the reasons H1 was falsified; the rule is kept
    # only so the record reproduces.
    assert indexes["library"].token_df("watch") > ns.DISTINCT_MAX_DF
    assert indexes["library"].token_df("orrery") > ns.DISTINCT_MAX_DF
    assert _ids("library", "is Watch worth reading") == []
    assert _ids("library", "tell me about the Orrery") == []
    assert _ids("library", "is night watch any good") == ["b1"]


# -- across sources --------------------------------------------------------------

def test_nesting_is_suppressed_across_sources(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    hits = ns.exact_name_matches_all(("library", "archive"), "read the Night Watch Restoration Notes")
    assert [(ds, c.entity_id) for ds, c in hits] == [("archive", "a1")]


def test_the_same_name_in_two_sources_is_an_ambiguity_not_a_nesting(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    hits = ns.exact_name_matches_all(("library", "archive"), "what is the Orrery")
    assert {(ds, c.entity_id) for ds, c in hits} == {("library", "b3"), ("archive", "a3")}


def test_separate_mentions_survive_across_sources(indexes, monkeypatch):
    _mode(monkeypatch, "1")
    hits = ns.exact_name_matches_all(("library", "archive"), "compare Night Watch with Gilding")
    assert {(ds, c.entity_id) for ds, c in hits} == {("library", "b1"), ("archive", "a2")}


def test_exclude_drops_schema_word_names(indexes, monkeypatch):
    _mode(monkeypatch, "0")
    assert ns.exact_name_matches_all(("library",), "list every Watch", exclude={"library": {"watch"}}) == []


# -- the real snapshot ------------------------------------------------------------

@pytest.mark.skipif(
    not (Path(ns.REPO) / "data/graphs/attack/canonical/nodes.jsonl").exists(),
    reason="canonical snapshot not present",
)
def test_the_named_cases_on_the_real_snapshot(monkeypatch):
    _mode(monkeypatch, "1")
    ns.index_for.cache_clear()
    names = lambda ds, q: [c.name for c in ns.exact_name_matches(ds, q)]  # noqa: E731
    assert "Phishing" in names("attack", "what is Phishing")
    assert "Credentials" not in names("attack", "stolen credentials were used")
    assert names("attack", "Which techniques does group G9999 (Crimson Hollow) use?") == []
    assert "Hardware" in names("capec", "Browsing Hardware as a starting point, which attack patterns sit underneath the category?")
    both = ns.exact_name_matches_all(("attack", "capec"), "what is Phishing")
    assert {ds for ds, _ in both} == {"attack", "capec"}
