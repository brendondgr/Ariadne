#!/usr/bin/env python3
"""Judge agent (stage 2): ``answers.jsonl`` -> ``judgments.jsonl``.

A standalone agent that consumes the runner's persisted answers and grades each
for correctness against its golden expected answer, using the local LLM when
``--llm`` is set (with the deterministic id-recall/precision floor otherwise, and
as the fallback). It never imports the runner or reporter — only the shared
contracts and the correctness judge — so it can be re-run repeatedly against a
fixed ``answers.jsonl`` (e.g. LLM off first, then on) without touching the
pipeline.
"""

from __future__ import annotations

import dataclasses
import logging
import os
import sys

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    read_jsonl,
    write_jsonl,
)
from utils.evaluation.harness.correctness_judge import judge_answers
from utils.evaluation.llm_judge.config import EvalConfig

logger = logging.getLogger("ariadne.evaluation.harness.judge")


class JudgeAgent:
    """Grades persisted answers into correctness verdicts."""

    def __init__(
        self,
        *,
        use_llm: bool = False,
        config: EvalConfig | None = None,
        sample_size: int | None = None,
        concurrency: int = 1,
    ) -> None:
        self._use_llm = use_llm
        self._config = config or EvalConfig.from_env()
        self._sample_size = sample_size
        self._concurrency = max(1, concurrency)

    @classmethod
    def from_args(cls, args) -> "JudgeAgent":
        config = EvalConfig.from_env()
        use_llm = bool(getattr(args, "llm", False))
        if use_llm:
            config = dataclasses.replace(config, llm_enabled=True)
        return cls(
            use_llm=use_llm,
            config=config,
            sample_size=getattr(args, "judge_sample", None),
            concurrency=getattr(args, "concurrency", 1) or 1,
        )

    def run(self, records: list[AnswerRecord]) -> list[CorrectnessVerdict]:
        return judge_answers(
            records,
            config=self._config,
            use_llm=self._use_llm,
            sample_size=self._sample_size,
            concurrency=self._concurrency,
        )

    def run_files(self, answers_path: str, judgments_path: str) -> int:
        if not os.path.exists(answers_path):
            print(
                f"[judge] no answers at {answers_path} — run the 'run' stage first",
                file=sys.stderr,
            )
            return 1
        records = [AnswerRecord.from_dict(d) for d in read_jsonl(answers_path)]
        if not records:
            print(
                "[judge] answers.jsonl is empty (hermetic run) — nothing to judge",
                file=sys.stderr,
            )
            write_jsonl(judgments_path, [])
            return 0

        print(
            f"[judge] grading {len(records)} answers — LLM: "
            f"{'ON' if self._use_llm else 'OFF (deterministic backstop)'}"
            + (
                f", model={self._config.llm_model} @ {self._config.llm_base_url}"
                f", concurrency={self._concurrency}"
                if self._use_llm
                else ""
            ),
            file=sys.stderr,
        )
        verdicts = self.run(records)
        n = write_jsonl(judgments_path, verdicts)

        labels = {"correct": 0, "partial": 0, "incorrect": 0}
        llm_covered = 0
        for v in verdicts:
            labels[v.label] = labels.get(v.label, 0) + 1
            if v.source == "llm":
                llm_covered += 1
        print(
            f"[judge] wrote {n} verdicts to {judgments_path} — "
            f"correct={labels['correct']} partial={labels['partial']} "
            f"incorrect={labels['incorrect']}; llm-graded={llm_covered}",
            file=sys.stderr,
        )
        return 0
