#!/usr/bin/env python3
"""End-to-end (whole-pipeline) accuracy scoring — the Wk 12-13 e2e metrics.

Component evaluation scores the planner and specialists in isolation. This
module scores the *assembled* pipeline against the four ``goals.md`` end-to-end
metrics, driving the committed golden catalogue through the same federation +
synthesis path the live golden suites trust:

* **cross-source answer accuracy** — the live cross-source join values vs the
  snapshot-derived ``must_correlate`` (exact-set-match + precision/recall/F1);
  negatives must surface no correlation.
* **CAPEC→ATT&CK mapping recall** — of the resolvable technique ids a CAPEC
  pattern maps to, the fraction the pipeline actually surfaced.
* **provenance correctness** — every citation under a rendered claim resolves to
  a retrieved record whose provenance is complete and whose recorded query is
  the query that was executed; abstentions carry a truthful proof.
* **analyst inspectability** — every rendered claim is citation-backed and its
  claim→record→query chain is reconstructable, and every abstention's proof is
  complete.

The per-answer scoring functions are pure over ``(entry, evidence, answer)`` so
they are tested hermetically with stubbed pipeline output; the live drivers at
the bottom build the real router/specialists and are exercised when the Docker
stack is up. The LLM judge (deterministic proxy by default) scores the same
answers for faithfulness/groundedness/evidence-sufficiency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from utils.evaluation.llm_judge import EvalConfig, JudgeReport, judge_run
from utils.evaluation.stats import wilson_interval
from utils.specialists.contracts import EvidenceRecord, SpecialistResult
from utils.specialists.federation import FederatedEvidence
from utils.synthesis.contracts import SynthesizedAnswer
from utils.synthesis.grounding import id_pool, normalize_id

# Provenance fields that must all be present for a record to count as fully
# provenanced (analyst can trace the claim to a source, backend, and query).
_PROVENANCE_FIELDS = ("source", "dataset", "backend", "query", "timestamp")


# ---------------------------------------------------------------------------
# per-entry metric helpers (pure — no database, no network)
# ---------------------------------------------------------------------------


def _prf(expected: set[str], got: set[str]) -> tuple[float, float, float]:
    """Precision, recall, F1 of a predicted id set against gold."""
    if not expected and not got:
        return 1.0, 1.0, 1.0
    tp = len(expected & got)
    precision = tp / len(got) if got else (1.0 if not expected else 0.0)
    recall = tp / len(expected) if expected else (1.0 if not got else 0.0)
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return precision, recall, f1


def _capec_result(evidence: FederatedEvidence) -> SpecialistResult | None:
    for result in evidence.results:
        if result.task.source == "capec":
            return result
    return None


def score_correlation(entry: dict, evidence: FederatedEvidence) -> dict[str, Any]:
    """Cross-source answer accuracy for one federated entry."""
    asserts = entry.get("assertions", {})
    live = set(evidence.cross_source_join_values())
    negative = bool(asserts.get("expect_no_correlation"))
    if negative:
        # A negative is exactly right when no correlation is fabricated.
        return {
            "negative": True,
            "exact": not live,
            "precision": 1.0 if not live else 0.0,
            "recall": 1.0,
            "f1": 1.0 if not live else 0.0,
            "n_expected": 0,
            "n_got": len(live),
        }
    gold = {normalize_id(v) for v in asserts.get("must_correlate", [])}
    got = {normalize_id(v) for v in live}
    precision, recall, f1 = _prf(gold, got)
    return {
        "negative": False,
        "exact": gold == got,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "n_expected": len(gold),
        "n_got": len(got),
    }


def score_mapping_recall(
    entry: dict, evidence: FederatedEvidence
) -> dict[str, Any] | None:
    """CAPEC→ATT&CK mapping recall: gold technique ids surfaced on the CAPEC side.

    Returns ``None`` for negatives and entries without mapping gold (nothing to
    recall).
    """
    asserts = entry.get("assertions", {})
    if asserts.get("expect_no_correlation"):
        return None
    gold = {normalize_id(v) for v in asserts.get("must_correlate", [])}
    if not gold:
        return None
    result = _capec_result(evidence)
    pool = id_pool(result.records) if result else set()
    found = gold & pool
    return {
        "gold": len(gold),
        "found": len(found),
        "recall": len(found) / len(gold),
        "missing": sorted(gold - pool),
    }


def _records_by_source(evidence: FederatedEvidence) -> dict[str, list[EvidenceRecord]]:
    out: dict[str, list[EvidenceRecord]] = {}
    for result in evidence.results:
        out.setdefault(result.task.source, []).extend(result.records)
    return out


def _executed_queries(evidence: FederatedEvidence) -> set[str]:
    return {r.query for r in evidence.results if r.query}


def _record_provenance_ok(
    record: EvidenceRecord, executed: set[str]
) -> bool:
    prov = record.provenance
    if prov is None:
        return False
    for fieldname in _PROVENANCE_FIELDS:
        if not getattr(prov, fieldname, None):
            return False
    # The recorded query must be one the pipeline actually executed.
    return prov.query in executed


def score_provenance(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> dict[str, Any]:
    """Every rendered claim's citations must resolve to a fully-provenanced record."""
    by_source = _records_by_source(evidence)
    executed = _executed_queries(evidence)
    total = 0
    compliant = 0
    for claim in answer.rendered_claims():
        for citation in claim.citations:
            total += 1
            want = normalize_id(citation.primary_id)
            matched = [
                r
                for r in by_source.get(citation.source, [])
                if normalize_id(r.primary_id) == want
            ]
            if matched and any(_record_provenance_ok(r, executed) for r in matched):
                compliant += 1

    # Abstention proofs: an executed-query proof must be a real executed query;
    # a boundary abstention must carry no query at all.
    abstention_ok = True
    for abst in answer.abstentions:
        if abst.query and abst.query not in executed:
            abstention_ok = False
    citation_rate = compliant / total if total else 1.0
    return {
        "citations": total,
        "compliant": compliant,
        "citation_provenance_rate": citation_rate,
        "abstention_proof_ok": abstention_ok,
        "fully_provenanced": citation_rate == 1.0 and abstention_ok,
    }


def score_inspectability(
    answer: SynthesizedAnswer, evidence: FederatedEvidence
) -> dict[str, Any]:
    """Claim citation coverage + claim→record→query traceability + abstention proofs."""
    by_source = _records_by_source(evidence)
    executed = _executed_queries(evidence)
    rendered = answer.rendered_claims()

    if rendered:
        cited = sum(1 for c in rendered if c.citations)
        citation_coverage = cited / len(rendered)
        traceable = 0
        for claim in rendered:
            chains = []
            for citation in claim.citations:
                want = normalize_id(citation.primary_id)
                chains.append(
                    any(
                        r.provenance is not None and r.provenance.query in executed
                        for r in by_source.get(citation.source, [])
                        if normalize_id(r.primary_id) == want
                    )
                )
            if claim.citations and all(chains):
                traceable += 1
        traceability = traceable / len(rendered)
    else:
        citation_coverage = 1.0
        traceability = 1.0

    if answer.abstentions:
        proof_ok = sum(
            1
            for a in answer.abstentions
            if (a.query and a.query in executed) or (not a.query and a.statement)
        )
        abstention_proofs = proof_ok / len(answer.abstentions)
    else:
        abstention_proofs = 1.0

    composite = (citation_coverage + traceability + abstention_proofs) / 3
    return {
        "citation_coverage": citation_coverage,
        "traceability": traceability,
        "abstention_proofs": abstention_proofs,
        "inspectability": composite,
    }


@dataclass
class E2ECase:
    """One catalogue entry's end-to-end scores."""

    id: str
    kind: str  # "federated" | "single"
    tier: str = ""
    category: str = ""
    correlation: dict[str, Any] | None = None
    mapping_recall: dict[str, Any] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    inspectability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "tier": self.tier,
            "category": self.category,
            "correlation": self.correlation,
            "mapping_recall": self.mapping_recall,
            "provenance": self.provenance,
            "inspectability": self.inspectability,
        }


def evaluate_case(
    entry: dict,
    evidence: FederatedEvidence,
    answer: SynthesizedAnswer,
    *,
    kind: str,
) -> E2ECase:
    """Score one entry from its (evidence, answer) — pure, DB-free."""
    case = E2ECase(
        id=entry.get("id", ""),
        kind=kind,
        tier=entry.get("tier", "") or "",
        category=entry.get("category", "") or _category_of(entry.get("id", "")),
        provenance=score_provenance(answer, evidence),
        inspectability=score_inspectability(answer, evidence),
    )
    if kind == "federated":
        case.correlation = score_correlation(entry, evidence)
        case.mapping_recall = score_mapping_recall(entry, evidence)
    return case


def _category_of(qid: str) -> str:
    """Derive the federated category prefix (e.g. ``F-CTM-01`` → ``F-CTM``)."""
    parts = qid.split("-")
    return "-".join(parts[:2]) if len(parts) >= 3 else qid


# ---------------------------------------------------------------------------
# aggregation
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def aggregate(cases: list[E2ECase], judge: JudgeReport) -> dict[str, Any]:
    """Roll per-case scores into the report's overall + segmented views."""
    fed = [c for c in cases if c.kind == "federated" and c.correlation is not None]
    positives = [c for c in fed if not c.correlation["negative"]]
    negatives = [c for c in fed if c.correlation["negative"]]

    exact_k = sum(1 for c in positives if c.correlation["exact"])
    exact_pt, exact_lo, exact_hi = wilson_interval(exact_k, len(positives)) if positives else (0.0, 0.0, 0.0)

    neg_ok = sum(1 for c in negatives if c.correlation["exact"])
    neg_pt, neg_lo, neg_hi = wilson_interval(neg_ok, len(negatives)) if negatives else (1.0, 0.0, 1.0)

    mapped = [c.mapping_recall for c in fed if c.mapping_recall is not None]
    gold_total = sum(m["gold"] for m in mapped)
    found_total = sum(m["found"] for m in mapped)

    prov_rates = [c.provenance["citation_provenance_rate"] for c in cases]
    prov_full_k = sum(1 for c in cases if c.provenance["fully_provenanced"])
    prov_pt, prov_lo, prov_hi = wilson_interval(prov_full_k, len(cases)) if cases else (0.0, 0.0, 0.0)

    inspect = [c.inspectability["inspectability"] for c in cases]

    return {
        "cross_source_accuracy": {
            "positives": len(positives),
            "exact_match": {"k": exact_k, "n": len(positives), "rate": round(exact_pt, 4),
                            "ci_low": round(exact_lo, 4), "ci_high": round(exact_hi, 4)},
            "mean_precision": round(_mean([c.correlation["precision"] for c in positives]), 4),
            "mean_recall": round(_mean([c.correlation["recall"] for c in positives]), 4),
            "mean_f1": round(_mean([c.correlation["f1"] for c in positives]), 4),
            "negatives": len(negatives),
            "no_fabrication_rate": {"k": neg_ok, "n": len(negatives), "rate": round(neg_pt, 4),
                                    "ci_low": round(neg_lo, 4), "ci_high": round(neg_hi, 4)},
        },
        "mapping_recall": {
            "entries": len(mapped),
            "gold_mappings": gold_total,
            "found_mappings": found_total,
            "micro_recall": round(found_total / gold_total, 4) if gold_total else 1.0,
            "mean_recall": round(_mean([m["recall"] for m in mapped]), 4),
        },
        "provenance_correctness": {
            "answers": len(cases),
            "mean_citation_provenance_rate": round(_mean(prov_rates), 4),
            "fully_provenanced": {"k": prov_full_k, "n": len(cases), "rate": round(prov_pt, 4),
                                  "ci_low": round(prov_lo, 4), "ci_high": round(prov_hi, 4)},
        },
        "analyst_inspectability": {
            "answers": len(cases),
            "mean_inspectability": round(_mean(inspect), 4),
            "mean_citation_coverage": round(_mean([c.inspectability["citation_coverage"] for c in cases]), 4),
            "mean_traceability": round(_mean([c.inspectability["traceability"] for c in cases]), 4),
            "mean_abstention_proofs": round(_mean([c.inspectability["abstention_proofs"] for c in cases]), 4),
        },
        "llm_judge": judge.to_dict(),
    }


def build_e2e(cases: list[E2ECase], judge: JudgeReport) -> dict[str, Any]:
    """Assemble the full e2e result block (overall + by-tier + cases)."""
    overall = aggregate(cases, judge)
    by_tier: dict[str, Any] = {}
    tiers = sorted({c.tier for c in cases if c.tier})
    for tier in tiers:
        subset = [c for c in cases if c.tier == tier]
        by_tier[tier] = aggregate(subset, JudgeReport())
    return {
        "live": True,
        "overall": overall,
        "by_tier": by_tier,
        "cases": [c.to_dict() for c in cases],
    }


# ---------------------------------------------------------------------------
# live drivers (require the Docker stack; imported lazily)
# ---------------------------------------------------------------------------

_JOIN_KEY = "attack-technique-id"
_AUTHORING_KEYS = ("expected_template", "seed_from")


def _build_plan(entry: dict):
    from utils.planner.schema import JoinDeclaration, Plan, SubQuestion

    subs = [
        SubQuestion.from_dict(
            {k: v for k, v in sub.items() if k not in _AUTHORING_KEYS}
        )
        for sub in entry["sub_questions"]
    ]
    joins = []
    if entry["sequenced"]:
        joins.append(
            JoinDeclaration.from_dict(
                {"key": _JOIN_KEY, "sources": ["capec", "attack"], "on": _JOIN_KEY}
            )
        )
    return Plan(request=entry["question"], sub_questions=subs, joins=joins)


def run_federated(entry: dict, router, synth_config):
    """Drive one federated entry through router + synthesis (live)."""
    from utils.synthesis.factory import synthesize

    plan = _build_plan(entry)
    evidence = router.run_plan(plan)
    answer = synthesize(evidence, synth_config)
    return evidence, answer


def run_single(entry: dict, specialist, synth_config):
    """Drive one single-source entry through specialist + synthesis (live)."""
    from utils.specialists.contracts import SpecialistTask
    from utils.synthesis.factory import synthesize

    task = SpecialistTask.from_dict(entry["task"])
    result = specialist.run(task)
    evidence = FederatedEvidence(request=entry["question"], results=[result])
    answer = synthesize(evidence, synth_config)
    return evidence, answer


def _load_banks():
    from utils.specialists.evalset.compile_banks import (
        ATTACK_BANK_PATH,
        CAPEC_BANK_PATH,
        FEDERATED_BANK_PATH,
        load_bank,
    )

    return (
        load_bank(FEDERATED_BANK_PATH)["questions"],
        load_bank(ATTACK_BANK_PATH)["questions"],
        load_bank(CAPEC_BANK_PATH)["questions"],
    )


def score_e2e(
    *,
    live: bool = True,
    judge_config: EvalConfig | None = None,
    limit: int | None = None,
    tiers: set[str] | None = None,
    include_single: bool = True,
) -> dict[str, Any]:
    """Run the golden catalogue through the pipeline and score the e2e metrics.

    When ``live`` is False (or the stack is unreachable) this returns an empty
    report marked ``live=False`` — the hermetic path scores nothing and is used
    only to keep the CLI/report byte-reproducible without a database.
    """
    if not live:
        return {"live": False, "cases": [], "overall": {}, "by_tier": {}}

    from utils.specialists.config import SpecialistConfig
    from utils.specialists.federation import SpecialistRouter
    from utils.synthesis.config import SynthesisConfig

    config = SpecialistConfig.from_env()
    synth_config = SynthesisConfig()  # deterministic composer; verifier always on
    # One router per degradation mode, mirroring the federated golden fixture:
    # partial-degradation entries must run with the failed source absent, or
    # both sides answer and a correlation the scenario forbids would appear.
    full = SpecialistRouter(config)
    routers = {
        None: full,
        "boundary": full,
        "attack_down": SpecialistRouter(config, cards=full.cards, specialists={"attack": None}),
        "capec_down": SpecialistRouter(config, cards=full.cards, specialists={"capec": None}),
    }
    federated, attack_q, capec_q = _load_banks()

    def _keep(entry: dict) -> bool:
        return tiers is None or (entry.get("tier") in tiers)

    cases: list[E2ECase] = []
    judge_items: list = []

    fed_entries = [e for e in federated if _keep(e)]
    if limit is not None:
        fed_entries = fed_entries[:limit]
    for entry in fed_entries:
        router = routers[entry["partial_mode"]]
        evidence, answer = run_federated(entry, router, synth_config)
        cases.append(evaluate_case(entry, evidence, answer, kind="federated"))
        judge_items.append((entry["id"], answer, evidence))

    if include_single:
        for source, entries in (("attack", attack_q), ("capec", capec_q)):
            specialist = full._specialist_for(source)
            if specialist is None:
                continue
            single = [e for e in entries if _keep(e)]
            if limit is not None:
                single = single[:limit]
            for entry in single:
                evidence, answer = run_single(entry, specialist, synth_config)
                cases.append(evaluate_case(entry, evidence, answer, kind="single"))
                judge_items.append((entry["id"], answer, evidence))

    judge = judge_run(judge_items, judge_config or EvalConfig.from_env())
    return build_e2e(cases, judge)
