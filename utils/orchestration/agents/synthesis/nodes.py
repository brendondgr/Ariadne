#!/usr/bin/env python3
"""Synthesis subgraph nodes: compose → verify → narrate.

The invariant the wiring makes structural: **the verifier is not optional.**
``verify`` is an unconditional edge after ``compose``, whichever composer
drafted the claims. The LLM narrator runs *after* verification and is
best-effort — it only rewrites the prose ``narrative`` on the verified
answer, never the claims (``utils.synthesis.factory.apply_llm_narrative``).
"""

from __future__ import annotations

from typing import Any, Callable

from utils.orchestration.state import SynthesisState
from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import AnswerComposer, apply_llm_narrative
from utils.synthesis.verifier import verify_answer

NodeFn = Callable[[SynthesisState], dict[str, Any]]


def build_nodes(composer: AnswerComposer, config: SynthesisConfig) -> dict[str, NodeFn]:
    """Return the synthesis chain's node functions, closed over collaborators."""

    def compose(state: SynthesisState) -> dict[str, Any]:
        return {"draft": composer.compose(state["evidence"])}

    def verify(state: SynthesisState) -> dict[str, Any]:
        return {"answer": verify_answer(state["draft"], state["evidence"])}

    def narrate(state: SynthesisState) -> dict[str, Any]:
        answer = state["answer"]
        apply_llm_narrative(answer, state["evidence"], config)
        return {"answer": answer}

    return {"compose": compose, "verify": verify, "narrate": narrate}
