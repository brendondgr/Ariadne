#!/usr/bin/env python3
"""Hermetic tests for the LLM judge path — no network.

Exercises the pure prompt/parse helpers, the hybrid fallback to the proxy on
``JudgeUnavailable``, and that an enabled judge marks its verdicts ``llm`` and
keeps the deterministic unsupported-claim rate.
"""

from __future__ import annotations

from utils.evaluation.llm_judge import (
    DeterministicJudge,
    HybridJudge,
    JudgeUnavailable,
    judge_run,
)
from utils.evaluation.llm_judge.config import EvalConfig
from utils.evaluation.llm_judge.llm_judge import (
    build_messages,
    extract_json_object,
    parse_verdict,
)
from utils.synthesis.contracts import Citation, Claim, SynthesizedAnswer
from utils.synthesis.tests._fixtures import make_evidence, make_record, make_result
from utils.synthesis.verifier import verify_answer


def _answer_and_evidence():
    record = make_record(
        "T1047", related=[{"id": "M1038", "name": "Execution Prevention"}]
    )
    evidence = make_evidence([make_result(records=[record])])
    claim = Claim(
        text="T1047 is mitigated by M1038.",
        citations=(Citation(source="attack", primary_id="T1047"),),
        entity_ids=("T1047", "M1038"),
    )
    answer = verify_answer(SynthesizedAnswer(request="q", claims=[claim]), evidence)
    return answer, evidence


class _StubLLM:
    name = "llm"

    def __init__(self, verdict=None, *, fail=False):
        self._verdict = verdict
        self._fail = fail

    def judge(self, question_id, answer, evidence):
        if self._fail:
            raise JudgeUnavailable("stub endpoint down")
        return self._verdict


def test_build_messages_is_pure_and_lists_claims():
    answer, evidence = _answer_and_evidence()
    messages = build_messages(answer, evidence)
    assert messages[0]["role"] == "system"
    user = messages[1]["content"]
    assert "T1047" in user
    assert "EVIDENCE RECORDS" in user


def test_extract_json_object_ignores_prose_and_fences():
    text = 'Sure!\n```json\n{"faithfulness": 0.9, "groundedness": 1.0}\n```'
    data = extract_json_object(text)
    assert data["faithfulness"] == 0.9


def test_parse_verdict_clamps_and_keeps_deterministic_rate():
    data = {
        "faithfulness": 1.4,          # over-range → clamped to 1.0
        "groundedness": -0.2,         # under-range → clamped to 0.0
        "evidence_sufficiency": 0.75,
        "reasons": "looks solid",
    }
    verdict = parse_verdict(data, "q1", unsupported_claim_rate=0.25)
    assert verdict.source == "llm"
    assert verdict.faithfulness == 1.0
    assert verdict.groundedness == 0.0
    assert verdict.evidence_sufficiency == 0.75
    assert verdict.unsupported_claim_rate == 0.25  # never from the LLM
    assert verdict.reasons == ["looks solid"]


def test_hybrid_falls_back_to_proxy_when_llm_unavailable():
    answer, evidence = _answer_and_evidence()
    hybrid = HybridJudge(_StubLLM(fail=True), DeterministicJudge())
    verdict = hybrid.judge("q1", answer, evidence)
    assert verdict.source == "deterministic"
    assert hybrid.last_used == "deterministic"


def test_judge_run_marks_llm_source_when_enabled():
    answer, evidence = _answer_and_evidence()
    stub_verdict = parse_verdict(
        {"faithfulness": 0.8, "groundedness": 0.9, "evidence_sufficiency": 0.7},
        "q1",
        0.0,
    )
    config = EvalConfig(llm_enabled=True, sample_size=5)
    report = judge_run(
        [("q1", answer, evidence)], config, judge=_StubLLM(verdict=stub_verdict)
    )
    assert report.source == "llm"
    assert report.llm_covered == 1
    assert report.to_dict()["mean_groundedness"] == 0.9


def test_judge_run_samples_then_proxies_the_rest():
    answer, evidence = _answer_and_evidence()
    stub_verdict = parse_verdict(
        {"faithfulness": 0.8, "groundedness": 0.8, "evidence_sufficiency": 0.8},
        "x",
        0.0,
    )
    config = EvalConfig(llm_enabled=True, sample_size=1)
    items = [("q1", answer, evidence), ("q2", answer, evidence)]
    report = judge_run(items, config, judge=_StubLLM(verdict=stub_verdict))
    assert report.llm_covered == 1          # only the first sampled
    assert report.source == "mixed"
    sources = [v.source for v in report.verdicts]
    assert sources == ["llm", "deterministic"]
