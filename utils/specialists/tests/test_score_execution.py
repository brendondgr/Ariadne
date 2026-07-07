"""Tests for the Execution Accuracy (EX) scorer.

The taxonomy-bucketing and pool-extraction logic is tested hermetically with
synthetic records (no DB). A live test runs the real specialists against the
stack and asserts EX is high and precise; it skips when the stack is down.
"""

from __future__ import annotations

import pytest

from utils.specialists.contracts import EvidenceRecord
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.evalset.score_execution import (
    _got_pool,
    _score_set,
    score_execution,
)
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable


# --- hermetic: taxonomy bucketing ------------------------------------------

def test_score_set_exact_match() -> None:
    exact, prec, rec, f1, bucket = _score_set({"a", "b"}, {"a", "b"})
    assert exact and prec == 1.0 and rec == 1.0 and f1 == 1.0 and bucket is None


def test_score_set_missing_hop() -> None:
    # under-fetch: everything returned is right, but some gold is missing
    exact, prec, rec, f1, bucket = _score_set({"a", "b", "c"}, {"a", "b"})
    assert not exact and prec == 1.0 and rec == pytest.approx(2 / 3)
    assert bucket == "missing_hop"


def test_score_set_over_broad() -> None:
    # over-fetch: all gold found, but extra ids returned
    exact, prec, rec, f1, bucket = _score_set({"a"}, {"a", "b"})
    assert not exact and rec == 1.0 and prec == 0.5 and bucket == "over_broad"


def test_score_set_mismatch() -> None:
    exact, prec, rec, f1, bucket = _score_set({"a", "b"}, {"b", "c"})
    assert not exact and bucket == "mismatch"


def test_score_set_empty_when_nonempty() -> None:
    exact, prec, rec, f1, bucket = _score_set({"a"}, set())
    assert not exact and rec == 0.0 and bucket == "empty_when_nonempty"


def test_score_set_negative_exact_and_fabricated() -> None:
    exact, prec, rec, f1, bucket = _score_set(set(), set())
    assert exact and bucket is None                       # correct empty
    exact2, _p, _r, _f, bucket2 = _score_set(set(), {"x"})
    assert not exact2 and bucket2 == "fabricated_nonempty"  # invented rows


# --- hermetic: pool extraction ---------------------------------------------

def _rec(primary: str, related_ids=(), join=()) -> EvidenceRecord:
    return EvidenceRecord(
        primary_id=primary, id_scheme="attack-technique-id", label="Technique",
        name=primary, related=[{"id": r} for r in related_ids], join_values=tuple(join),
    )


def test_got_pool_node_neighbors_join() -> None:
    records = [_rec("T1047", related_ids=["M1018", "M1040"], join=["T1047"])]
    # node: the record ids themselves
    assert _got_pool(records, "node", ("T1047",)) == {"T1047"}
    # neighbors: everything exposed minus the seed input
    assert _got_pool(records, "neighbors", ("T1047",)) == {"M1018", "M1040"}
    # join: only the join values
    assert _got_pool(records, "join", ("T1047",)) == {"T1047"}


# --- hermetic: every set-gold question carries ex_gold ----------------------

def test_relationship_questions_have_ex_gold() -> None:
    for path in (ATTACK_BANK_PATH, CAPEC_BANK_PATH):
        for q in load_bank(path)["questions"]:
            a = q["assertions"]
            if a.get("expect_boundary") or q["expected_template"] in ("label_scan", "capec_scan"):
                assert "ex_gold" not in q  # scans/boundary carry no set gold
            else:
                assert "ex_gold" in q, q["id"]
                assert q["ex_gold"]["pool"] in ("node", "neighbors", "join")


# --- live: EX is high and precise ------------------------------------------

@pytest.mark.live
@pytest.mark.integration
def test_execution_accuracy_live_high_and_precise() -> None:
    if not (_neo4j_reachable() and _gremlin_reachable()):
        pytest.skip("graph stack not reachable")
    report = score_execution()
    for source in ("attack", "capec"):
        overall = report[source]["overall"]
        # With correctly-scoped snapshot gold, the deterministic specialists
        # reproduce it: high exact-match, and no fabrication.
        assert overall["exact_match"]["rate"] >= 0.9, report[source]["taxonomy"]
        assert overall["mean_precision"] == 1.0
        tax = report[source]["taxonomy"]
        assert "fabricated_nonempty" not in tax
        assert "empty_when_nonempty" not in tax
