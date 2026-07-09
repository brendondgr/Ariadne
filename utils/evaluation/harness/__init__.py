"""Decoupled golden-evaluation harness (run -> judge -> report).

Three independently-runnable *agents* that hand off through persisted JSONL
artifacts, so a slow live run can be judged and reported repeatedly without
re-running the pipeline:

* ``RunnerAgent`` (``run_stage``)   golden set -> ``answers.jsonl``
* ``JudgeAgent`` (``judge_stage``)  ``answers.jsonl`` -> ``judgments.jsonl``
* ``ReporterAgent`` (``report_stage``) ``judgments.jsonl`` -> ``golden-eval.{md,json}``

This is a *correctness*-oriented complement to ``utils.evaluation.score_e2e``:
the judge grades each answer against the golden expected answer (the bank
``assertions``) using the local LLM, with a deterministic id-recall/precision
backstop so a number always exists.
"""

from utils.evaluation.harness.contracts import (
    AnswerRecord,
    CorrectnessVerdict,
    read_jsonl,
    write_jsonl,
)
from utils.evaluation.harness.golden import GoldenEntry, extract_gold, load_entries

__all__ = [
    "AnswerRecord",
    "CorrectnessVerdict",
    "read_jsonl",
    "write_jsonl",
    "GoldenEntry",
    "extract_gold",
    "load_entries",
]
