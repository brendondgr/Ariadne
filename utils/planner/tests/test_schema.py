#!/usr/bin/env python3

from __future__ import annotations

from utils.planner.schema import (
    JoinDeclaration,
    Limits,
    Plan,
    SubQuestion,
    UnsupportedPart,
)


def test_limits_present_requires_all_positive() -> None:
    assert Limits(3, 1000, 5000).is_present()
    assert not Limits(0, 1000, 5000).is_present()
    assert not Limits().is_present()


def test_plan_roundtrip_to_from_dict() -> None:
    plan = Plan(
        request="example",
        sub_questions=[
            SubQuestion(
                id="q1",
                source="capec",
                text="find credential-theft patterns",
                entities=["AttackPattern", "MAPS_TO"],
                limits=Limits(3, 1000, 5000),
                join_key="attack-technique-id",
                rationale="CAPEC holds attack patterns",
            )
        ],
        joins=[JoinDeclaration(key="attack-technique-id", sources=["capec", "attack"], on="technique id")],
        unsupported=[UnsupportedPart(description="threat intel feed", reason="no live source")],
        assumptions=["interpreted 'credential theft' as a keyword filter"],
        rationale="routed by card coverage",
        partial=True,
    )
    restored = Plan.from_dict(plan.to_dict())
    assert restored.request == "example"
    assert restored.sub_questions[0].limits == Limits(3, 1000, 5000)
    assert restored.joins[0].key == "attack-technique-id"
    assert restored.unsupported[0].reason == "no live source"
    assert restored.partial is True
    assert restored.target_sources() == {"capec"}


def test_from_dict_missing_limits_defaults_to_zero() -> None:
    sq = SubQuestion.from_dict({"id": "q1", "source": "capec", "entities": ["AttackPattern"]})
    assert sq.limits == Limits()
    assert not sq.limits.is_present()


def test_empty_plan_detected() -> None:
    assert Plan(request="x").is_empty()
    assert not Plan(request="x", unsupported=[UnsupportedPart("a", "b")]).is_empty()
