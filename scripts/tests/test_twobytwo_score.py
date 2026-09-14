"""Cover for the paired reads and the interaction term.

The 2x2 exists because the two variables might interact. A scorer that computed
the corners but got the interaction backwards would answer the wrong question
confidently, so the sign and the pairing are both pinned here.
"""

from __future__ import annotations

import json

from scripts.twobytwo_score import cell_summary, coverage, load, paired


def _artifact(case, cov, *, wall=1.0, fallback=None):
    out = {
        "id": case,
        "deterministic_scores": {"coverage": {"coverage": cov}} if cov is not None else {},
        "run_meta": {"wall_s": wall},
        "answer": {},
    }
    if fallback:
        out["answer"]["fallback_reason"] = fallback
    return out


def _cell(pairs, **kw):
    return {c: _artifact(c, v, **kw) for c, v in pairs}


class TestLoader:
    def test_sidecars_and_manifests_are_excluded(self, tmp_path):
        answers = tmp_path / "arm" / "answers"
        answers.mkdir(parents=True)
        (answers / "a.json").write_text(json.dumps(_artifact("a", 1.0)))
        (answers / "a.judgment.rc2.json").write_text(json.dumps(_artifact("a", 0.0)))
        (answers / "manifest.json").write_text(json.dumps({"x": 1}))
        loaded = load(str(tmp_path), "arm")
        assert set(loaded) == {"a"}
        assert coverage(loaded["a"]) == 1.0


class TestPaired:
    def test_the_difference_is_b_minus_a(self):
        # Sign matters: the plan effect is reported as "letting the planner run
        # costs this much", so a worse treatment must come out negative.
        a = _cell([("D0-x", 1.0)])
        b = _cell([("D0-x", 0.4)])
        assert paired(a, b)["mean"] == -0.6

    def test_it_pairs_per_question_not_per_arm(self):
        a = _cell([("D0-x", 1.0), ("D0-y", 0.0)])
        b = _cell([("D0-x", 0.0), ("D0-y", 1.0)])
        out = paired(a, b)
        assert out["mean"] == 0.0     # the means are equal...
        assert out["sd"] > 0          # ...but the questions moved
        assert out["n"] == 2

    def test_a_question_missing_from_one_side_is_not_paired(self):
        a = _cell([("D0-x", 1.0), ("D0-orphan", 1.0)])
        b = _cell([("D0-x", 1.0)])
        assert paired(a, b)["n"] == 1

    def test_an_entry_without_gold_is_skipped(self):
        a = _cell([("D0-x", None)])
        b = _cell([("D0-x", None)])
        assert paired(a, b)["n"] == 0

    def test_identical_cells_are_not_separable(self):
        a = _cell([(f"D0-{i}", 1.0) for i in range(10)])
        out = paired(a, dict(a))
        assert out["mean"] == 0.0
        assert out["separable"] is False

    def test_tiers_split_on_the_case_id_prefix(self):
        a = _cell([("D0-x", 1.0), ("D6-y", 1.0)])
        b = _cell([("D0-x", 1.0), ("D6-y", 0.0)])
        per_tier = paired(a, b)["per_tier"]
        assert per_tier["D0"]["mean"] == 0.0
        assert per_tier["D6"]["mean"] == -1.0


class TestCellSummary:
    def test_fallbacks_divide_by_answers(self):
        cases = {}
        cases.update(_cell([("a", 1.0)], fallback="LLM narrator unavailable (x)"))
        cases.update(_cell([("b", 1.0), ("c", 1.0), ("d", 1.0)]))
        out = cell_summary(cases)
        assert out["n"] == 4
        assert out["fallback_rate"] == 0.25

    def test_the_wall_clock_field_names_its_concurrency(self):
        # Throughput under load is not what one analyst waits, and the record
        # must not let the two be read as the same number.
        out = cell_summary(_cell([("a", 1.0)], wall=90.0))
        assert "at_4_workers" in "".join(out)
        assert out["wall_s_mean_at_4_workers"] == 90.0

    def test_a_cell_with_no_gold_reports_none_not_zero(self):
        out = cell_summary(_cell([("a", None)]))
        assert out["gold_coverage_mean"] is None
        assert out["scored"] == 0
