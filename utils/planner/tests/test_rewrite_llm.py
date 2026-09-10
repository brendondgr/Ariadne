#!/usr/bin/env python3
"""The gated, cached model fill.

Every test here drives a fake client. The point of this seam is not that the
model is good at choosing — that is Step 7's experiment — it is that **nothing
the model returns can put a value into a form that was not on the list it was
handed**. That is a property of this code and is testable without a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest

from utils.llm import LLMUnavailable
from utils.planner.canonical import (
    DIR_IN,
    DIR_OUT,
    MODE_DESCRIBE,
    MODE_ENUMERATE,
    SLOT_ANCHORS,
    SLOT_RELATION,
    SLOT_TARGET_LABELS,
    CandidateLists,
    Choice,
    IntentForm,
    gate_form,
)
from utils.planner.rewrite_cache import CacheEntry, RewriteCache, cache_key
from utils.planner.rewrite_llm import (
    PROMPT_VERSION,
    RewriteChoice,
    RewriteUnavailable,
    apply_choice,
    build_prompt,
    choose,
    fill,
)
from utils.planner.tests._fixtures import load_fixture_cards

CARDS = load_fixture_cards()
ATTACK = CARDS["attack"]


@dataclass
class _Settings:
    model: str = "test-model"
    base_url: str = "http://test/v1"
    provider: str = "openai"
    max_tokens: int = 512
    thinking_budget: int | None = None


@dataclass
class _Result:
    content: str
    model: str = "weights-under-test"
    finish_reason: str = "stop"

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


@dataclass
class _FakeClient:
    """Records what it was asked and returns a canned reply."""

    reply: Any
    calls: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, settings, messages, **kwargs):
        self.calls.append({"settings": settings, "messages": messages, **kwargs})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _lists() -> dict[str, CandidateLists]:
    return {
        "attack": CandidateLists(
            dataset="attack",
            anchors=(
                Choice(0, "T1047", "Technique", "Windows Management Instrumentation", "A gloss."),
                Choice(1, "T1059", "Technique", "Command and Scripting Interpreter", "Another."),
            ),
            relations=(
                Choice(0, "MITIGATES", gloss="A Mitigation reduces risk for a Technique."),
                Choice(1, "ATTRIBUTED_TO", gloss="A Campaign is attributed to a Group."),
            ),
            labels=(Choice(0, "Mitigation"), Choice(1, "Technique")),
        )
    }


def _open_form() -> IntentForm:
    return IntentForm(mode=MODE_ENUMERATE, datasets=("attack",)).with_unbound(
        SLOT_ANCHORS, SLOT_RELATION, SLOT_TARGET_LABELS
    )


def _choice(**kwargs) -> RewriteChoice:
    return RewriteChoice.from_payload(kwargs)


# -- the prompt -------------------------------------------------------------


def test_the_prompt_offers_only_the_outstanding_slots() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), mode=MODE_ENUMERATE,
        datasets=("attack",),
    ).with_unbound(SLOT_RELATION)
    prompt = build_prompt("what stops it?", form, _lists())
    assert "ALREADY DETERMINED" in prompt
    assert "anchor = T1047" in prompt
    assert "RELATIONSHIPS" in prompt
    assert "ANCHOR CANDIDATES" not in prompt


def test_the_prompt_numbers_every_option_it_shows() -> None:
    prompt = build_prompt("anything", _open_form(), _lists())
    assert "0. T1047 [Technique] Windows Management Instrumentation — A gloss." in prompt
    assert "0. MITIGATES — A Mitigation reduces risk for a Technique." in prompt


# -- what a choice may and may not do ---------------------------------------


def test_a_valid_choice_fills_the_outstanding_slots() -> None:
    form, rejected = apply_choice(
        _open_form(), _choice(anchor=0, relation=0, target_label=0), _lists(), CARDS
    )
    assert rejected == []
    assert form.anchors == ("T1047",)
    assert form.anchor_labels == ("Technique",)
    assert form.relation == "MITIGATES"
    assert form.target_labels == ("Mitigation",)
    assert form.direction == DIR_IN  # read from the card, never from the model
    assert form.unbound == ()
    assert form.sources[SLOT_ANCHORS] == "model"


def test_an_invented_identifier_is_not_a_choice() -> None:
    form, rejected = apply_choice(
        _open_form(), _choice(anchor="T9999"), _lists(), CARDS
    )
    assert form.anchors == ()
    assert SLOT_ANCHORS in form.unbound
    assert any("not an index" in r for r in rejected)


def test_a_name_that_is_on_the_list_is_still_not_a_choice() -> None:
    """Writing "MITIGATES" is not the same as picking the index that holds it."""
    form, rejected = apply_choice(
        _open_form(), _choice(relation="MITIGATES"), _lists(), CARDS
    )
    assert form.relation is None
    assert any("not an index" in r for r in rejected)


def test_an_out_of_range_index_is_rejected() -> None:
    _form, rejected = apply_choice(_open_form(), _choice(anchor=99), _lists(), CARDS)
    assert any("99" in r for r in rejected)


def test_a_boolean_is_not_an_index() -> None:
    _form, rejected = apply_choice(_open_form(), _choice(anchor=True), _lists(), CARDS)
    assert rejected


def test_an_invented_mode_is_rejected_and_the_old_one_kept() -> None:
    form, rejected = apply_choice(
        _open_form(), _choice(mode="speculate"), _lists(), CARDS
    )
    assert form.mode == MODE_ENUMERATE
    assert any("speculate" in r for r in rejected)


def test_a_relation_the_anchor_does_not_carry_is_refused_not_rendered() -> None:
    """ATTRIBUTED_TO runs Campaign -> Group. A Technique has no such edge."""
    form, rejected = apply_choice(
        _open_form(), _choice(anchor=0, relation=1, target_label=1), _lists(), CARDS
    )
    assert form.relation is None
    assert any("not declared" in r for r in rejected)


def test_ambiguous_abstains_and_changes_nothing() -> None:
    before = _open_form()
    after, rejected = apply_choice(before, _choice(ambiguous=True), _lists(), CARDS)
    assert after == before
    assert rejected == ["the model declined: ambiguous"]


def test_direction_is_never_taken_from_the_model() -> None:
    """Even a payload that names a direction cannot set one."""
    form, _rejected = apply_choice(
        _open_form(),
        _choice(anchor=0, relation=0, target_label=0, direction=DIR_OUT),
        _lists(),
        CARDS,
    )
    assert form.direction == DIR_IN


# -- the gate ---------------------------------------------------------------


def test_the_gate_passes_a_form_the_model_never_touched() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction=DIR_IN, mode=MODE_ENUMERATE, datasets=("attack",),
    )
    assert gate_form(form, _lists(), CARDS).passed


def test_the_gate_rejects_an_anchor_the_model_supplied_that_is_off_list() -> None:
    form = IntentForm(
        anchors=("T9999",), anchor_labels=("Technique",), mode=MODE_DESCRIBE,
        datasets=("attack",), sources={SLOT_ANCHORS: "model"},
    )
    verdict = gate_form(form, _lists(), CARDS)
    assert not verdict.passed
    assert any("not on any candidate list" in r for r in verdict.reasons)


def test_the_gate_rejects_an_invented_label() -> None:
    form = IntentForm(
        anchors=("T1047",), target_labels=("Wishlist",), mode=MODE_ENUMERATE,
        datasets=("attack",),
    )
    verdict = gate_form(form, _lists(), CARDS)
    assert not verdict.passed
    assert any("Wishlist" in r for r in verdict.reasons)


def test_the_gate_rejects_an_invented_relation() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="CURES", mode=MODE_ENUMERATE, datasets=("attack",),
    )
    assert not gate_form(form, _lists(), CARDS).passed


def test_the_gate_rejects_a_reversed_direction() -> None:
    form = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction=DIR_OUT, mode=MODE_ENUMERATE, datasets=("attack",),
    )
    verdict = gate_form(form, _lists(), CARDS)
    assert not verdict.passed
    assert any("contradicts the declared endpoints" in r for r in verdict.reasons)


def test_the_gate_rejects_a_dead_source() -> None:
    form = IntentForm(anchors=("X",), datasets=("nowhere",))
    assert not gate_form(form, _lists(), CARDS).passed


# -- transport, cache and the end-to-end contract ---------------------------


def test_a_transport_failure_abstains_rather_than_raising(tmp_path) -> None:
    client = _FakeClient(LLMUnavailable("connection refused"))
    form, trace = fill(
        "anything", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert trace["rung"] == "abstain"
    assert form == _open_form()
    assert any("unavailable" in r for r in trace["rejected"])


def test_an_empty_reply_abstains(tmp_path) -> None:
    client = _FakeClient(_Result("", finish_reason="length"))
    _form, trace = fill(
        "anything", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert trace["rung"] == "abstain"
    assert any("output budget" in r for r in trace["rejected"])


def test_unparseable_output_abstains(tmp_path) -> None:
    client = _FakeClient(_Result("I think it is probably T1047, honestly"))
    _form, trace = fill(
        "anything", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert trace["rung"] == "abstain"


def test_a_good_choice_passes_the_gate_and_reports_the_rung(tmp_path) -> None:
    client = _FakeClient(
        _Result(json.dumps({"anchor": 0, "relation": 0, "target_label": 0, "why": "wmi"}))
    )
    form, trace = fill(
        "how do I stop WMI abuse?", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert trace["rung"] == "model"
    assert trace["gate"]["passed"] is True
    assert trace["why"] == "wmi"
    assert form.anchors == ("T1047",)


def test_a_gated_out_choice_abstains_and_keeps_the_original_form(tmp_path) -> None:
    client = _FakeClient(_Result(json.dumps({"anchor": 5, "relation": 9})))
    form, trace = fill(
        "anything", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert form == _open_form()
    assert trace["rung"] in {"abstain", "model"}
    assert trace["rejected"]


def test_an_ambiguous_reply_abstains(tmp_path) -> None:
    client = _FakeClient(_Result(json.dumps({"ambiguous": True, "why": "three fit"})))
    form, trace = fill(
        "anything", _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert trace["rung"] == "abstain"
    assert form == _open_form()


def test_the_second_call_is_served_from_cache(tmp_path) -> None:
    client = _FakeClient(_Result(json.dumps({"anchor": 0, "relation": 0, "target_label": 0})))
    cache = RewriteCache(tmp_path)
    question = "how do I stop WMI abuse?"
    first, trace_a = fill(
        "x" + question, _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=cache, client=client,
    )
    second, trace_b = fill(
        "x" + question, _open_form(), CARDS, _Settings(),
        lists=_lists(), cache=cache, client=client,
    )
    assert len(client.calls) == 1
    assert trace_a["cache_hit"] is False
    assert trace_b["cache_hit"] is True
    assert first == second


def test_the_cache_key_separates_prompt_versions_and_weights() -> None:
    base = cache_key(PROMPT_VERSION, "weights-a", "q")
    assert base != cache_key(PROMPT_VERSION + "x", "weights-a", "q")
    assert base != cache_key(PROMPT_VERSION, "weights-b", "q")
    assert base != cache_key(PROMPT_VERSION, "weights-a", "q ")


def test_a_corrupt_cache_entry_is_a_miss_not_a_crash(tmp_path) -> None:
    cache = RewriteCache(tmp_path)
    key = cache_key(PROMPT_VERSION, "m", "q")
    path = cache.path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    assert cache.get(key) is None


def test_the_budget_is_never_below_the_reasoning_floor(tmp_path) -> None:
    """A reasoning model with a small budget truncates to empty, and the
    pipeline then reports "LLM unavailable" and nobody looks further."""
    client = _FakeClient(_Result(json.dumps({"anchor": 0})))
    choose(
        "q", _open_form(), CARDS, _Settings(max_tokens=64),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert client.calls[0]["max_tokens"] >= 2048
    assert client.calls[0]["sampling"]["temperature"] == 0


def test_a_form_that_needs_nothing_never_reaches_the_model(tmp_path) -> None:
    """Consulting the model here would put a choice in front of a fact."""
    client = _FakeClient(_Result(json.dumps({"anchor": 1})))
    bound = IntentForm(
        anchors=("T1047",), anchor_labels=("Technique",), target_labels=("Mitigation",),
        relation="MITIGATES", direction=DIR_IN, mode=MODE_ENUMERATE, datasets=("attack",),
    )
    form, trace = fill(
        "anything", bound, CARDS, _Settings(),
        lists=_lists(), cache=RewriteCache(tmp_path), client=client,
    )
    assert client.calls == []
    assert trace["rung"] == "deterministic"
    assert form == bound


def test_a_resolved_direction_stops_being_outstanding() -> None:
    open_with_direction = _open_form().with_unbound("direction")
    form, _rejected = apply_choice(
        open_with_direction, _choice(anchor=0, relation=0, target_label=0), _lists(), CARDS
    )
    assert form.direction == DIR_IN
    assert "direction" not in form.unbound


# -- the relation is derived, not chosen (EXP-2026-09-015) ------------------


def test_the_label_pair_derives_the_relation_and_the_model_is_not_asked() -> None:
    """Technique + Mitigation pins MITIGATES; the model's index is irrelevant."""
    form, rejected = apply_choice(
        _open_form(), _choice(anchor=0, relation=1, target_label=0), _lists(), CARDS
    )
    assert form.relation == "MITIGATES"
    assert form.sources["relation"] == "schema-registry"
    assert rejected == []


def test_an_out_of_range_relation_index_no_longer_blocks_a_pinned_pair() -> None:
    """The dominant abstention cause: 24 of 80 were an index past the list."""
    form, rejected = apply_choice(
        _open_form(), _choice(anchor=0, relation=99, target_label=0), _lists(), CARDS
    )
    assert form.relation == "MITIGATES"
    assert form.sources["relation"] == "schema-registry"
    assert rejected == []


def test_an_unpinned_pair_still_consults_the_model() -> None:
    """No target label means nothing to derive from, so the index is read."""
    form = IntentForm(mode=MODE_ENUMERATE, datasets=("attack",)).with_unbound(
        SLOT_ANCHORS, SLOT_RELATION
    )
    filled, rejected = apply_choice(form, _choice(anchor=0, relation=0), _lists(), CARDS)
    assert filled.relation == "MITIGATES"
    assert filled.sources["relation"] == "model"
    assert rejected == []


def test_an_unpinned_pair_still_rejects_an_out_of_range_index() -> None:
    form = IntentForm(mode=MODE_ENUMERATE, datasets=("attack",)).with_unbound(
        SLOT_ANCHORS, SLOT_RELATION
    )
    _filled, rejected = apply_choice(form, _choice(anchor=0, relation=99), _lists(), CARDS)
    assert any("not an index into the list" in r for r in rejected)


def test_the_derivation_can_be_ablated_off() -> None:
    """EXP-2026-09-015's control arm: same picks, the old interpretation."""
    form, rejected = apply_choice(
        _open_form(),
        _choice(anchor=0, relation=1, target_label=0),
        _lists(),
        CARDS,
        derive_relation=False,
    )
    assert form.sources.get("relation") != "schema-registry"
    assert any("ATTRIBUTED_TO" in r for r in rejected) or form.relation == "ATTRIBUTED_TO"
