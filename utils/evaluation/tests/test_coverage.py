#!/usr/bin/env python3
"""A judged mean must carry the number it is out of.

EXP-2026-08-021: 6 of 1,794 gradings failed and every one was in the top 5% of
answers by size. A dropped case is not a thinner sample, it is the hardest
questions leaving the denominator, so the mean rises and the figure says nothing.
"""

from __future__ import annotations

from utils.evaluation.coverage import coverage_note, judgment_coverage


def _make(tmp_path, answers=3, judged=3, errored=0, suffix=""):
    d = tmp_path / "arm" / "answers"
    d.mkdir(parents=True)
    for i in range(answers):
        (d / f"H-{i:02d}.json").write_text("{}")
    for i in range(judged):
        (d / f"H-{i:02d}.judgment{suffix}.json").write_text("{}")
    for i in range(judged, judged + errored):
        (d / f"H-{i:02d}.judgment{suffix}.error.txt").write_text("boom")
    return tmp_path


def test_a_complete_pass_is_complete_and_says_nothing(tmp_path):
    cov = judgment_coverage(_make(tmp_path), "arm")
    assert cov["complete"] and cov["coverage"] == 1.0
    assert coverage_note(cov) == ""


def test_an_incomplete_pass_names_the_missing_cases(tmp_path):
    cov = judgment_coverage(_make(tmp_path, answers=3, judged=2, errored=1), "arm")
    assert cov == {
        "n_answers": 3, "n_judged": 2, "n_errored": 1,
        "ungraded_cases": ["H-02"], "coverage": round(2 / 3, 4), "complete": False,
    }
    note = coverage_note(cov)
    assert "2/3 graded" in note and "H-02" in note and "not missing at random" in note


def test_a_suffixed_pass_is_counted_separately(tmp_path):
    root = _make(tmp_path, answers=3, judged=3)
    (root / "arm" / "answers" / "H-00.judgment.r2.json").write_text("{}")
    assert judgment_coverage(root, "arm", ".r2")["n_judged"] == 1
    assert judgment_coverage(root, "arm")["n_judged"] == 3


def test_a_judgment_of_a_judgment_is_never_counted(tmp_path):
    root = _make(tmp_path, answers=2, judged=2)
    (root / "arm" / "answers" / "H-00.judgment.judgment.json").write_text("{}")
    assert judgment_coverage(root, "arm")["n_judged"] == 2


def test_a_missing_directory_is_not_a_crash(tmp_path):
    cov = judgment_coverage(tmp_path, "nope")
    assert cov["n_answers"] == 0 and not cov["complete"] and coverage_note(cov) == ""
