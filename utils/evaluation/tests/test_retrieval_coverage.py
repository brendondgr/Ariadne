#!/usr/bin/env python3
"""Tests for the judge-free retrieval scorer."""

from __future__ import annotations

from utils.evaluation.retrieval_coverage import compare, score_case, summarize


def _artifact(
    case_id: str,
    *,
    gold: list[str],
    evidence: list[str],
    answer: list[str] | None = None,
    skipped: bool = False,
) -> dict:
    traces = [{"step": "gate", "detail": {"template": "generic_chain"}}]
    if skipped:
        traces.append(
            {"step": "dependency", "reasons": ["producer q1: it returned no join values"]}
        )
    return {
        "id": case_id,
        "category": case_id.rsplit("-", 1)[0],
        "gold": {"assertions": {"must_include_ids": gold}},
        "logic_flow": {
            "results": [
                {
                    "records": [{"primary_id": e} for e in evidence],
                    "traces": traces,
                }
            ]
        },
        "answer": {
            "claims": [{"entity_ids": answer if answer is not None else evidence}],
            "narrative": "",
        },
    }


def test_full_coverage_is_one() -> None:
    row = score_case(_artifact("A-1", gold=["T1003"], evidence=["T1003"]))

    assert row["coverage"] == 1.0
    assert row["covered"] is True
    assert row["missing"] == []


def test_partial_coverage_reports_what_is_missing() -> None:
    row = score_case(
        _artifact("A-2", gold=["T1003", "AN1031"], evidence=["T1003"])
    )

    assert row["coverage"] == 0.5
    assert row["covered"] is False
    assert row["missing"] == ["AN1031"]


def test_a_question_with_no_id_assertions_is_vacuously_covered() -> None:
    """Negatives and bounded scans assert nothing about ids.

    Scoring them 0.0 would punish an arm for a question shape rather than for
    its retrieval, and would make the mean depend on how many negatives the
    catalogue happens to contain.
    """
    row = score_case(_artifact("A-NEG-1", gold=[], evidence=[]))

    assert row["coverage"] == 1.0
    assert row["covered"] is True


def test_scorable_mean_excludes_vacuous_entries() -> None:
    """The secondary mean matches score_e2e's population, not the full 120."""
    cases = {
        "A-1": score_case(_artifact("A-1", gold=["T1"], evidence=[])),
        "A-NEG-1": score_case(_artifact("A-NEG-1", gold=[], evidence=[])),
    }
    summary = summarize(cases)

    assert summary["gold_in_evidence"] == 0.5
    assert summary["gold_in_evidence_scorable"] == 0.0


def test_skipped_consumers_are_counted() -> None:
    """A dependent sub-question that never ran is the federation failure signal."""
    row = score_case(
        _artifact("F-1", gold=["T1003"], evidence=[], skipped=True)
    )

    assert row["skipped_consumers"] == 1


def test_compare_reports_regressions_separately_from_gains() -> None:
    """A change that gains more than it loses is still a trade, and must show it."""
    reference = {
        "A-1": score_case(_artifact("A-1", gold=["T1", "T2"], evidence=["T1", "T2"])),
        "A-2": score_case(_artifact("A-2", gold=["T3", "T4"], evidence=[])),
    }
    treatment = {
        "A-1": score_case(_artifact("A-1", gold=["T1", "T2"], evidence=["T1"])),
        "A-2": score_case(_artifact("A-2", gold=["T3", "T4"], evidence=["T3", "T4"])),
    }
    result = compare(treatment, reference)

    assert result["improved"] == 1
    assert result["regressed"] == 1
    assert result["gold_ids_recovered"] == 2
    assert result["gold_ids_lost"] == 1
    assert result["regressions"][0]["id"] == "A-1"
