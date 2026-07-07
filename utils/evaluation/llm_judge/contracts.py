#!/usr/bin/env python3
"""Contracts for the LLM evaluator: per-answer judge verdicts and roll-ups.

The judge scores a *verified* ``SynthesizedAnswer`` on the four dimensions the
proposal commits to — faithfulness, groundedness, evidence sufficiency, and
unsupported-claim rate. Every score is a float in ``[0, 1]``. ``source`` records
which judge produced the verdict (``deterministic`` proxy or ``llm``) so the
report can label non-reproducible LLM numbers distinctly from the reproducible
proxy.

Pure JSON-serialisable dataclasses, matching ``utils.synthesis.contracts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The scored dimensions, in report order. ``unsupported_claim_rate`` is always
# taken deterministically from the verifier; the other three come from whichever
# judge ran.
DIMENSIONS = ("faithfulness", "groundedness", "evidence_sufficiency")


@dataclass(frozen=True)
class JudgeVerdict:
    """One judge's ruling on one synthesized answer."""

    question_id: str
    source: str  # "deterministic" | "llm"
    faithfulness: float = 0.0
    groundedness: float = 0.0
    evidence_sufficiency: float = 0.0
    unsupported_claim_rate: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "source": self.source,
            "faithfulness": round(self.faithfulness, 4),
            "groundedness": round(self.groundedness, 4),
            "evidence_sufficiency": round(self.evidence_sufficiency, 4),
            "unsupported_claim_rate": round(self.unsupported_claim_rate, 4),
            "reasons": list(self.reasons),
        }


@dataclass
class JudgeReport:
    """Per-answer verdicts plus the mean of each dimension across a run."""

    verdicts: list[JudgeVerdict] = field(default_factory=list)
    # Which judge produced the aggregate: "deterministic" when the LLM was off
    # or every LLM call fell back, "llm" when at least one real LLM verdict
    # contributed, "mixed" otherwise.
    source: str = "deterministic"
    # How many answers a real LLM verdict covered (0 when off / all fell back).
    llm_covered: int = 0

    def _mean(self, attr: str) -> float:
        if not self.verdicts:
            return 0.0
        return sum(getattr(v, attr) for v in self.verdicts) / len(self.verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "llm_covered": self.llm_covered,
            "answers_scored": len(self.verdicts),
            "mean_faithfulness": round(self._mean("faithfulness"), 4),
            "mean_groundedness": round(self._mean("groundedness"), 4),
            "mean_evidence_sufficiency": round(
                self._mean("evidence_sufficiency"), 4
            ),
            "mean_unsupported_claim_rate": round(
                self._mean("unsupported_claim_rate"), 4
            ),
            "verdicts": [v.to_dict() for v in self.verdicts],
        }
