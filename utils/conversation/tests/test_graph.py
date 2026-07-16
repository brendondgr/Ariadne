#!/usr/bin/env python3
"""Golden event-order tests for the conversational super-graph.

Exercises the quick / graph / retry paths with an injected extraction runner
(no live backend) and stub LLM clients, pinning the exact emitted event order —
the same discipline the pipeline uses for its SSE contract.
"""

from __future__ import annotations

from dataclasses import replace

from utils.conversation.config import ConversationConfig, ConversationLLMConfig
from utils.conversation.main import iter_conversation
from utils.orchestration.main import PipelineRun
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer


class _StubLLM:
    """Enabled stub returning queued replies (last repeats)."""

    def __init__(self, replies, *, enabled=True):
        self._replies = list(replies)
        self.enabled = enabled
        self.calls = 0

    def complete(self, messages, **kwargs):
        self.calls += 1
        if not self._replies:
            return ""
        idx = min(self.calls - 1, len(self._replies) - 1)
        return self._replies[idx]


def _runner_forwarding(canned: PipelineRun):
    def runner(question, *, mode, use_llm, run, forward=None, **kw):
        if forward is not None:
            forward("status", {"phase": "querying", "message": "Querying graphs"})
            forward("evidence", {"evidence": {}})
            forward("answer", {"headline": "h"})
            forward("done", {"status": "answered"})  # must be suppressed
        run.answer = canned.answer
        run.evidence = canned.evidence
        run.status = canned.status
        run.exit_code = canned.exit_code
        return run

    return runner


def _names(events):
    return [name for name, _ in events]


def _cfg(**over):
    return replace(ConversationConfig(), **over)


def test_graph_path_llm_off_default_order():
    canned = PipelineRun(
        question="q",
        answer=SynthesizedAnswer(request="q", narrative="grounded body"),
        evidence=FederatedEvidence(request="q"),
        status="answered",
        exit_code=0,
    )
    events = list(
        iter_conversation(
            "Which techniques map to CAPEC-98?",
            conversation_id="c1",
            history=[],
            runner=_runner_forwarding(canned),
        )
    )
    names = _names(events)
    assert names == [
        "status",
        "context",
        "route",
        "status",  # forwarded pipeline status
        "evidence",
        "answer",
        "validation",
        "final",
        "conversation",
        "done",
    ]
    # Pipeline's own `done` was suppressed (only one terminal done).
    assert names.count("done") == 1
    route = dict(events)["route"]
    assert route["decision"] == "graph"
    final = dict(events)["final"]
    assert final["final_answer"] == "grounded body"
    assert dict(events)["done"]["status"] == "answered"


def test_quick_path_order_skips_extraction():
    router = _StubLLM(['{"route": "quick", "reason": "meta"}'])
    canned = PipelineRun(question="q", status="answered", exit_code=0)
    history = [
        {"role": "user", "content": "which techniques map to CAPEC-98?"},
        {"role": "assistant", "content": "T1566 and T1598.", "facts": ["CAPEC-98 -> T1598"]},
    ]
    events = list(
        iter_conversation(
            "remind me what it maps to",
            conversation_id="c1",
            history=history,
            router_client=router,
            runner=_runner_forwarding(canned),
        )
    )
    names = _names(events)
    assert names == ["status", "context", "route", "final", "conversation", "done"]
    assert dict(events)["route"]["decision"] == "quick"
    # No graph events at all.
    assert "evidence" not in names and "validation" not in names


def test_retry_path_runs_extraction_twice():
    validation = _StubLLM(
        [
            '{"sufficient": false, "missing": ["mitigations"], "reason": "no mitigations"}',
            '{"sufficient": true, "reason": "now complete"}',
        ]
    )
    canned = PipelineRun(
        question="q",
        answer=SynthesizedAnswer(request="q", narrative="body"),
        status="answered",
        exit_code=0,
    )
    events = list(
        iter_conversation(
            "full detail on T1598",
            conversation_id="c1",
            history=[],
            config=_cfg(max_validation_iters=3),
            validation_client=validation,
            runner=_runner_forwarding(canned),
        )
    )
    names = _names(events)
    # Two extraction passes -> two forwarded `answer` events and two validations.
    assert names.count("answer") == 2
    assert names.count("validation") == 2
    validations = [pl for nm, pl in events if nm == "validation"]
    assert validations[0]["verdict"] == "insufficient"
    assert validations[1]["verdict"] == "pass"
    assert names[-3:] == ["final", "conversation", "done"]


def test_retry_cap_forces_pass():
    # Always-insufficient LLM, cap=2 -> exactly two extraction passes then forced pass.
    validation = _StubLLM(['{"sufficient": false, "missing": ["x"], "reason": "r"}'])
    canned = PipelineRun(
        question="q", answer=SynthesizedAnswer(request="q", narrative="b"),
        status="answered", exit_code=0,
    )
    events = list(
        iter_conversation(
            "q",
            conversation_id="c1",
            history=[],
            config=_cfg(max_validation_iters=2),
            validation_client=validation,
            runner=_runner_forwarding(canned),
        )
    )
    names = _names(events)
    assert names.count("answer") == 2  # capped at two extraction passes
    validations = [pl for nm, pl in events if nm == "validation"]
    assert validations[-1]["verdict"] == "pass"
    assert validations[-1]["capped"] is True


def _runner_capturing(canned: PipelineRun, sink: dict):
    """A runner that records the question extraction was actually asked."""

    def runner(question, *, mode, use_llm, run, forward=None, **kw):
        sink["question"] = question
        run.answer = canned.answer
        run.evidence = canned.evidence
        run.status = canned.status
        run.exit_code = canned.exit_code
        return run

    return runner


def test_graph_path_anchors_entity_free_followup_with_llm_off():
    # Reproduces the reported failure condition: the reference-resolution LLM is
    # OFF (default), so the raw follow-up would otherwise reach the planner. The
    # deterministic anchor must fold the held entity into the extraction question.
    canned = PipelineRun(
        question="q", answer=SynthesizedAnswer(request="q", narrative="b"),
        evidence=FederatedEvidence(request="q"), status="answered", exit_code=0,
    )
    sink: dict = {}
    events = list(
        iter_conversation(
            "Please explore the execution steps involved.",
            conversation_id="c1",
            history=[
                {"role": "user", "content": "What is Creating a Rogue CA Certificate?"},
                {"role": "assistant", "content": "CAPEC-459 is ..."},
            ],
            anchor=[("CAPEC-459", "Creating a Rogue Certification Authority Certificate")],
            runner=_runner_capturing(canned, sink),
        )
    )
    assert "CAPEC-459" in sink["question"]
    context = dict(events)["context"]
    assert context["anchored"] is True
    assert context["anchor_id"] == "CAPEC-459"


def test_graph_path_does_not_anchor_standalone_question():
    canned = PipelineRun(
        question="q", answer=SynthesizedAnswer(request="q", narrative="b"),
        evidence=FederatedEvidence(request="q"), status="answered", exit_code=0,
    )
    sink: dict = {}
    events = list(
        iter_conversation(
            "What is phishing?",
            conversation_id="c1",
            history=[{"role": "assistant", "content": "CAPEC-459 is ..."}],
            anchor=[("CAPEC-459", "Creating a Rogue Certification Authority Certificate")],
            runner=_runner_capturing(canned, sink),
        )
    )
    assert "CAPEC-459" not in sink["question"]
    assert dict(events)["context"]["anchored"] is False


def test_conversation_event_carries_id():
    canned = PipelineRun(
        question="q", answer=SynthesizedAnswer(request="q", narrative="b"),
        status="answered", exit_code=0,
    )
    events = list(
        iter_conversation(
            "q", conversation_id="c-xyz", history=[],
            runner=_runner_forwarding(canned),
        )
    )
    convo = dict(events)["conversation"]
    assert convo["conversation_id"] == "c-xyz"
