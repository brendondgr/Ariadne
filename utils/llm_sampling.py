#!/usr/bin/env python3
"""Sampling parameters shared by every *graded* LLM call in the pipeline.

Q2 asked what the variance on the LLM-in-the-loop figures is. Part of the answer
is a design property that was already true and never written down: **every
graded call site sends ``temperature: 0``** — the planner drafter, the intent
classifier, the specialist query builder, the synthesis composer and the judge.
Only the bank Author samples at 1.0, and there phrasing variety *is* the point
and the output is never scored.

Temperature 0 is not the same as determinism. A server doing greedy decoding
still reduces floating point over whatever batch a request lands in, so identical
prompts can diverge when concurrency changes the batch shape. That residual is
what this module exists to shrink.

``seed`` is the lever. vLLM honours it, and a server that does not simply ignores
an unknown field, so sending it cannot break a call. It does not make batched
inference bit-exact — nothing at the client can — but it removes every source of
variation that *is* under client control.

**Deliberately not applied to the Author** (`utils/specialists/evalset/author.py`):
a bank drawn with a fixed seed and temperature 0 would ask thirty anchors the
same question thirty ways less varied than a human would, and the Author's whole
purpose is phrasing diversity. Its nondeterminism is a feature and is recorded
as such in the EXP-2026-08-015 manifest.
"""

from __future__ import annotations

from utils.config import env_int

#: Fixed so a re-run varies as little as the serving stack allows. The value is
#: arbitrary; that it is *pinned and recorded* is the point. Matches the
#: bootstrap seed used elsewhere in the research record so one number identifies
#: "this project's fixed seed".
DEFAULT_SEED = 1729


def sampling_params(
    *, max_tokens: int, seed: int | None = None, thinking_budget: int | None = None
) -> dict[str, object]:
    """The graded-call sampling block: greedy, seeded, bounded.

    Callers spread this into their request payload rather than restating the
    fields, so a change to the project's determinism posture happens in one
    place instead of five.
    """
    params: dict[str, object] = {
        "temperature": 0,
        "top_p": 1,
        "seed": env_int("LLM_SEED", DEFAULT_SEED) if seed is None else seed,
        "max_tokens": max_tokens,
    }
    # Cap the chain of thought when the served model is a reasoning model.
    #
    # The whole llm_query saga was a reasoning model spending its allowance on
    # thinking and emitting nothing: 4,134 tokens of answer behind 16,106
    # characters of preamble on an easy question, and 42,602 characters when
    # given room. That is not deliberation this task needs -- the builder is
    # writing one bounded query against a schema it was handed -- and it is what
    # made the arm cost roughly forty thousand times the template path.
    #
    # Sent through the two channels vLLM accepts, since which one applies
    # depends on the served model's chat template; an endpoint that understands
    # neither ignores both rather than failing, so this is safe to send always.
    # The budget is resolved by utils.llm.config, which is now the single source
    # for it -- there used to be three (this env read, SYNTHESIS_LLM_THINKING_
    # BUDGET, and an implicit max_tokens // 2 inside SynthesisConfig). Callers
    # that hold resolved settings pass the value; the env read stays as the
    # fallback for the scripts that set LLM_THINKING_BUDGET directly, and
    # utils.llm.config honours that same name as a legacy alias so both paths
    # agree.
    budget = env_int("LLM_THINKING_BUDGET", 0) if thinking_budget is None else thinking_budget
    if budget > 0:
        # A budget at or above the output cap leaves nothing for the answer and
        # the model returns empty content -- which reaches a caller as a silent
        # "LLM unavailable" rather than an error. Refuse to send that.
        if budget >= max_tokens:
            budget = max(0, max_tokens - 1)
    if budget > 0:
        params["chat_template_kwargs"] = {"thinking_budget": budget}
        params["extra_body"] = {"thinking_budget": budget}
    return params
