#!/usr/bin/env python3
"""Tests for the Graph Extraction wrapper node (with an injected pipeline runner)."""

from __future__ import annotations

from utils.conversation.agents.graph_extraction import (
    augment_question,
    make_extraction_node,
)
from utils.conversation.config import ConversationConfig
from utils.orchestration.main import PipelineRun
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer


def _stub_runner(canned: PipelineRun, sink: list | None = None):
    def runner(question, *, mode, use_llm, run, forward=None, **kw):
        if sink is not None:
            sink.append(question)
        # Populate the caller-owned run like the real pipeline does.
        run.plan = canned.plan
        run.evidence = canned.evidence
        run.answer = canned.answer
        run.status = canned.status
        run.exit_code = canned.exit_code
        run.live_view = canned.live_view
        if forward is not None:
            forward("status", {"phase": "probing"})
            forward("answer", {"headline": "h"})
        return run

    return runner


def test_augment_question_no_params_is_identity():
    assert augment_question("base q", None) == "base q"
    assert augment_question("base q", {}) == "base q"


def test_augment_question_folds_focus_and_reason():
    out = augment_question(
        "details on T1598", {"focus": ["mitigations"], "reason": "no mitigations found"}
    )
    assert "details on T1598" in out
    assert "mitigations" in out
    assert "no mitigations found" in out


def test_extraction_node_returns_pipeline_outputs():
    canned = PipelineRun(
        question="q",
        answer=SynthesizedAnswer(request="q", narrative="grounded"),
        evidence=FederatedEvidence(request="q"),
        status="answered",
        exit_code=0,
    )
    node = make_extraction_node(ConversationConfig(), runner=_stub_runner(canned))
    out = node({"resolved_question": "q", "mode": "query"})

    assert out["status"] == "answered"
    assert out["exit_code"] == 0
    assert out["answer"].narrative == "grounded"
    assert isinstance(out["run"], PipelineRun)
    assert out["trace"][0]["node"] == "graph_extraction"
    assert out["trace"][0]["attempt"] == 1


def test_extraction_node_augments_on_retry():
    seen: list[str] = []
    canned = PipelineRun(question="q", status="answered", exit_code=0)
    node = make_extraction_node(
        ConversationConfig(), runner=_stub_runner(canned, seen)
    )
    node(
        {
            "resolved_question": "details on T1598",
            "mode": "query",
            "validation_iterations": 1,
            "extraction_params": {"focus": ["mitigations"], "reason": "missing"},
        }
    )
    assert "mitigations" in seen[0]


def test_extraction_node_attempt_counts_from_iterations():
    canned = PipelineRun(question="q", status="answered", exit_code=0)
    node = make_extraction_node(ConversationConfig(), runner=_stub_runner(canned))
    out = node({"resolved_question": "q", "validation_iterations": 1})
    assert out["trace"][0]["attempt"] == 2
