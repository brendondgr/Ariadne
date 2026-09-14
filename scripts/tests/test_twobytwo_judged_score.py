"""Cover for the judged read, including the partial-grading case.

An overnight run that loses its endpoint mid-pass leaves some cases graded once
and others twice. A mean over one position is not comparable with a mean over
two, so that has to be visible rather than silently averaged away.
"""

from __future__ import annotations

import json

from scripts.twobytwo_judged_score import dimensions, flags, paired, positions, scores


def _write(directory, case, correctness, suffix=".rc1", **extra):
    directory.mkdir(parents=True, exist_ok=True)
    payload = {"case_id": case, "correctness": correctness}
    payload.update(extra)
    (directory / f"{case}.judgment{suffix}.json").write_text(json.dumps(payload))


class TestScores:
    def test_a_case_averages_its_grading_positions(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0, ".rc1")
        _write(tmp_path, "D0-a", 0.0, ".rc2")
        assert scores(tmp_path) == {"D0-a": 0.5}

    def test_a_judgment_without_correctness_is_skipped_not_zeroed(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0, ".rc1")
        (tmp_path / "D0-b.judgment.rc1.json").write_text(json.dumps({"case_id": "D0-b"}))
        assert scores(tmp_path) == {"D0-a": 1.0}

    def test_answers_are_not_read_as_judgments(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0)
        (tmp_path / "D0-a.json").write_text(json.dumps({"id": "D0-a", "answer": {}}))
        assert set(scores(tmp_path)) == {"D0-a"}


class TestPositions:
    def test_partial_grading_is_visible(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0, ".rc1")
        _write(tmp_path, "D0-a", 1.0, ".rc2")
        _write(tmp_path, "D0-b", 1.0, ".rc1")
        counts = positions(tmp_path)
        assert counts == {"D0-a": 2, "D0-b": 1}
        assert sum(1 for v in counts.values() if v >= 2) == 1


class TestPaired:
    def test_the_difference_is_b_minus_a(self):
        assert paired({"D0-a": 1.0, "D0-b": 1.0},
                      {"D0-a": 0.4, "D0-b": 0.4})["mean"] == -0.6

    def test_pairs_per_question(self):
        out = paired({"D0-a": 1.0, "D0-b": 0.0}, {"D0-a": 0.0, "D0-b": 1.0})
        assert out["mean"] == 0.0
        assert out["sd"] > 0

    def test_fewer_than_two_shared_cases_reports_none_not_a_crash(self):
        out = paired({"D0-a": 1.0}, {"D0-b": 1.0})
        assert out["n"] == 0
        assert out["mean"] is None
        assert out["separable"] is None

    def test_tiers_split_on_the_prefix(self):
        out = paired({"D0-a": 1.0, "D6-b": 1.0}, {"D0-a": 1.0, "D6-b": 0.0})
        assert out["per_tier"]["D6"]["mean"] == -1.0


class TestFlags:
    def test_list_valued_flags_count_their_entries(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0, ".rc1", hallucinations=["T9999", "T8888"])
        _write(tmp_path, "D0-b", 1.0, ".rc1", abstained=True)
        out = flags(tmp_path)
        assert out["hallucinations"] == 2
        assert out["abstained"] == 1
        assert out["fabricated_mapping"] == 0


class TestDimensions:
    def test_every_grader_dimension_is_reported_not_just_correctness(self, tmp_path):
        # The headline hides the trade: higher correctness, lower faithfulness.
        _write(tmp_path, "D0-a", 0.9, ".rc1", faithfulness=0.8,
               groundedness=0.7, completeness=0.6)
        out = dimensions(tmp_path)
        assert out["correctness"] == 0.9
        assert out["faithfulness"] == 0.8
        assert out["groundedness"] == 0.7
        assert out["completeness"] == 0.6

    def test_hallucinations_are_per_judgment_not_per_case(self, tmp_path):
        # Two positions per case means two judgments; dividing by cases would
        # halve the rate and make a doubling look like no change.
        _write(tmp_path, "D0-a", 1.0, ".rc1", hallucinations=["T1", "T2"])
        _write(tmp_path, "D0-a", 1.0, ".rc2", hallucinations=["T3"])
        assert dimensions(tmp_path)["hallucinations_per_judgment"] == 1.5

    def test_a_missing_dimension_is_none_not_zero(self, tmp_path):
        _write(tmp_path, "D0-a", 1.0, ".rc1")
        assert dimensions(tmp_path)["faithfulness"] is None
