#!/usr/bin/env python3
"""The verification pass: every claim must be backed by a retrieved record.

Always deterministic — the guard must not itself trust the model it audits.
``verify_answer`` walks the draft claim by claim and rules each one
``supported`` or ``unsupported``:

1. **Cited** — a claim with no citations is unsupported outright; the
   composers are required to cite.
2. **Resolvable** — every citation must resolve to a record that was actually
   retrieved from that source (id-normalized; ``record_id`` checked when the
   citation carries one). Citing a source that returned nothing, or a record
   that does not exist, is the fabrication class this layer exists to catch.
3. **Grounded** — every identifier the claim asserts (``entity_ids``) must
   appear in the id pool of the records it cites (primary ids, join values,
   related ids).
4. **Correlated** — a ``correlation`` claim's identifiers must additionally be
   backed by the federation's join index across more than one source.

Unsupported claims are *cut from the rendered prose and kept flagged* in the
verification report — auditable, never silently shown as fact.

The pass also enforces abstention: for every sub-question whose specialist ran
cleanly and returned zero records, the verified answer carries an
``Abstention`` with the executed query attached as proof. Missing abstentions
are repaired deterministically (they are fully derivable from evidence), wrong
queries are replaced with the executed one, and abstentions claimed against
sub-questions that actually returned evidence are removed — an answer may not
hide evidence behind a false "the sources don't establish this".
"""

from __future__ import annotations

from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.federation import FederatedEvidence

from .composer import abstention_for
from .contracts import (
    Abstention,
    Citation,
    Claim,
    ClaimVerdict,
    SynthesizedAnswer,
    VerificationReport,
)
from .grounding import id_pool, normalize_id


def _records_by_source(evidence: FederatedEvidence) -> dict[str, list[EvidenceRecord]]:
    out: dict[str, list[EvidenceRecord]] = {}
    for result in evidence.results:
        out.setdefault(result.task.source, []).extend(result.records)
    return out


def _resolve_citation(
    citation: Citation, by_source: dict[str, list[EvidenceRecord]]
) -> tuple[list[EvidenceRecord], str | None]:
    """Return the records a citation resolves to, or a failure reason."""
    records = by_source.get(citation.source)
    if not records:
        return [], (
            f"citation ({citation.source}, {citation.primary_id}) points at a "
            f"source that returned no records"
        )
    want = normalize_id(citation.primary_id)
    matched = [r for r in records if normalize_id(r.primary_id) == want]
    if citation.record_id:
        narrowed = [
            r
            for r in matched
            if r.provenance is not None and r.provenance.record_id == citation.record_id
        ]
        if narrowed:
            matched = narrowed
        # A stale/wrong record_id on an otherwise-real primary_id keeps the
        # primary_id match: the record was retrieved; the pointer is imprecise,
        # not fabricated.
    if not matched:
        return [], (
            f"citation ({citation.source}, {citation.primary_id}) does not match "
            f"any retrieved record"
        )
    return matched, None


def _verify_claim(
    claim: Claim,
    by_source: dict[str, list[EvidenceRecord]],
    cross_values: set[str],
) -> ClaimVerdict:
    reasons: list[str] = []

    if not claim.citations:
        return ClaimVerdict(
            verdict="unsupported",
            reasons=["uncited claim: no evidence records were cited"],
        )

    cited_records: list[EvidenceRecord] = []
    for citation in claim.citations:
        matched, failure = _resolve_citation(citation, by_source)
        if failure:
            reasons.append(failure)
        else:
            cited_records.extend(matched)

    if not reasons:
        pool = id_pool(cited_records)
        for entity in claim.entity_ids:
            if normalize_id(entity) not in pool:
                reasons.append(
                    f"entity {entity} is not grounded in the cited records"
                )

    if claim.kind == "correlation" and not reasons:
        for entity in claim.entity_ids:
            if normalize_id(entity) not in cross_values:
                reasons.append(
                    f"correlation on {entity} is not backed by the cross-source "
                    f"join index"
                )

    if reasons:
        return ClaimVerdict(verdict="unsupported", reasons=reasons)
    return ClaimVerdict(verdict="supported")


def _empty_ok_results(evidence: FederatedEvidence) -> list[SpecialistResult]:
    return [r for r in evidence.results if r.ok and not r.records]


def _enforce_abstentions(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> tuple[list[Abstention], int]:
    """Rebuild the abstention set against evidence; count every repair."""
    supplied = {a.sub_question_id: a for a in answer.abstentions}
    repairs = 0
    enforced: list[Abstention] = []

    for result in _empty_ok_results(evidence):
        sq = result.task.sub_question_id
        prior = supplied.pop(sq, None)
        if prior is None:
            repairs += 1
            enforced.append(abstention_for(result))
            continue
        if prior.query != result.query or prior.source != result.task.source:
            repairs += 1
            prior = Abstention(
                sub_question_id=sq,
                source=result.task.source,
                statement=prior.statement,
                query=result.query,
            )
        enforced.append(prior)

    # Whatever is left claims an absence for a sub-question that actually
    # produced evidence (or never ran clean) — a false abstention hides
    # evidence, so it is removed and counted as a repair.
    repairs += len(supplied)
    return enforced, repairs


def verify_answer(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> SynthesizedAnswer:
    """Attach the verification report and the enforced abstentions in place."""
    by_source = _records_by_source(evidence)
    cross_values = {normalize_id(v) for v in evidence.cross_source_join_values()}

    verdicts = [
        _verify_claim(claim, by_source, cross_values) for claim in answer.claims
    ]
    abstentions, repairs = _enforce_abstentions(answer, evidence)

    answer.abstentions = abstentions
    answer.verification = VerificationReport(
        verdicts=verdicts, repaired_abstentions=repairs
    )
    return answer
