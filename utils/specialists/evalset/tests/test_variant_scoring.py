#!/usr/bin/env python3
"""The variant harness's scoring, on a three-case fixture.

Every metric here exists because its absence produced a plausible wrong number
once. `records_exact` alone cannot tell a form that was right and rendered badly
from a form that was wrong and dumped its way onto the gold; slot accuracy and
`catalogue_dump` are what separate them. And a per-run figure without its spread
is what kept Q2 open since August.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# `scripts/variant_harness` calls `load_env()` at import time — the same
# import-time leak D-029 records, where the API's `load_env` sent "LLM-off"
# tests to the live model. Importing it from a test module leaks the operator's
# `.env` into every test that runs afterwards, and it did: three event-parity
# tests fail if this module is collected first. The environment is snapshotted
# and restored around the import so the module under test can keep its side
# effect and this file cannot spread it.
import os  # noqa: E402

_ENV_BEFORE = dict(os.environ)
try:
    from scripts.variant_harness import (  # noqa: E402
        REWRITE_ENV,
        _numbered,
        _rewrite_fields,
        _slot_gold_index,
        _spread,
        aggregate,
        score,
        score_slots,
    )
finally:
    os.environ.clear()
    os.environ.update(_ENV_BEFORE)

GOLD = {
    "entity_ids": ["M1038", "M1040", "T1047"],
    "queries": ["MATCH (t:Technique) RETURN t"],
    "claims": ["T1047 has 2 related item(s)."],
    "record_count": 1,
}


def _variant(**over):
    base = {
        "entity_ids": list(GOLD["entity_ids"]),
        "queries": list(GOLD["queries"]),
        "claims": list(GOLD["claims"]),
        "record_count": 1,
        "abstentions": [],
    }
    base.update(over)
    return base


# -- the record metrics -----------------------------------------------------


def test_an_identical_extraction_scores_exact_on_every_axis() -> None:
    cells = score(_variant(), GOLD)
    assert cells["records_exact"] and cells["queries_exact"] and cells["claims_exact"]
    assert cells["records_recall"] == 1.0
    assert not cells["wrong_entity"] and not cells["catalogue_dump"]


def test_a_different_query_reaching_the_same_records_is_a_success() -> None:
    """Outcome, not interpretation: `records` is the primary metric."""
    cells = score(_variant(queries=["MATCH (x) RETURN x"]), GOLD)
    assert cells["records_exact"]
    assert not cells["queries_exact"]


def test_returning_records_none_of_which_are_the_golds_is_wrong_entity() -> None:
    """The metric that matters most and is easiest to miss: every claim is
    genuinely grounded in a genuinely retrieved record, and all of them are
    about the wrong thing."""
    cells = score(_variant(entity_ids=["T9999", "M0001"]), GOLD)
    assert cells["wrong_entity"]
    assert cells["records_recall"] == 0.0


def test_returning_nothing_abstains_and_is_not_wrong_entity() -> None:
    cells = score(_variant(entity_ids=[]), GOLD)
    assert cells["abstained"]
    assert not cells["wrong_entity"]


def test_a_catalogue_dump_is_flagged_even_though_it_contains_the_gold() -> None:
    """Recall inflated by returning everything is not retrieval."""
    cells = score(
        _variant(entity_ids=GOLD["entity_ids"] + [f"T{i:04d}" for i in range(600)],
                 record_count=600),
        GOLD,
    )
    assert cells["catalogue_dump"]
    assert cells["records_recall"] == 1.0  # which is exactly why the flag is needed


# -- slot accuracy ----------------------------------------------------------


SLOT_GOLD = {
    "case_id": "A-MIT-01",
    "anchors": ["T1047"],
    "anchor_labels": ["Technique"],
    "target_labels": ["Mitigation"],
    "relation": "MITIGATES",
}


def _row(form):
    return {"rewrite": {"form": form}}


def test_a_form_matching_the_gold_scores_every_slot() -> None:
    cells = score_slots(
        _row({"anchors": ["T1047"], "anchor_labels": ["Technique"],
              "target_labels": ["Mitigation"], "relation": "MITIGATES"}),
        SLOT_GOLD,
    )
    assert cells["form_exact"]
    assert cells["slots_scored"] == 4
    assert all(cells[k] for k in ("slot_anchor", "slot_anchor_label",
                                  "slot_target_label", "slot_relation"))


def test_one_wrong_slot_is_visible_and_stops_form_exact() -> None:
    cells = score_slots(
        _row({"anchors": ["T1059"], "anchor_labels": ["Technique"],
              "target_labels": ["Mitigation"], "relation": "MITIGATES"}),
        SLOT_GOLD,
    )
    assert cells["slot_anchor"] is False
    assert cells["slot_relation"] is True
    assert cells["form_exact"] is False


def test_anchor_matching_is_case_insensitive() -> None:
    cells = score_slots(_row({"anchors": ["t1047"]}), SLOT_GOLD)
    assert cells["slot_anchor"] is True


def test_a_slot_the_gold_does_not_record_is_none_not_zero() -> None:
    """A slot nobody claimed and a slot nobody asked about are different
    things, and averaging them together invents a number."""
    cells = score_slots(
        _row({"anchors": ["T1047"]}),
        {"anchors": ["T1047"], "anchor_labels": [], "target_labels": [], "relation": None},
    )
    assert cells["slot_anchor"] is True
    assert cells["slot_relation"] is None
    assert cells["slots_scored"] == 1


def test_no_rewrite_block_scores_no_slots_at_all() -> None:
    cells = score_slots({}, SLOT_GOLD)
    assert cells["form_exact"] is None
    assert cells["slots_scored"] == 0


def test_slot_gold_index_is_empty_when_the_file_is_absent(tmp_path) -> None:
    assert _slot_gold_index(tmp_path) == {}


# -- provenance columns -----------------------------------------------------


def test_the_rung_defaults_to_off_when_the_stage_never_ran() -> None:
    cells = _rewrite_fields({})
    assert cells["rung"] == "off"
    assert cells["model_consulted"] is False
    assert cells["cache_hit"] is False


def test_model_consulted_is_false_when_the_deterministic_pass_finished_it() -> None:
    cells = _rewrite_fields({"rewrite": {"rung": "deterministic", "served_model": ""}})
    assert cells["model_consulted"] is False


def test_model_consulted_is_true_when_the_model_answered_even_if_it_abstained() -> None:
    cells = _rewrite_fields(
        {"rewrite": {"rung": "abstain", "served_model": "weights-x", "cache_hit": True}}
    )
    assert cells["model_consulted"] is True
    assert cells["cache_hit"] is True
    assert cells["served_model"] == "weights-x"


# -- aggregation ------------------------------------------------------------


def _scored(tier, run_index, exact, **over):
    row = {
        "tier": tier, "run_index": run_index, "records_exact": exact,
        "records_recall": 1.0 if exact else 0.0, "queries_exact": exact,
        "claims_exact": exact, "abstained": False, "wrong_entity": not exact,
        "catalogue_dump": False, "rung": "model", "model_consulted": True,
        "cache_hit": False, "served_model": "weights-x",
        "slot_anchor": exact, "slot_anchor_label": exact,
        "slot_target_label": exact, "slot_relation": exact, "form_exact": exact,
        "timing": {"latency_s": 2.0},
    }
    row.update(over)
    return row


def test_a_single_run_reports_a_mean_and_no_spread() -> None:
    out = aggregate([_scored("T4", 0, True), _scored("T4", 0, False)], repeats=1)
    cell = out["tiers"]["T4"]["records_exact"]
    assert cell == {"mean": 0.5, "sd": None, "n": 1}
    assert out["tiers"]["T4"]["n"] == 2


def test_three_runs_report_the_spread_across_runs_not_across_questions() -> None:
    """Three runs is three runs. The sd is over the per-run figures."""
    rows = []
    for run_index, exact in enumerate((True, True, False)):
        rows.append(_scored("T5", run_index, exact))
    out = aggregate(rows, repeats=3)
    cell = out["tiers"]["T5"]["records_exact"]
    assert cell["n"] == 3
    assert cell["mean"] == pytest.approx(2 / 3, abs=1e-4)
    assert cell["sd"] > 0


def test_recall_with_the_dumps_removed_is_derived_not_looked_up() -> None:
    rows = [
        _scored("T4", 0, True),
        _scored("T4", 0, True, records_recall=1.0, catalogue_dump=True),
        _scored("T4", 0, False, records_recall=0.0),
    ]
    out = aggregate(rows, repeats=1)
    assert out["tiers"]["T4"]["records_recall"]["mean"] == pytest.approx(2 / 3, abs=1e-4)
    assert out["tiers"]["T4"]["records_recall_no_dump"]["mean"] == pytest.approx(0.5)


def test_the_aggregate_names_the_weights_and_counts_the_rungs() -> None:
    out = aggregate([_scored("T4", 0, True), _scored("T4", 0, False, rung="abstain")], 1)
    assert out["served_models"] == ["weights-x"]
    assert out["rungs"] == {"model": 1, "abstain": 1}


def test_latency_is_reported_and_lives_outside_the_compared_fields() -> None:
    out = aggregate([_scored("T4", 0, True)], repeats=1)
    assert out["tiers"]["T4"]["latency_s_mean"] == 2.0


def test_spread_of_nothing_is_none_not_zero() -> None:
    assert _spread([]) is None


# -- arm plumbing -----------------------------------------------------------


def test_every_rewrite_mode_states_both_flags() -> None:
    """An arm that inherits a flag from the operator's .env is not the arm its
    name claims — the same shape as the import-time load_env leak."""
    for mode, env in REWRITE_ENV.items():
        assert set(env) == {"ARIADNE_REWRITE", "ARIADNE_REWRITE_MODEL"}, mode
    assert REWRITE_ENV["off"] == {"ARIADNE_REWRITE": "0", "ARIADNE_REWRITE_MODEL": "0"}
    assert REWRITE_ENV["det"]["ARIADNE_REWRITE_MODEL"] == "0"
    assert REWRITE_ENV["model"] == {"ARIADNE_REWRITE": "1", "ARIADNE_REWRITE_MODEL": "1"}


def test_repeat_runs_are_written_to_separate_files() -> None:
    assert _numbered("scored_r2.json", 0) == "scored_r2.run1.json"
    assert _numbered("scored_r2.json", 2) == "scored_r2.run3.json"


def test_the_bank_runner_offers_all_three_rewrite_arms() -> None:
    from utils.evaluation.experiment_untruncated import ARMS, RUNNERS

    for arm in ("rewrite_off", "rewrite_det", "rewrite_model"):
        assert arm in ARMS and arm in RUNNERS
    # The control must NOT be the gold-replay arm: that one never runs the
    # planner, which is where the stage under test lives.
    assert RUNNERS["rewrite_off"] is not RUNNERS["deterministic"]
