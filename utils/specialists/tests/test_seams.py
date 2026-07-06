#!/usr/bin/env python3
"""Contract tests for the four integration-frozen seams (Wk 10–11).

Integration failures live at the seams, not inside the agents. Each test here
guards one boundary contract hermetically (LLM off, no live DB):

  1. Plan → SpecialistTask          — no silent field drops
  2. Specialist → SpecialistResult  — provenance complete, ATTACK-only join values
  3. results → FederatedEvidence    — one shared partial/status rule
  4. FederatedEvidence → SynthesizedAnswer — claims resolve, empties abstain
"""

from __future__ import annotations

from utils.planner.schema import Limits, Plan, SubQuestion, UnsupportedPart

from utils.specialists.contracts import (
    EvidenceRecord,
    Provenance,
    SpecialistResult,
    SpecialistTask,
)
from utils.specialists.evidence import check_contract, result_conforms
from utils.specialists.federation import bundle_evidence, status_and_exit
from utils.specialists.gremlin.normalizer import GremlinNormalizer
from utils.specialists.resolve import ResolvedTask
from utils.specialists.tests._fixtures import fixture_card

from utils.synthesis.config import SynthesisConfig
from utils.synthesis.factory import synthesize


def _prov(dataset: str = "attack", backend: str = "neo4j") -> Provenance:
    return Provenance(
        source=dataset, dataset=dataset, backend=backend,
        query="MATCH (n) RETURN n LIMIT 1", record_id="r1",
        timestamp="2026-07-06T00:00:00+00:00",
    )


def _record(primary_id: str, join_values: tuple[str, ...] = (), **kw) -> EvidenceRecord:
    return EvidenceRecord(
        primary_id=primary_id, id_scheme="attack-id", label="Technique",
        name=primary_id, join_values=join_values,
        provenance=kw.pop("provenance", _prov()), **kw,
    )


def _task(source: str = "attack") -> SpecialistTask:
    return SpecialistTask(sub_question_id="q1", source=source, text="t")


def _result(
    source: str = "attack",
    records: list[EvidenceRecord] | None = None,
    ok: bool = True,
    partial: bool = False,
) -> SpecialistResult:
    return SpecialistResult(
        task=_task(source), query="MATCH (n) RETURN n LIMIT 1",
        records=records if records is not None else [_record("T1047", ("T1047",))],
        summary="s", ok=ok, partial=partial,
    )


# -- Seam 1: Plan → SpecialistTask ------------------------------------------


def test_seam_plan_to_task_preserves_every_field() -> None:
    sq = SubQuestion(
        id="q7",
        source="capec",
        text="find credential-theft patterns and mapped ATT&CK ids",
        entities=["AttackPattern", "MAPS_TO"],
        limits=Limits(max_traversal_depth=3, max_result_rows=1000, query_timeout_ms=5000),
        join_key="attack-technique-id",
        rationale="capec models attack patterns",
    )
    task = SpecialistTask.from_sub_question(sq, seed_ids=("T1110", "T1555"))

    assert task.sub_question_id == sq.id
    assert task.source == sq.source
    assert task.text == sq.text
    assert task.entities == tuple(sq.entities)
    assert task.limits == sq.limits.to_dict()
    assert task.join_key == sq.join_key
    assert task.rationale == sq.rationale
    assert task.seed_ids == ("T1110", "T1555")
    # And the limit accessors read the card-provided bounds, not fallbacks.
    assert task.max_depth() == 3 and task.max_rows() == 1000 and task.timeout_ms() == 5000


# -- Seam 2: Specialist → SpecialistResult ----------------------------------


def test_seam_result_requires_complete_provenance() -> None:
    good = _result()
    assert result_conforms(good)
    assert check_contract(good.records) == []

    # A record with no provenance violates the seam contract.
    bare = EvidenceRecord(
        primary_id="T1047", id_scheme="attack-id", label="Technique",
        name="WMI", provenance=None,
    )
    problems = check_contract([bare])
    assert problems, "missing provenance must be flagged"


def test_seam_gremlin_join_values_are_attack_taxonomy_only() -> None:
    """A MAPS_TO result over mixed taxonomies leaks no WASC join value."""
    card = fixture_card("capec")
    rows = [
        {
            "ap": {"id": "capec-66", "label": "AttackPattern",
                   "name": "SQL Injection", "record_id": "capec-66"},
            "tax": {"id": "tax-1", "label": "TaxonomyEntry", "name": "Exploit...",
                    "entry_id": "1190", "taxonomy_name": "ATTACK"},
        },
        {
            "ap": {"id": "capec-66", "label": "AttackPattern",
                   "name": "SQL Injection", "record_id": "capec-66"},
            "tax": {"id": "tax-2", "label": "TaxonomyEntry", "name": "SQL Injection",
                    "entry_id": "19", "taxonomy_name": "WASC"},
        },
    ]
    resolved = ResolvedTask(task=_task("capec"), dataset="capec")
    records = GremlinNormalizer().normalize(rows, resolved, "g.V()...", card)

    assert len(records) == 1
    assert records[0].join_values == ("T1190",)
    assert all(v.startswith("T") for v in records[0].join_values)
    # The WASC entry survives as related context, just never as a join value.
    assert any(r.get("taxonomy_name") == "WASC" for r in records[0].related)


# -- Seam 3: results → FederatedEvidence (one shared partial rule) ----------


def test_seam_partial_rule_single_source_of_truth() -> None:
    plan = Plan(request="q", sub_questions=[], joins=[])

    clean = bundle_evidence(plan, [_result()], [])
    assert clean.partial is False
    assert status_and_exit(cards_present=True, evidence=clean) == ("answered", 0)

    failed = bundle_evidence(plan, [_result(ok=False)], [])
    partial = bundle_evidence(plan, [_result(partial=True)], [])
    skipped = bundle_evidence(plan, [_result()], [{"sub_question": "q2", "source": "capec", "reason": "down"}])
    unsupported_plan = Plan(request="q", unsupported=[UnsupportedPart("x", "no source")])
    unsupported = bundle_evidence(unsupported_plan, [_result()], [])
    for bundle in (failed, partial, skipped, unsupported):
        assert bundle.partial is True
        assert status_and_exit(cards_present=True, evidence=bundle) == ("partial", 1)

    assert status_and_exit(cards_present=False) == ("no_sources", 2)
    assert status_and_exit(cards_present=True, mode="plan", plan=plan) == ("answered", 0)
    partial_plan = Plan(request="q", partial=True)
    assert status_and_exit(cards_present=True, mode="plan", plan=partial_plan) == ("partial", 1)


def test_seam_cli_and_api_bundle_through_the_shared_helper() -> None:
    """Drift guard: both entry points delegate orchestration to iter_pipeline,
    and the partial rule exists exactly once, in the shared federation helper."""
    import inspect

    import api.services.query as api_query
    import utils.specialists.cli as spec_cli
    import utils.specialists.federation as federation
    import utils.specialists.pipeline as pipeline

    api_src = inspect.getsource(api_query)
    cli_src = inspect.getsource(spec_cli)
    assert "iter_pipeline" in api_src and "iter_pipeline" in cli_src
    rule = "any((not r.ok) or r.partial for r in results)"
    assert rule in inspect.getsource(federation.bundle_evidence)
    for src in (api_src, cli_src, inspect.getsource(pipeline)):
        assert rule not in src


# -- Seam 4: FederatedEvidence → SynthesizedAnswer ---------------------------


def _synth_config() -> SynthesisConfig:
    return SynthesisConfig(llm_enabled=False)


def test_seam_synthesis_claims_resolve_to_retrieved_records() -> None:
    plan = Plan(request="what mitigates T1047?")
    evidence = bundle_evidence(plan, [_result()], [])
    answer = synthesize(evidence, _synth_config())

    rendered = answer.rendered_claims()
    assert rendered, "non-empty evidence must render at least one claim"
    retrieved = {r.primary_id for res in evidence.results for r in res.records}
    for claim in rendered:
        assert claim.citations, "every rendered claim must cite"
        for cite in claim.citations:
            assert cite.primary_id in retrieved
    assert answer.verification.unsupported_claim_rate == 0.0


def test_seam_synthesis_empty_source_becomes_abstention_with_query_proof() -> None:
    plan = Plan(request="does X map to Y?")
    empty = _result(records=[])
    evidence = bundle_evidence(plan, [empty], [])
    answer = synthesize(evidence, _synth_config())

    assert not answer.rendered_claims()
    assert len(answer.abstentions) == 1
    assert answer.abstentions[0].query == empty.query, "proof must be the executed query"
