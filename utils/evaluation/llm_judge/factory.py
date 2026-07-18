#!/usr/bin/env python3
"""Judge selection and the one-call run entry.

Mirrors the synthesis factory: when the LLM judge is enabled a ``HybridJudge``
tries the OpenAI-compatible endpoint and falls back to the deterministic proxy
on any failure. ``judge_run`` scores a batch of answers into one ``JudgeReport``
— when the LLM is enabled it is applied to at most ``config.sample_size``
answers (cost control), and every remaining answer is scored by the
deterministic proxy so the report always covers the whole batch.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer

from .config import EvalConfig
from .contracts import JudgeReport, JudgeVerdict
from .deterministic_judge import DeterministicJudge
from .llm_judge import JudgeUnavailable, OpenAICompatibleJudge

logger = logging.getLogger("ariadne.evaluation.judge.factory")


class Judge(Protocol):
    """Anything that scores one answer into a ``JudgeVerdict``."""

    name: str

    def judge(
        self,
        question_id: str,
        answer: SynthesizedAnswer,
        evidence: FederatedEvidence,
    ) -> JudgeVerdict: ...


class HybridJudge:
    """Tries a primary judge, falling back to the proxy on any failure."""

    name = "hybrid"

    def __init__(self, primary: Judge, fallback: Judge) -> None:
        self._primary = primary
        self._fallback = fallback
        self.last_used: str = ""

    def judge(
        self,
        question_id: str,
        answer: SynthesizedAnswer,
        evidence: FederatedEvidence,
    ) -> JudgeVerdict:
        try:
            verdict = self._primary.judge(question_id, answer, evidence)
            self.last_used = self._primary.name
            return verdict
        except JudgeUnavailable as exc:
            logger.info(
                "LLM judge unavailable (%s); using deterministic proxy", exc
            )
            self.last_used = self._fallback.name
            return self._fallback.judge(question_id, answer, evidence)


def select_judge(config: EvalConfig) -> Judge:
    """Return the configured judge (hybrid LLM when enabled, else proxy)."""
    deterministic = DeterministicJudge()
    if config.llm_enabled:
        logger.info(
            "LLM judge enabled: %s (model=%s)", config.llm_base_url, config.llm_model
        )
        return HybridJudge(OpenAICompatibleJudge(config), deterministic)
    return deterministic


def judge_run(
    items: list[tuple[str, SynthesizedAnswer, FederatedEvidence]],
    config: EvalConfig | None = None,
    *,
    judge: Judge | None = None,
) -> JudgeReport:
    """Score a batch of (question_id, answer, evidence) into one report."""
    config = config or EvalConfig.from_env()
    judge = judge or select_judge(config)
    proxy = DeterministicJudge()

    # Only the first ``sample_size`` answers get the (costly) LLM judge when
    # enabled; the rest fall to the reproducible proxy. The LLM calls are
    # independent, so they run concurrently while verdicts are placed back by
    # index — the emitted report is identical to the sequential path.
    verdicts: list[JudgeVerdict | None] = [None] * len(items)
    llm_indices: list[int] = []
    for index, (question_id, answer, evidence) in enumerate(items):
        if config.llm_enabled and index < config.sample_size:
            llm_indices.append(index)
        else:
            verdicts[index] = proxy.judge(question_id, answer, evidence)

    def _run_llm(index: int) -> JudgeVerdict:
        question_id, answer, evidence = items[index]
        return judge.judge(question_id, answer, evidence)

    workers = max(1, min(config.judge_workers, len(llm_indices)))
    if workers == 1:
        for index in llm_indices:
            verdicts[index] = _run_llm(index)
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for index, verdict in zip(
                llm_indices, pool.map(_run_llm, llm_indices)
            ):
                verdicts[index] = verdict

    # Placeholder ``None`` slots are all filled by this point.
    verdicts = [v for v in verdicts if v is not None]
    llm_covered = sum(1 for v in verdicts if v.source == "llm")

    if llm_covered == 0:
        source = "deterministic"
    elif llm_covered == len(verdicts):
        source = "llm"
    else:
        source = "mixed"
    return JudgeReport(verdicts=verdicts, source=source, llm_covered=llm_covered)
