"""Cover for the paired read, and for the denominator that has gone wrong before.

`EXP-2026-09-016` A-8 divided by the file count of a directory that also held
judgment sidecars and reported 0.04 where the truth was 0.43. The loader here
excludes every suffixed variant, and the first test is the one that would have
caught it.
"""

from __future__ import annotations

import json

from scripts.planner_cost_score import coverage, load_arm, records, summarize


def _artifact(case: str, cov: float | None, recs: int) -> dict:
    out: dict = {"id": case, "evidence_volume": {"records": recs}}
    if cov is not None:
        out["deterministic_scores"] = {"coverage": {"coverage": cov}}
    return out


class TestLoader:
    def test_judgment_sidecars_are_not_loaded_as_answers(self, tmp_path):
        answers = tmp_path / "generic_composed" / "answers"
        answers.mkdir(parents=True)
        (answers / "D0-a.json").write_text(json.dumps(_artifact("D0-a", 1.0, 1)))
        # A sidecar beside its input. Counting it doubles the denominator.
        (answers / "D0-a.judgment.rc2.json").write_text(json.dumps(_artifact("D0-a", 0.0, 0)))
        loaded = load_arm(tmp_path, "generic_composed")
        assert set(loaded) == {"D0-a"}
        assert coverage(loaded["D0-a"]) == 1.0


class TestSummary:
    def test_the_difference_is_paired_per_question(self):
        control = {c: _artifact(c, v, 1) for c, v in
                   (("D0-a", 1.0), ("D0-b", 1.0), ("D1-c", 0.0))}
        treatment = {c: _artifact(c, v, 1) for c, v in
                     (("D0-a", 0.0), ("D0-b", 1.0), ("D1-c", 1.0))}
        out = summarize(control, treatment)
        # (0-1) + (1-1) + (1-0) = 0 over three questions.
        assert out["paired_difference"]["mean"] == 0.0
        assert out["n_paired"] == 3

    def test_only_questions_present_in_both_arms_are_paired(self):
        control = {"D0-a": _artifact("D0-a", 1.0, 1), "D0-orphan": _artifact("D0-orphan", 0.0, 0)}
        treatment = {"D0-a": _artifact("D0-a", 0.0, 0)}
        assert summarize(control, treatment)["n_paired"] == 1

    def test_an_entry_without_gold_is_skipped_rather_than_scored_zero(self):
        control = {"D0-a": _artifact("D0-a", None, 1)}
        treatment = {"D0-a": _artifact("D0-a", None, 1)}
        assert summarize(control, treatment)["n_paired"] == 0

    def test_tiers_are_split_on_the_case_id_prefix(self):
        control = {"D0-a": _artifact("D0-a", 1.0, 1), "D6-b": _artifact("D6-b", 1.0, 1)}
        treatment = {"D0-a": _artifact("D0-a", 1.0, 1), "D6-b": _artifact("D6-b", 0.0, 0)}
        per_tier = summarize(control, treatment)["per_tier"]
        assert per_tier["D0"]["mean_difference"] == 0.0
        assert per_tier["D6"]["mean_difference"] == -1.0

    def test_retrieval_losses_and_gains_are_both_counted(self):
        # The reverse direction is counted rather than assumed empty: the
        # planner is not only worse, and a scorer that looks one way would miss
        # the mechanism where it is better.
        control = {"D0-a": _artifact("D0-a", 1.0, 3), "D0-b": _artifact("D0-b", 0.0, 0)}
        treatment = {"D0-a": _artifact("D0-a", 0.0, 0), "D0-b": _artifact("D0-b", 1.0, 2)}
        out = summarize(control, treatment)["retrieval"]
        assert out["treatment_empty_where_control_retrieved"] == 1
        assert out["control_empty_where_treatment_retrieved"] == 1
        assert out["lost_case_ids"] == ["D0-a"]

    def test_records_missing_is_zero_not_an_exception(self):
        assert records({"id": "x"}) == 0
