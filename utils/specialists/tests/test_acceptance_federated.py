#!/usr/bin/env python3
"""Live end-to-end acceptance for the federated pipeline (Wk 10–11).

Two layers, both against the real Neo4j + Gremlin stack (skipped when down):

  1. THE acceptance test — the proposal's flagship credential-theft flow,
     graded against the snapshot-derived federated gold: faithful fetch,
     exact correlation set, all technique→mitigation pairs, unsupported-claim
     rate 0 %, complete provenance, exit 0.
  2. A small federated golden set (~6 genuinely cross-source questions,
     gold computed from the pinned snapshot via the committed gold artifacts)
     to catch integration regressions. This is plumbing proof, NOT the
     Wk 12–13 scored evaluation.
"""

from __future__ import annotations

import pytest

from utils.specialists.evalset.federated_gold import load_federated_gold
from utils.specialists.evalset.gold_bank import load_gold_bank
from utils.specialists.evalset.grade_federated import grade_credential_theft
from utils.specialists.pipeline import run_pipeline
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable

from utils.synthesis.config import SynthesisConfig

FLAGSHIP = (
    "Which CAPEC patterns related to credential theft map to ATT&CK "
    "techniques, and what mitigations appear for those techniques?"
)


def _stack_up() -> bool:
    return _neo4j_reachable() and _gremlin_reachable()


@pytest.fixture(scope="module")
def gold():
    return load_federated_gold()


@pytest.fixture(scope="module")
def bank():
    return load_gold_bank()


def _run(question: str):
    if not _stack_up():
        pytest.skip("live stack down — skipping federated acceptance suite")
    from utils.config import load_env

    load_env()
    return run_pipeline(question, synthesis_config=SynthesisConfig(llm_enabled=False))


def _assert_provenance_complete(run) -> None:
    by_key = {}
    for result in run.evidence.results:
        for rec in result.records:
            by_key[(result.task.source, rec.primary_id)] = rec
    for claim in run.answer.rendered_claims():
        assert claim.citations, f"claim without citation: {claim.text!r}"
        for cite in claim.citations:
            rec = by_key.get((cite.source, cite.primary_id))
            assert rec is not None and rec.provenance is not None
            assert rec.provenance.query and rec.provenance.timestamp


# -- 1. the flagship acceptance test -----------------------------------------


@pytest.mark.live
def test_credential_theft_flow_matches_snapshot_gold(gold) -> None:
    run = _run(FLAGSHIP)
    assert (run.status, run.exit_code) == ("answered", 0)

    verdict = grade_credential_theft(run.evidence.to_dict(), gold)
    assert verdict["faithful"], verdict
    assert verdict["correlation_matches_gold"], verdict
    assert verdict["retrieved_pairs"] == verdict["expected_pairs"] == 64
    assert verdict["dropped_pair_count"] == 0
    assert verdict["over_fetch_capec_tids"] == 0 and verdict["over_fetch_attack_tids"] == 0

    assert run.answer.verification.unsupported_claim_rate == 0.0
    _assert_provenance_complete(run)

    # The dependency actually sequenced: ATT&CK was seeded by CAPEC's output.
    seq = run.evidence.sequencing
    assert len(seq) == 1 and seq[0]["skipped"] is None
    assert seq[0]["seed_count"] == len(gold["technique_ids"])


# -- 2. the federated golden set ----------------------------------------------

# (question, capec_id) — expected values are read from the committed
# snapshot-derived gold bank, never typed here.
_SEEDED_QUESTIONS = [
    ("Does CAPEC-600 map to any ATT&CK techniques, and what mitigations exist "
     "for those techniques?", "CAPEC-600"),
    ("Which ATT&CK techniques does CAPEC-565 map to, and what mitigations "
     "apply to them?", "CAPEC-565"),
    ("Which ATT&CK techniques does CAPEC-555 map to, and what mitigations "
     "apply to them?", "CAPEC-555"),
    ("Does CAPEC-49 map to any ATT&CK techniques, and what mitigations exist "
     "for those techniques?", "CAPEC-49"),
]


@pytest.mark.live
@pytest.mark.parametrize("question,capec_id", _SEEDED_QUESTIONS)
def test_federated_golden_seeded_mapping(question: str, capec_id: str, bank) -> None:
    expected_tids = bank["capec"]["attack_mappings"][capec_id]
    run = _run(question)
    assert (run.status, run.exit_code) == ("answered", 0)

    # Correlation = exactly the snapshot's mapped T-IDs for this pattern.
    assert run.evidence.cross_source_join_values() == expected_tids

    # Every expected technique→mitigation pair appears in the ATT&CK evidence.
    tm = bank["attack"]["technique_mitigations"]
    attack_records = {
        r.primary_id: r
        for res in run.evidence.results if res.task.source == "attack"
        for r in res.records
    }
    for tid in expected_tids:
        rec = attack_records.get(tid)
        assert rec is not None, f"{tid} missing from ATT&CK evidence"
        got_mits = {rel.get("id") for rel in rec.related if rel.get("id")}
        assert got_mits == set(tm.get(tid, [])), f"mitigations for {tid} diverge from gold"

    assert run.answer.verification.unsupported_claim_rate == 0.0
    _assert_provenance_complete(run)


@pytest.mark.live
def test_federated_golden_deprecated_pattern_double_abstention(bank) -> None:
    """CAPEC-557 is excluded at load: the producer returns an honest empty with
    query proof and the consumer abstains on the dependency, never running broad."""
    assert "CAPEC-557" in bank["capec"]["deprecated"]
    run = _run(
        "Does the deprecated pattern CAPEC-557 map to any ATT&CK techniques, "
        "and what mitigations apply?"
    )
    assert (run.status, run.exit_code) == ("answered", 0)
    assert not run.answer.rendered_claims()
    abst = {a.source: a for a in run.answer.abstentions}
    assert set(abst) == {"capec", "attack"}
    assert abst["capec"].query, "producer abstention must carry the executed query"
    assert not abst["attack"].query, "dependency abstention must NOT invent a query"
    assert "depends on" in abst["attack"].statement
    seq = run.evidence.sequencing
    assert len(seq) == 1 and seq[0]["skipped"] == "it returned no join values"


@pytest.mark.live
def test_federated_golden_nonexistent_pattern_abstains() -> None:
    run = _run(
        "Does CAPEC-99999 map to any ATT&CK techniques, and what mitigations apply?"
    )
    assert (run.status, run.exit_code) == ("answered", 0)
    assert not run.answer.rendered_claims()
    assert len(run.answer.abstentions) == 2
