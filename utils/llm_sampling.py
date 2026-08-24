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


def sampling_params(*, max_tokens: int, seed: int | None = None) -> dict[str, object]:
    """The graded-call sampling block: greedy, seeded, bounded.

    Callers spread this into their request payload rather than restating the
    fields, so a change to the project's determinism posture happens in one
    place instead of five.
    """
    return {
        "temperature": 0,
        "top_p": 1,
        "seed": env_int("LLM_SEED", DEFAULT_SEED) if seed is None else seed,
        "max_tokens": max_tokens,
    }
