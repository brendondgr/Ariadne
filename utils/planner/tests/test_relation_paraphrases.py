"""A generated relation lexicon binds a relation from the analyst's words, and never routes (EXP-2026-09-027).

Runs on a made-up card so the mechanism is shown to read only the card's own
``relationship_paraphrases`` block.
"""

from __future__ import annotations

from utils.planner import drafter
from utils.planner.cards import SourceCardView


def _card(paraphrases: dict[str, list[str]] | None = None) -> SourceCardView:
    return SourceCardView.from_card_dict({
        "dataset": "library", "runtime_backend": "neo4j",
        "node_labels": ["Book", "Topic", "Reader"],
        "relationship_types": ["COVERS", "BORROWED_BY"],
        "node_properties": {"Book": {"title": {}}, "Topic": {"name": {}}, "Reader": {"name": {}}},
        "entity_descriptions": {
            "nodes": {"Book": "A published volume.", "Topic": "A subject a book treats."},
            "relationships": {"COVERS": "A Book covers a Topic.", "BORROWED_BY": "A Book is borrowed by a Reader."},
            **({"relationship_paraphrases": paraphrases} if paraphrases is not None else {}),
        },
    })


PARA = {"COVERS": ["deal with", "treat", "subject matter"], "BORROWED_BY": ["checked out", "on loan"]}


def test_off_by_default_the_router_ignores_the_lexicon(monkeypatch):
    monkeypatch.delenv("ARIADNE_RELATION_PARAPHRASES", raising=False)
    _id, gloss = drafter._concept_indexes(_card(PARA))  # noqa: SLF001
    assert "loan" not in gloss and "deal" not in gloss


def test_on_a_paraphrase_word_binds_its_relation_as_a_gloss_hit(monkeypatch):
    monkeypatch.setenv("ARIADNE_RELATION_PARAPHRASES", "1")
    id_index, gloss = drafter._concept_indexes(_card(PARA))  # noqa: SLF001
    assert gloss["loan"] == {"BORROWED_BY"}
    assert gloss["deal"] == {"COVERS"}
    assert "loan" not in id_index, "a paraphrase is a hint, never a routing token"


def test_a_paraphrase_for_an_undeclared_relation_is_ignored(monkeypatch):
    monkeypatch.setenv("ARIADNE_RELATION_PARAPHRASES", "1")
    _id, gloss = drafter._concept_indexes(_card({"CITES": ["refer to"]}))  # noqa: SLF001
    assert "refer" not in gloss


def test_the_router_reaches_the_relation_through_the_paraphrase(monkeypatch):
    monkeypatch.setenv("ARIADNE_RELATION_PARAPHRASES", "1")
    card = _card(PARA)
    tokens = drafter._tokens("which readers have this book on loan")  # noqa: SLF001
    _ids, _gloss_hits, matched, _toks = drafter._match_card(tokens, card)  # noqa: SLF001
    assert "BORROWED_BY" in matched
