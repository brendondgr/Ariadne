"""LLM evaluator (LLM-as-judge) for Ariadne (Wk 12-13).

The proposal commits to an LLM evaluator estimating faithfulness, groundedness,
evidence sufficiency, and unsupported-claim rate. This package provides it as an
**opt-in** layer on top of the deterministic verifier:

* ``DeterministicJudge`` scores every answer with mechanical checks against the
  evidence — always available, fully reproducible, and the fallback the LLM
  path degrades to. It keeps the ``utils.evaluation`` "no metric depends on an
  LLM judge" invariant intact when the LLM is off (the default).
* ``OpenAICompatibleJudge`` estimates the three qualitative dimensions via a
  configurable OpenAI-compatible endpoint (``EVAL_LLM_*``), mirroring the
  synthesis composer exactly. Its numbers are labeled non-reproducible.

``judge_run`` is the single batch entry point; ``select_judge`` wires the hybrid.
"""

from .config import EvalConfig
from .contracts import JudgeReport, JudgeVerdict
from .deterministic_judge import DeterministicJudge
from .factory import HybridJudge, judge_run, select_judge
from .llm_judge import JudgeUnavailable, OpenAICompatibleJudge

__all__ = [
    "EvalConfig",
    "JudgeReport",
    "JudgeVerdict",
    "DeterministicJudge",
    "OpenAICompatibleJudge",
    "JudgeUnavailable",
    "HybridJudge",
    "select_judge",
    "judge_run",
]
