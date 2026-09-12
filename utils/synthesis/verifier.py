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

import re
from dataclasses import replace

from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.federation import FederatedEvidence

from .composer import abstention_for
from .config import SynthesisConfig
from .contracts import (
    Abstention,
    Citation,
    Claim,
    ClaimVerdict,
    SynthesisEdge,
    SynthesizedAnswer,
    VerificationReport,
)
from .grounding import id_pool, normalize_id
from .reconcile import conflicted_values, detect_conflicts

_CAPEC_RE = re.compile(r"^capec-\d+$", re.IGNORECASE)
_TECHNIQUE_RE = re.compile(r"^t\d{4}(?:\.\d{3})?$", re.IGNORECASE)
_MITIGATION_RE = re.compile(r"^m\d{4}$", re.IGNORECASE)


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
    config: SynthesisConfig | None = None,
    evidence: FederatedEvidence | None = None,
) -> ClaimVerdict:
    """Rule on one claim through four gates, any of which may be ablated.

    On the default path (every gate on) this is exactly the original cascade and
    ``waived`` is always empty. When a gate is disabled its objection is routed
    to ``waived`` instead of ``reasons``, so it no longer makes the claim
    unsupported but is still counted — which is what makes the ablation a diff
    rather than a re-derivation (EXP-2026-08-014).

    The short-circuits are preserved exactly. A gate that is *disabled* stops
    short-circuiting too: with `resolvable` off, an unresolvable citation no
    longer suppresses the grounding check, so grounding is evaluated against the
    records that did resolve. That is the honest reading of "this gate is not
    there" — the downstream gate sees what it would see in a system built
    without the disabled one.
    """
    cfg = config or SynthesisConfig.from_env()
    reasons: list[str] = []
    waived: list[str] = []

    def object_to(gate_on: bool, reason: str) -> None:
        (reasons if gate_on else waived).append(reason)

    if not claim.citations:
        object_to(cfg.gate_cited, "uncited claim: no evidence records were cited")
        if cfg.gate_cited:
            return ClaimVerdict(verdict="unsupported", reasons=reasons)
        # `cited` ablated: an uncited claim has no records to ground against, so
        # every later gate would fire spuriously. Waive it wholesale and say so.
        return ClaimVerdict(verdict="supported", waived=tuple(waived))

    cited_records: list[EvidenceRecord] = []
    for citation in claim.citations:
        matched, failure = _resolve_citation(citation, by_source)
        if failure:
            object_to(cfg.gate_resolvable, failure)
        else:
            cited_records.extend(matched)

    if not reasons:
        pool = id_pool(cited_records)
        for entity in claim.entity_ids:
            if normalize_id(entity) not in pool:
                object_to(
                    cfg.gate_grounded,
                    f"entity {entity} is not grounded in the cited records",
                )

    if claim.kind == "absence" and not reasons:
        # An absence claim asserts that nothing is there, so its proof is the
        # query rather than a record: admitted only when the result it came from
        # RAN CLEAN and returned no rows for the requested relation. Without this
        # the composer could assert "X has no execution steps" off a failed
        # lookup, which is the one way a grounded system can state a falsehood
        # with full provenance.
        result = _result_for(claim, evidence) if evidence is not None else None
        if result is None:
            object_to(cfg.gate_grounded, "absence claim has no matching result")
        elif not result.ok or result.error:
            object_to(
                cfg.gate_grounded,
                "absence claim rests on a query that did not run clean",
            )
        elif not _absence_holds(result, claim):
            object_to(
                cfg.gate_grounded,
                "absence claim contradicted by the evidence: the requested "
                "relation has related records or a non-zero facet count",
            )

    if claim.kind == "correlation" and not reasons:
        for entity in claim.entity_ids:
            if normalize_id(entity) not in cross_values:
                object_to(
                    cfg.gate_correlated,
                    f"correlation on {entity} is not backed by the cross-source "
                    f"join index",
                )

    if reasons:
        return ClaimVerdict(
            verdict="unsupported", reasons=reasons, waived=tuple(waived)
        )
    return ClaimVerdict(verdict="supported", waived=tuple(waived))


def _related_entries(record: EvidenceRecord) -> list[dict]:
    return [rel for rel in (record.related or ()) if isinstance(rel, dict)]


def _absence_holds(result: SpecialistResult, claim: Claim) -> bool:
    """Re-derive the composer's emptiness test, independently of the claim text.

    The verifier must not take the composer's word for which relation was asked
    about, so it reads every relation the claim could be about off the result's
    own task and checks the same two conditions the composer did: no related
    entry of that relation, and no facet for it with a non-zero count.
    """
    from .composer import _relation_is_empty

    relations = [
        entity
        for entity in (result.task.entities or ())
        if _relation_mentioned(entity, claim.text)
    ]
    if not relations:
        # Nothing in the task names a relation this claim could be about, so the
        # narrow test cannot run; fall back to the strict one.
        return not any(_related_entries(record) for record in result.records)
    return all(_relation_is_empty(result, relation) for relation in relations)


def _relation_mentioned(entity: str, text: str) -> bool:
    """Is ``entity`` the relation this absence claim names, in words?"""
    words = [w.lower() for w in (entity or "").replace("_", " ").split() if w]
    return bool(words) and all(word in (text or "").lower() for word in words)


def _result_for(claim: Claim, evidence: FederatedEvidence) -> SpecialistResult | None:
    """The result this claim was composed from, by sub-question id."""
    for result in evidence.results:
        if result.task.sub_question_id == claim.sub_question_id:
            return result
    return None


def _empty_ok_results(evidence: FederatedEvidence) -> list[SpecialistResult]:
    """Results that must carry an abstention: nothing found, or nothing *joined*.

    "No records" was the whole test until the cross-source bridges became outer
    joins. An outer join returns the anchor with an empty mapping list, so a
    pattern that maps to no ATT&CK technique now produces a record — and the
    producer stopped abstaining, which silently deleted the one statement the
    question was actually asking for. A sub-question that declared a join key
    and came back with no join values is an honest empty *for that join*,
    whatever else its records describe.
    """
    results: list[SpecialistResult] = []
    for result in evidence.results:
        if not result.ok:
            continue
        if not result.records:
            results.append(result)
            continue
        if result.task.join_key and not any(
            record.join_values for record in result.records
        ):
            results.append(result)
    return results


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


def _supported_id_pool(
    claims: list[Claim], verdicts: list[ClaimVerdict]
) -> set[str]:
    """Normalized ids that appear in a *supported* claim — the only endpoints an
    edge may connect. A cut claim's ids never enter the pool, so any edge that
    depended on it is pruned."""
    pool: set[str] = set()
    for claim, verdict in zip(claims, verdicts):
        if not verdict.supported:
            continue
        for citation in claim.citations:
            pool.add(normalize_id(citation.primary_id))
        for entity in claim.entity_ids:
            pool.add(normalize_id(entity))
    return pool


def _synthesis_edges(
    evidence: FederatedEvidence, supported_ids: set[str]
) -> list[SynthesisEdge]:
    """Provenance-exact CAPEC→ATT&CK edges from the cross-source join index.

    A join value present under more than one source means the CAPEC pattern and
    the ATT&CK technique that both carry it genuinely map to each other — no
    cross-product guessing. Each edge is kept only when *both* endpoints survive
    in a supported claim (``supported_ids``), so the plot never shows topology
    the verifier cut.
    """
    join_index = evidence.join_index()
    edges: list[SynthesisEdge] = []
    seen: set[tuple[str, str]] = set()

    for value in evidence.cross_source_join_values():
        entries = join_index.get(value, [])
        capec_ids = [e["primary_id"] for e in entries if _CAPEC_RE.match(normalize_id(e["primary_id"]))]
        technique_ids = [
            e["primary_id"] for e in entries if _TECHNIQUE_RE.match(normalize_id(e["primary_id"]))
        ]
        # The shared join value is itself the ATT&CK id even when no record's
        # primary_id equals it — use it as a target too.
        if _TECHNIQUE_RE.match(normalize_id(value)):
            if normalize_id(value) not in {normalize_id(t) for t in technique_ids}:
                technique_ids.append(value)

        for capec in capec_ids:
            for technique in technique_ids:
                nc, nt = normalize_id(capec), normalize_id(technique)
                if nc == nt or nc not in supported_ids or nt not in supported_ids:
                    continue
                if (nc, nt) in seen:
                    continue
                seen.add((nc, nt))
                edges.append(SynthesisEdge(source_id=capec, target_id=technique, rel="mapsTo"))

    return edges


def _mitigation_edges(
    evidence: FederatedEvidence, supported_ids: set[str]
) -> list[SynthesisEdge]:
    """Provenance-exact technique→mitigation edges from the records themselves.

    A technique record's ``related`` mitigation entries are the graph's real
    ``MITIGATES`` relationships, retrieved by the executed query — not a
    co-citation guess. The pruning rule deliberately differs from the mapsTo
    both-endpoints rule: the *technique* must survive in a supported claim, but
    the mitigation id need not — the deterministic composer never asserts M-ids
    in ``entity_ids``, so requiring both endpoints would starve these edges to
    zero. The mitigation is grounded by the very record asserting the
    relationship, the same rule ``grounding.id_pool`` applies to related ids.
    """
    edges: list[SynthesisEdge] = []
    seen: set[tuple[str, str]] = set()

    for result in evidence.results:
        for record in result.records:
            technique = record.primary_id
            nt = normalize_id(technique)
            if not _TECHNIQUE_RE.match(nt) or nt not in supported_ids:
                continue
            for entry in record.related:
                raw = entry.get("id") or entry.get("entry_id")
                if not raw:
                    continue
                mitigation = str(raw)
                nm = normalize_id(mitigation)
                if not _MITIGATION_RE.match(nm) or (nt, nm) in seen:
                    continue
                seen.add((nt, nm))
                edges.append(
                    SynthesisEdge(source_id=technique, target_id=mitigation, rel="mitigatedBy")
                )

    return edges


def _claim_ids(claim: Claim) -> set[str]:
    """Every normalized id a claim asserts or cites — the surface a conflict on
    a shared join value can contest."""
    ids = {normalize_id(c.primary_id) for c in claim.citations}
    ids.update(normalize_id(e) for e in claim.entity_ids)
    return ids


def _mark_contested(
    verdict: ClaimVerdict, claim: Claim, conflicted: set[str]
) -> ClaimVerdict:
    """Flag (never cut) a supported claim that touches a conflicted join value.

    Only supported claims are annotated — a cut claim is already off the trust
    surface, so contesting it would be noise."""
    if not verdict.supported or not conflicted:
        return verdict
    touched = tuple(sorted(_claim_ids(claim) & conflicted))
    if not touched:
        return verdict
    return replace(verdict, contested=touched)


def verify_answer(
    answer: SynthesizedAnswer,
    evidence: FederatedEvidence,
    config: SynthesisConfig | None = None,
) -> SynthesizedAnswer:
    """Attach the verification report and the enforced abstentions in place.

    ``config`` is resolved from the environment when not supplied, so every
    existing caller is unchanged and every gate defaults on.
    """
    cfg = config or SynthesisConfig.from_env()
    by_source = _records_by_source(evidence)
    cross_values = {normalize_id(v) for v in evidence.cross_source_join_values()}

    verdicts = [
        _verify_claim(claim, by_source, cross_values, cfg, evidence)
        for claim in answer.claims
    ]

    # Consistency axis: reconcile corroborating records against each other, then
    # flag (never cut) the supported claims that assert a contested id.
    conflicts = detect_conflicts(evidence)
    conflicted = conflicted_values(conflicts)
    verdicts = [
        _mark_contested(v, claim, conflicted)
        for v, claim in zip(verdicts, answer.claims)
    ]

    abstentions, repairs = _enforce_abstentions(answer, evidence)

    answer.abstentions = abstentions
    answer.verification = VerificationReport(
        verdicts=verdicts, repaired_abstentions=repairs, conflicts=conflicts
    )
    supported_ids = _supported_id_pool(answer.claims, verdicts)
    answer.edges = _synthesis_edges(evidence, supported_ids) + _mitigation_edges(
        evidence, supported_ids
    )
    return answer
