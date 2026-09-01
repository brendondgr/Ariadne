#!/usr/bin/env python3
"""Gold-width joining — no database, no LLM.

Three joining rules were each got wrong once before being got right, and each
wrong version produced a plausible number rather than an error. That is what
these tests are for.

The fourth test is the important one: it holds the analysis to reading width
from the committed bank rather than from the grader's own estimate of it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils.evaluation import gold_width as gw

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "gold_width_effect.py"


# --- the guard against measuring the grader ---------------------------------


def test_analysis_script_does_not_read_the_grader_field() -> None:
    """`gold_expected` is a judge output; reading it would measure the grader."""
    gw.verify_grader_field_unused(SCRIPT)
    gw.verify_grader_field_unused(Path(gw.__file__))


def test_guard_catches_a_module_that_does_read_it(tmp_path: Path) -> None:
    """The guard must actually fire — a guard that cannot fail guards nothing."""
    offender = tmp_path / "offender.py"
    offender.write_text('payload = {}\nwidth = payload.get("gold_expected")\n')
    with pytest.raises(AssertionError, match="grader output"):
        gw.verify_grader_field_unused(offender)


def test_guard_ignores_the_name_in_prose(tmp_path: Path) -> None:
    """A docstring naming the field is not a read of it."""
    innocent = tmp_path / "innocent.py"
    innocent.write_text('"""We must never read gold_expected from a judgment."""\nx = 1\n')
    gw.verify_grader_field_unused(innocent)


# --- the three joining rules -------------------------------------------------


def test_case_ids_are_bank_local() -> None:
    """`H-SW-02` is a different question in each bank; keying on the id merges them."""
    banks, _ = gw.load_banks()
    widths = {key: table.get("H-SW-02") for key, table in banks.items() if "H-SW-02" in table}
    assert len(widths) > 1, "expected the same id in more than one bank"
    assert len(set(widths.values())) > 1, "distinct banks must give distinct widths"


def test_membership_uses_every_id_not_only_those_with_gold() -> None:
    """Adversarial questions belong to a bank and declare no gold.

    If membership were tested against the width table, a run containing one of
    them would match no bank and its judgments would vanish silently.
    """
    banks, ids = gw.load_banks()
    for key in banks:
        assert set(banks[key]) <= ids[key]
    assert len(ids["catalogue"]) > len(banks["catalogue"])


def test_federated_questions_are_excluded_from_width_but_kept_for_membership() -> None:
    """Their gold is a chained computation; a first-hop count would be invented."""
    excluded = gw.federated_ids()
    assert excluded, "expected federated ids to be found"
    banks, ids = gw.load_banks(excluded)
    assert excluded <= ids["catalogue"]
    assert not (excluded & set(banks["catalogue"]))


def test_every_run_on_disk_maps_to_exactly_one_bank() -> None:
    """Seven `untruncated-*` runs predate the manifest `bank` field.

    They are inferred from case-id membership. If that inference breaks, 836
    judgments drop out of the analysis without an error.
    """
    _, ids = gw.load_banks()
    runs = gw.run_bank_map(ids)
    assert len(runs) >= 32
    assert any(name.startswith("untruncated") for name in runs)


# --- the statistics ----------------------------------------------------------


def test_gold_width_reads_both_bank_shapes() -> None:
    assert gw.gold_width({"ex_gold": {"expected": ["M1", "M2"]}}) == 2
    assert gw.gold_width({"assertions": {"must_include_related": ["A"]}}) == 1
    assert gw.gold_width({"ex_gold": {"expected": []}}) == 0
    assert gw.gold_width({"question": "no gold declared"}) is None


def test_within_cell_correlation_cancels_arm_strength() -> None:
    """A pooled correlation would see a trend here; the within-cell one must not.

    Two arms, one strong and one weak. Width is uncorrelated with score inside
    each arm, but the weak arm holds all the wide questions — exactly the
    confound the within-cell control exists to remove.
    """
    rows = []
    for width in (1, 2, 3, 4):
        rows.append({"run": "r", "arm": "strong", "width": width, "correctness": 1.0})
    for width in (20, 30, 40, 50):
        rows.append({"run": "r", "arm": "weak", "width": width, "correctness": 0.5})
    pooled = gw.pearson([r["width"] for r in rows], [r["correctness"] for r in rows])
    assert pooled < -0.8, "the confound must be visible when pooled"
    assert gw.within_cell_correlation(rows)["cells"] == 0, "flat cells give no correlation"


def test_narrow_vs_wide_reports_sign_stability_not_just_a_mean() -> None:
    """A mean without the sign count hides an unstable effect."""
    rows = []
    for cell, sign in (("a", 1), ("b", -1)):
        for width in (1, 2, 3, 4, 5):
            rows.append({"run": cell, "arm": "x", "width": width, "correctness": 0.5})
        for width in (60, 70, 80):
            rows.append({"run": cell, "arm": "x", "width": width, "correctness": 0.5 + 0.1 * sign})
    result = gw.narrow_vs_wide(rows, 50)
    assert result["cells"] == 2
    assert result["negative_cells"] == 1
    assert abs(result["mean_delta"]) < 1e-9


def test_abstention_probes_are_excluded_from_the_width_analysis() -> None:
    rows = [
        {"run": "r", "arm": "a", "bank": "b", "case": "X", "category": "X", "width": 0,
         "correctness": 1.0, "completeness": 1.0},
        {"run": "r", "arm": "a", "bank": "b", "case": "Y", "category": "Y", "width": 5,
         "correctness": 0.5, "completeness": 0.5},
    ]
    result = gw.analyse(rows, {})
    assert result["n_abstention_probes"] == 1
    assert result["n_answerable"] == 1
    assert result["width"]["max"] == 5
