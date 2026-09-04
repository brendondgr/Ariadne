#!/usr/bin/env python3
"""The LLM query builder: it is a fair baseline, and the gate still holds.

Two things are being defended here and only one of them is about the baseline.

**The gate must not weaken.** `BaseValidator` reads the query *string* and has
never looked at `draft.template`, which is what makes this arm possible without
touching the safety path. That is a claim about the code and it is asserted
directly: a model that emits `DETACH DELETE` is refused by the same validator
that refuses it today, and so is a write, an unbounded path, and a label that
does not exist. C-008 rests on the gate, so an arm that quietly bypassed it
would damage a claim while appearing to add one.

**The baseline must be fair.** C-012 wants to compare templates against an LLM
writing queries. A baseline that fails because it was never told the schema, or
never told the constraints, or was denied the repair loop the templated path
gets, measures the harness rather than the model. So the prompt is asserted to
carry the schema and the seeds, and the repair path is asserted to carry the
gate's rejection reasons back.

The counterpart of fairness is no fallback: on failure this builder must not
quietly hand back a templated query, because that would turn the baseline into
the treatment and make the comparison meaningless.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from utils.specialists.config import SpecialistConfig
from utils.specialists.contracts import SpecialistTask
from utils.specialists.cypher.specialist import build_cypher_specialist
from utils.specialists.cypher.validator import CypherValidator
from utils.specialists.gremlin.specialist import build_gremlin_specialist
from utils.specialists.llm_builder import (
    LLMBuilderUnavailable,
    LLMQueryBuilder,
    extract_json_object,
)
from utils.specialists.resolve import resolve
from utils.specialists.tests._fixtures import fixture_card
from utils.specialists.validation import QueryDraft

_LIMITS = {"max_result_rows": 300, "max_traversal_depth": 3, "query_timeout_ms": 5000}


def _resolved(text: str, entities: tuple[str, ...], seeds: tuple[str, ...] = ()):
    task = SpecialistTask(
        sub_question_id="q1", source="attack", text=text,
        entities=entities, limits=_LIMITS, seed_ids=seeds,
    )
    return resolve(task, fixture_card("attack"))


def _builder(reply: str | Exception, language: str = "cypher") -> LLMQueryBuilder:
    """A builder whose transport is stubbed, so no test needs a served model."""
    builder = LLMQueryBuilder(card=fixture_card("attack"), language=language)

    def _post(_prompt: str) -> str:
        if isinstance(reply, Exception):
            raise reply
        return reply

    builder._post = _post  # type: ignore[method-assign]
    return builder


# -- the gate is unchanged ---------------------------------------------------


@pytest.mark.parametrize(
    "query,why",
    [
        ("MATCH (n:Technique) DETACH DELETE n RETURN n", "destructive"),
        ("MATCH (n:Technique) SET n.name = 'x' RETURN n", "write"),
        ("MATCH (n:Technique) RETURN n; MATCH (m:Group) RETURN m", "two statements"),
        ("MATCH (g:Group)-[:USES*]->(t:Technique) RETURN t", "unbounded path"),
        ("MATCH (n:Wizard) RETURN n.attack_id", "label not in the card"),
        ("CALL db.labels() YIELD label RETURN label", "no MATCH"),
    ],
)
def test_the_gate_refuses_a_dangerous_llm_query(query: str, why: str) -> None:
    """The model may write anything; the validator is what decides.

    Each of these is a query a language model could plausibly emit and none of
    them may reach a connector. `draft.template` is `llm_generated` throughout —
    the validator never reads it, which is the property that lets this arm exist
    without a safety exception.
    """
    draft = QueryDraft(query=query, params={}, template="llm_generated")
    result = CypherValidator().validate(draft, fixture_card("attack"), _LIMITS)
    assert not result.ok, f"gate accepted a {why} query"
    assert result.reasons


def test_a_legal_llm_query_passes_the_gate() -> None:
    """The gate must not reject everything unlabelled, or the arm measures nothing."""
    draft = QueryDraft(
        query="MATCH (g:Group)-[:USES]->(t:Technique) WHERE g.attack_id IN $ids "
              "RETURN g.attack_id AS group_id, t.attack_id AS technique_id",
        params={"ids": ["G0082"]},
        template="llm_generated",
    )
    result = CypherValidator().validate(draft, fixture_card("attack"), _LIMITS)
    assert result.ok, result.reasons


# -- the baseline is fair ----------------------------------------------------


def test_the_prompt_carries_the_schema() -> None:
    prompt = _builder("{}").prompt_for(_resolved("Which techniques does G0082 use?",
                                                 ("Group", "Technique")), None)
    assert "Technique" in prompt and "USES" in prompt
    assert "node_labels" in prompt and "relationship_types" in prompt


def test_the_prompt_carries_the_resolved_seeds() -> None:
    """Asking a model to guess identifiers would measure recall, not query writing."""
    prompt = _builder("{}").prompt_for(
        _resolved("Which techniques does G0082 use?", ("Group", "Technique"), ("G0082",)),
        None,
    )
    assert "G0082" in prompt


def test_the_prompt_never_leaks_a_template() -> None:
    prompt = _builder("{}").prompt_for(_resolved("Which techniques does G0082 use?",
                                                 ("Group", "Technique"), ("G0082",)), None)
    for leak in ("group_techniques", "expected_template", "template"):
        assert leak not in prompt.lower(), f"prompt leaked {leak!r}"


def test_gate_rejections_are_fed_back_for_repair() -> None:
    """The templated path gets a repair loop; denying it here would be a strawman."""
    prompt = _builder("{}").prompt_for(
        _resolved("Which techniques does G0082 use?", ("Group", "Technique")),
        ["label 'Wizard' is not in the card", "unbounded variable-length path"],
    )
    assert "REJECTED" in prompt
    assert "Wizard" in prompt and "unbounded" in prompt


def test_the_language_rules_match_the_backend() -> None:
    cy = _builder("{}", "cypher").prompt_for(_resolved("q", ("Technique",)), None)
    gr = _builder("{}", "gremlin").prompt_for(_resolved("q", ("Technique",)), None)
    assert "MATCH and RETURN" in cy and "g.V(" not in cy
    assert "g.V(" in gr and "MATCH and RETURN" not in gr


# -- parsing and failure -----------------------------------------------------


def test_a_clean_reply_becomes_a_draft() -> None:
    builder = _builder('{"query": "MATCH (n:Technique) RETURN n", "params": {"ids": ["T1055"]}}')
    draft = builder.build(_resolved("q", ("Technique",)))
    assert draft.query == "MATCH (n:Technique) RETURN n"
    assert draft.params == {"ids": ["T1055"]}
    assert draft.template == "llm_generated"
    assert draft.meta["builder"] == "llm"


def test_reasoning_preamble_and_fences_are_survived() -> None:
    reply = (
        "Let me think about this. The schema has Technique.\n"
        '```json\n{"query": "MATCH (n:Technique) RETURN n", "params": {}}\n```'
    )
    assert _builder(reply).build(_resolved("q", ("Technique",))).query == (
        "MATCH (n:Technique) RETURN n"
    )


def test_an_unreachable_model_yields_an_empty_draft_not_a_template() -> None:
    """No fallback, on purpose.

    Falling back to the templated builder would convert the baseline into the
    treatment: the arm would score like Arm A and the C-012 comparison would be
    measuring nothing. An empty query is refused by the gate with a recorded
    reason, and the specialist reports an honest failure.
    """
    builder = _builder(LLMBuilderUnavailable("connection refused"))
    draft = builder.build(_resolved("Which techniques does G0082 use?", ("Group", "Technique")))
    assert draft.query == ""
    assert draft.template == "llm_generated"
    assert "connection refused" in (draft.meta["error"] or "")
    result = CypherValidator().validate(draft, fixture_card("attack"), _LIMITS)
    assert not result.ok
    assert "empty query" in result.reasons


def test_a_reply_with_no_json_yields_an_empty_draft() -> None:
    draft = _builder("I cannot write that query.").build(_resolved("q", ("Technique",)))
    assert draft.query == ""
    assert draft.meta["error"]


def test_extract_json_handles_nested_and_escaped_braces() -> None:
    text = '{"query": "MATCH (n) WHERE n.x = \\"{a}\\" RETURN n", "params": {"k": {"n": 1}}}'
    assert extract_json_object(text)["params"] == {"k": {"n": 1}}


# -- wiring ------------------------------------------------------------------


def test_the_arm_flag_is_not_the_flag_four_other_arms_already_set() -> None:
    """`SPECIALIST_LLM_ENABLED` is set true by Arms B, C, F and H.

    It sat unread by any builder. Consuming *it* would have swapped the query
    builder under four committed arms and invalidated the arm table, so this
    baseline gets its own switch.
    """
    data_dir = Path("data")
    on_old = build_cypher_specialist(
        fixture_card("attack"), SpecialistConfig(data_dir=data_dir, llm_enabled=True)
    )
    assert type(on_old.builder).__name__ == "CypherQueryBuilder"

    on_new = build_cypher_specialist(
        fixture_card("attack"), SpecialistConfig(data_dir=data_dir, llm_query_builder=True)
    )
    assert isinstance(on_new.builder, LLMQueryBuilder)


def test_both_backends_swap_their_builder() -> None:
    data_dir = Path("data")
    config = SpecialistConfig(data_dir=data_dir, llm_query_builder=True)
    assert isinstance(build_cypher_specialist(fixture_card("attack"), config).builder,
                      LLMQueryBuilder)
    assert isinstance(build_gremlin_specialist(fixture_card("capec"), config).builder,
                      LLMQueryBuilder)


def test_the_arm_is_registered_everywhere_it_must_be() -> None:
    """Five sites, one of which fails silently if missed.

    An arm absent from the env cascade falls through to the `else` branch and
    runs as full-LLM; an arm absent from the pool line gets a router pool built
    with the wrong config. Both produce a plausible-looking run of the wrong arm.
    """
    from utils.evaluation.experiment_untruncated import ARMS, RUNNERS, untruncated_env

    assert "llm_query" in ARMS
    assert "llm_query" in RUNNERS
    env = untruncated_env(arm="llm_query", llm_model="m", llm_max_tokens=4096)
    assert env["SPECIALIST_LLM_QUERY_BUILDER"] == "true"
    # the plan is held constant: only query writing varies against Arm A
    assert env["PLANNER_LLM_ENABLED"] == "false"
    assert env["SYNTHESIS_LLM_ENABLED"] == "false"


def test_no_other_arm_turns_the_query_builder_on() -> None:
    from utils.evaluation.experiment_untruncated import ARMS, untruncated_env

    for arm in ARMS:
        env = untruncated_env(arm=arm, llm_model="m", llm_max_tokens=4096)
        flag = env.get("SPECIALIST_LLM_QUERY_BUILDER")
        assert (flag == "true") == (arm == "llm_query"), f"{arm} set the builder flag to {flag}"


class TestTheBudgetIsReadAtCallTime:
    """An env-driven bound bound at import is a setting that can be ignored.

    `experiment_untruncated` applies its env profile *after* importing the
    builder, so the arm ran on whatever the environment held at import -- 4096 --
    while the profile it had just applied asked for 16384. Nothing errored: the
    model spent the smaller budget on chain-of-thought and returned an empty
    ``content``, which downstream is indistinguishable from a model with nothing
    to say. 153 of 284 questions in EXP-2026-09-002 came back that way.
    """

    def test_setting_the_env_after_import_now_takes_effect(self, monkeypatch):
        from utils.specialists.llm_builder import default_max_tokens

        monkeypatch.setenv("SPECIALIST_LLM_MAX_TOKENS", "16384")
        assert default_max_tokens() == 16384

    def test_the_fallback_is_unchanged_when_nothing_is_set(self, monkeypatch):
        from utils.specialists.llm_builder import default_max_tokens

        monkeypatch.delenv("SPECIALIST_LLM_MAX_TOKENS", raising=False)
        assert default_max_tokens() == 4096

    def test_an_explicit_budget_still_wins_over_the_environment(self, monkeypatch):
        from utils.specialists.llm_builder import LLMQueryBuilder

        monkeypatch.setenv("SPECIALIST_LLM_MAX_TOKENS", "16384")
        builder = LLMQueryBuilder(card=None, language="cypher", max_tokens=2048)
        assert builder.max_tokens == 2048

    def test_the_default_defers_rather_than_freezing_a_value(self):
        from utils.specialists.llm_builder import LLMQueryBuilder

        # None is the signal to resolve later; a concrete default here is what
        # made the setting ignorable.
        assert LLMQueryBuilder(card=None, language="cypher").max_tokens is None


class TestTheArmGetsTimeAsWellAsTokens:
    """A token budget the clock cuts off is not a budget.

    The 2026-09-04 re-run raised max_tokens and left the 120 s builder timeout
    alone. The model reasons for 170 s at 8192, so every call was aborted and
    returned nothing, the gate refused 282 of 284 as empty queries, and the
    answers record wall_s = 360.3 -- three attempts at 120 s exactly.
    """

    def test_the_llm_query_arm_sets_a_timeout_above_the_measured_reasoning_time(self):
        from utils.evaluation.experiment_untruncated import untruncated_env

        env = untruncated_env(arm="llm_query", llm_model="skynet", llm_max_tokens=8192)
        assert "SPECIALIST_LLM_TIMEOUT_S" in env, "tokens without time is not a budget"
        # 230 s is the slowest budget the probe measured; the arm must clear it.
        assert float(env["SPECIALIST_LLM_TIMEOUT_S"]) > 230.0

    def test_the_timeout_scales_with_the_token_budget(self):
        from utils.evaluation.experiment_untruncated import untruncated_env

        small = untruncated_env(arm="llm_query", llm_model="m", llm_max_tokens=8192)
        large = untruncated_env(arm="llm_query", llm_model="m", llm_max_tokens=32768)
        assert float(large["SPECIALIST_LLM_TIMEOUT_S"]) >= float(small["SPECIALIST_LLM_TIMEOUT_S"])
