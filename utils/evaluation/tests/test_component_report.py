"""Hermetic tests for the component-report builders.

Synthetic scorer outputs in, Markdown + JSON out — no scorers, no DB, no LLM.
Guards the report shape and the honest live-skip note.
"""

from __future__ import annotations

from utils.evaluation.component_report import build_json, build_markdown

_RATE = {"k": 30, "n": 30, "rate": 1.0, "ci_low": 0.89, "ci_high": 1.0}

_PLANNER = {
    "drafter": "deterministic",
    "overall": {"cases": 31, "mean_source_precision": 0.887, "mean_source_recall": 1.0,
                "total_unnecessary_source_calls": 7, "mean_sub_question_quality": 0.835,
                "routing_accuracy_rate": 0.774, "dependency_accuracy_rate": 0.774,
                "schema_adherence_rate": 1.0, "honesty_rate": 1.0},
    "dev": {"cases": 23, "mean_source_precision": 0.87, "mean_source_recall": 1.0},
    "holdout": {"cases": 8, "mean_source_precision": 0.94, "mean_source_recall": 1.0},
    "by_origin": {"curated": {"cases": 7, "pass_rate": 1.0}, "generated": {"cases": 24}},
    "cases": [],
}


def _specialist(live: bool) -> dict:
    return {
        "va": {"overall": {"first_pass_va": _RATE, "post_retry_va": _RATE, "boundary": 2}},
        "ex": ({"overall": {"exact_match": _RATE, "mean_precision": 1.0, "mean_recall": 1.0,
                            "mean_f1": 1.0}, "taxonomy": {}} if live else None),
        "safety": {"adherence_rate": 1.0, "audited": 30, "breaches": [],
                   "probe_block_rate": 1.0, "probes": 10, "leaks": []},
        "latency": ({"total_ms": {"p50": 1.1, "p95": 2.0, "p99": 5.0, "p50_p99_gap": 3.9},
                     "by_stage": {"gate_ms": {"p50": 0.04}, "execute_ms": {"p50": 1.0},
                                  "assess_ms": {"p50": 0.002}, "normalize_ms": {"p50": 0.016}},
                     "cold_vs_warm": {"cold_p50": 1.2, "warm_p50": 1.1}} if live else None),
    }


def test_build_json_structure() -> None:
    specialists = {"attack": _specialist(True), "capec": _specialist(True)}
    data = build_json(_PLANNER, specialists, {"attack_version": "19.0", "capec_version": "3.9"})
    assert set(data) == {"meta", "planner", "specialists", "diagnosis"}
    assert data["planner"]["overall"]["cases"] == 31
    assert isinstance(data["diagnosis"], list) and data["diagnosis"]


def test_markdown_covers_all_named_metrics() -> None:
    specialists = {"attack": _specialist(True), "capec": _specialist(True)}
    data = build_json(_PLANNER, specialists, {"attack_version": "19.0", "capec_version": "3.9",
                                              "generated_note": "full"})
    md = build_markdown(data)
    for needle in ("## Planner", "Source precision", "Sub-question quality",
                   "Query validity (VA)", "Execution accuracy (EX)",
                   "Safety adherence", "Latency", "What this diagnoses"):
        assert needle in md, needle
    # over-routing finding surfaces from the synthetic precision < 1
    assert "over-routes" in md


def test_markdown_notes_live_skip_when_ex_absent() -> None:
    specialists = {"attack": _specialist(False), "capec": _specialist(False)}
    data = build_json(_PLANNER, specialists, {"attack_version": "19.0", "capec_version": "3.9"})
    md = build_markdown(data)
    assert "_skipped: graph stack not reachable._" in md


def test_diagnosis_reports_ex_taxonomy() -> None:
    spec = _specialist(True)
    spec["ex"]["taxonomy"] = {"missing_hop": 3}
    data = build_json(_PLANNER, {"attack": spec, "capec": _specialist(True)},
                      {"attack_version": "19.0", "capec_version": "3.9"})
    assert any("missing_hop" in d for d in data["diagnosis"])
