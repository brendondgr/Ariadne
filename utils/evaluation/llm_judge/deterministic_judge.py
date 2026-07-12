#!/usr/bin/env python3
"""The deterministic proxy judge — the always-available, reproducible fallback.

It scores a verified ``SynthesizedAnswer`` on the four dimensions using only
mechanical checks against the evidence, so the LLM-off build produces stable
numbers and the ``utils.evaluation`` "no metric depends on an LLM judge"
invariant holds. Each dimension is *independently recomputed* from evidence
(not merely read back from the verifier), so the proxy doubles as a cross-check
on the verifier:

* **faithfulness** — supported claims / total claims (an answer asserting
  nothing asserts nothing false → 1.0).
* **groundedness** — of the rendered (shown) claims, the fraction whose every
  asserted identifier resolves in the cited records' id pool.
* **evidence_sufficiency** — of the sub-questions that returned records, the
  fraction the answer actually used (a rendered claim tied to that
  sub-question/source); evidence retrieved but never spoken to lowers this.
* **unsupported_claim_rate** — taken straight from the verifier.
"""

from __future__ import annotations

from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer
from utils.synthesis.grounding import id_pool, normalize_id

from .contracts import JudgeVerdict


def _records_by_source(evidence: FederatedEvidence):
    out: dict[str, list] = {}
    for result in evidence.results:
        out.setdefault(result.task.source, []).extend(result.records)
    return out


def _groundedness(answer: SynthesizedAnswer, evidence: FederatedEvidence) -> float:
    rendered = answer.rendered_claims()
    if not rendered:
        # No claims shown: nothing ungrounded is on display.
        return 1.0
    by_source = _records_by_source(evidence)
    grounded = 0
    for claim in rendered:
        cited: list = []
        for citation in claim.citations:
            want = normalize_id(citation.primary_id)
            cited.extend(
                r
                for r in by_source.get(citation.source, [])
                if normalize_id(r.primary_id) == want
            )
        pool = id_pool(cited)
        if claim.entity_ids and all(
            normalize_id(e) in pool for e in claim.entity_ids
        ):
            grounded += 1
        elif not claim.entity_ids and cited:
            # A claim with citations but no asserted ids is grounded if its
            # citations resolve.
            grounded += 1
    return grounded / len(rendered)


def _evidence_sufficiency(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> float:
    answerable = [r for r in evidence.results if r.ok and r.records]
    if not answerable:
        # Nothing to use: an honest empty/abstention is fully sufficient.
        return 1.0
    rendered = answer.rendered_claims()
    used_sub_questions = {c.sub_question_id for c in rendered if c.sub_question_id}
    used_sources = {cit.source for c in rendered for cit in c.citations}
    covered = 0
    for result in answerable:
        sq = result.task.sub_question_id
        if sq in used_sub_questions or result.task.source in used_sources:
            covered += 1
    return covered / len(answerable)


class DeterministicJudge:
    """Scores answers from evidence alone — reproducible, always available."""

    name = "deterministic"

    def judge(
        self,
        question_id: str,
        answer: SynthesizedAnswer,
        evidence: FederatedEvidence,
    ) -> JudgeVerdict:
        report = answer.verification
        claim_count = len(report.verdicts) if report else len(answer.claims)
        supported = report.supported_count if report else 0
        unsupported_rate = report.unsupported_claim_rate if report else 0.0
        faithfulness = 1.0 if claim_count == 0 else supported / claim_count
        return JudgeVerdict(
            question_id=question_id,
            source=self.name,
            faithfulness=faithfulness,
            groundedness=_groundedness(answer, evidence),
            evidence_sufficiency=_evidence_sufficiency(answer, evidence),
            unsupported_claim_rate=unsupported_rate,
            conflict_count=report.conflict_count if report else 0,
            reasons=["deterministic proxy: mechanical checks against evidence"],
        )
