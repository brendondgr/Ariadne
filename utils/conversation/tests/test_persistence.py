#!/usr/bin/env python3
"""Tests for the persistence/rehydration domain helpers."""

from __future__ import annotations

from utils.conversation.persistence import facts_from_synthesized, history_from_turns
from utils.conversation.store import TurnRecord
from utils.synthesis.contracts import (
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)


def _verified_answer():
    claims = [Claim(text="CAPEC-98 maps to T1566"), Claim(text="CAPEC-98 maps to T1598")]
    verification = VerificationReport(
        verdicts=[ClaimVerdict(verdict="supported"), ClaimVerdict(verdict="supported")]
    )
    return SynthesizedAnswer(request="q", claims=claims, verification=verification)


def test_facts_from_synthesized_returns_verified_claims():
    facts = facts_from_synthesized(_verified_answer())
    assert facts == ["CAPEC-98 maps to T1566", "CAPEC-98 maps to T1598"]


def test_facts_from_synthesized_none_and_unverified():
    assert facts_from_synthesized(None) == []
    # An unverified draft (no verification report) renders no claims -> no facts.
    draft = SynthesizedAnswer(request="q", claims=[Claim(text="unverified")])
    assert facts_from_synthesized(draft) == []


def test_facts_dedupe():
    claims = [Claim(text="same"), Claim(text="same")]
    verification = VerificationReport(
        verdicts=[ClaimVerdict(verdict="supported"), ClaimVerdict(verdict="supported")]
    )
    ans = SynthesizedAnswer(request="q", claims=claims, verification=verification)
    assert facts_from_synthesized(ans) == ["same"]


def _turn(seq, role, **kw):
    return TurnRecord(
        id=f"t{seq}", conversation_id="c", seq=seq, role=role, created_at="t", **kw
    )


def test_history_from_turns_shapes_roles():
    turns = [
        _turn(0, "user", question="which techniques map to CAPEC-98?"),
        _turn(
            1,
            "assistant",
            payload={
                "final_answer": "CAPEC-98 maps to T1566 and T1598.",
                "facts": ["CAPEC-98 maps to T1598"],
            },
        ),
    ]
    history = history_from_turns(turns)
    assert history == [
        {"role": "user", "content": "which techniques map to CAPEC-98?"},
        {
            "role": "assistant",
            "content": "CAPEC-98 maps to T1566 and T1598.",
            "facts": ["CAPEC-98 maps to T1598"],
        },
    ]


def test_history_from_turns_assistant_without_facts():
    turns = [_turn(0, "assistant", payload={"final_answer": "hi"})]
    history = history_from_turns(turns)
    assert history == [{"role": "assistant", "content": "hi"}]


def test_history_from_turns_limit_keeps_recent():
    turns = [_turn(i, "user", question=f"q{i}") for i in range(5)]
    history = history_from_turns(turns, limit=2)
    assert [h["content"] for h in history] == ["q3", "q4"]
