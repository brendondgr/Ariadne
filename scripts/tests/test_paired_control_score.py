#!/usr/bin/env python3
"""The paired-control scorer, against hand-computable fixtures and Step 6.

`control-metrics.json` was committed at `46652efc` without the code that made
it, so the experiment's headline pair could be quoted and not re-derived. The
scorer's own acceptance test is reproducing those figures; these lock the
arithmetic underneath it so a future change that still reproduces Step 6 by
coincidence cannot pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.paired_control_score import STEP6, _paired, _scores, score, verify


def _write(directory: Path, case: str, correctness: list[float]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for i, value in enumerate(correctness, start=1):
        (directory / f"{case}.judgment.rc{i}.json").write_text(
            json.dumps({"case_id": case, "correctness": value})
        )


def test_a_cases_score_is_the_mean_of_its_grading_positions(tmp_path):
    """Reading one position confounds the repair with the grading order."""
    _write(tmp_path, "D0-a::formal", [0.6, 1.0])
    assert _scores(tmp_path) == {"D0-a::formal": 0.8}


def test_the_difference_is_taken_per_question_not_between_the_means():
    """That is the whole point of pairing — see Q46's 0.0503 session shift."""
    before = {"a": 0.2, "b": 0.9, "c": 0.5}
    after = {"a": 0.4, "b": 1.0, "c": 0.5}
    row = _paired(before, after)
    assert row["n"] == 3
    assert row["paired_difference"] == pytest.approx(0.1)
    # A per-question spread, not the spread of the two arms.
    assert row["paired_sd"] == pytest.approx(0.1, abs=1e-9)


def test_only_questions_both_sides_graded_are_compared():
    """A cell that lost a case must not silently shift the other side's mean.

    The reference side here scored a third question the repaired side never
    reached. Averaging the two arms whole would report 0.5 against 0.75; pairing
    on the two they share reports 0.5 against 0.75 for those two and says n=2.
    """
    before = {"a": 0.0, "b": 1.0, "c": 0.5}
    after = {"a": 0.5, "b": 1.0}
    row = _paired(before, after)
    assert row["n"] == 2
    assert row["before"] == pytest.approx(0.5)
    assert row["after"] == pytest.approx(0.75)
    # And a single shared question is not a comparison at all.
    assert _paired({"a": 0.0}, {"a": 1.0}) is None


def test_separability_is_two_standard_errors_of_the_paired_difference():
    """A real difference must clear the spread of the differences themselves.

    Both slices below move by the same small amount on average; the first moves
    every question a little in the same direction, the second moves a few a lot
    in both. Only the first is separable, and that distinction is the reason the
    spread is taken over differences rather than over scores.
    """
    ids = [c for c in "abcdefghij"]
    consistent = _paired(
        {c: 0.5 for c in ids},
        {c: 0.5 + 0.04 + 0.002 * i for i, c in enumerate(ids)},
    )
    assert consistent["separable"] is True

    noisy = _paired(
        {c: 0.5 for c in ids},
        {c: 0.5 + (0.5 if i % 2 else -0.4) for i, c in enumerate(ids)},
    )
    assert noisy["paired_difference"] == pytest.approx(0.05)
    assert noisy["separable"] is False


def test_the_kill_gate_counts_fabricated_mappings_on_both_sides(tmp_path):
    """The gate is one-way: the repair must not INTRODUCE fabricated mappings."""
    for side in ("reference", "repaired"):
        for arm in ("deterministic", "generic_composed", "generic"):
            d = tmp_path / side / arm / "answers"
            d.mkdir(parents=True)
            (d / "D0-a::formal.judgment.rc1.json").write_text(json.dumps({
                "case_id": "D0-a::formal", "correctness": 0.5,
                "fabricated_mapping": side == "repaired" and arm == "generic",
            }))
    report = score(tmp_path)
    assert report["kill_gate"]["fabricated_mapping_reference"] == 0
    assert report["kill_gate"]["fabricated_mapping_repaired"] == 1
    assert report["kill_gate"]["passes"] is False


@pytest.mark.skipif(not (STEP6 / "control-metrics.json").is_file(),
                    reason="Step 6 control run not present")
def test_it_reproduces_the_committed_step_6_figures():
    """0.7188 -> 0.7845 and its five siblings, re-derived from the judgments.

    Until this passed, `control-metrics.json` was a number with no code behind
    it. It is the reason this scorer may be pointed at new data at all.
    """
    assert verify() == 0
