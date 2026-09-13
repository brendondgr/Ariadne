"""Cover for the three counts, and for reporting them beside the control.

A 100% zero-record rate means something different when the control also
retrieves nothing. The seam is chargeable for the difference, not for the
absolute, so every test here fixes the control as well as the model arm.
"""

from __future__ import annotations

import json

from scripts.specialist_seam_health import health, load


def _artifact(case, *, records=1, query="g.V()", reasons=()):
    return {
        "id": case,
        "evidence_volume": {"records": records},
        "logic_flow": {
            "results": [
                {"traces": [{"step": "gate", "reasons": list(reasons),
                             "detail": {"query": query}}]}
            ]
        },
    }


class TestLoader:
    def test_sidecars_and_manifests_are_excluded(self, tmp_path):
        (tmp_path / "a.json").write_text(json.dumps(_artifact("a")))
        (tmp_path / "a.judgment.rc2.json").write_text(json.dumps(_artifact("a")))
        (tmp_path / "manifest.json").write_text(json.dumps({"x": 1}))
        assert set(load(tmp_path)) == {"a"}


class TestCounts:
    def test_a_seam_that_changed_nothing_is_viable(self):
        # Identical queries mean zero drafts to reject, which must not be
        # reported as a 100% rejection rate.
        model = {"a": _artifact("a")}
        control = {"a": _artifact("a")}
        out = health(model, control)
        assert out["queries_differing_from_control"] == 0
        assert out["drafts_submitted_to_the_gate"] == 1
        assert out["rejection_rate_over_drafts"] == 0.0
        assert out["viable_at_this_model_size"] is True

    def test_empty_drafts_count_against_the_rate(self):
        model = {str(i): _artifact(str(i), records=0, query=None,
                                   reasons=["empty query"]) for i in range(4)}
        control = {str(i): _artifact(str(i)) for i in range(4)}
        out = health(model, control)
        assert out["empty_drafts"] == 4
        assert out["rejection_rate_over_drafts"] == 1.0
        assert out["viable_at_this_model_size"] is False

    def test_allowlist_rejections_are_counted_by_name(self):
        model = {"a": _artifact("a", records=0, query="g.E()",
                                reasons=["edge not in allowed_edge_patterns"])}
        control = {"a": _artifact("a")}
        assert health(model, control)["allowlist_rejections"] == 1

    def test_zero_records_are_reported_for_both_sides(self):
        # The control retrieving nothing either is the case where the seam is
        # not chargeable, and the numbers must make that visible.
        model = {"a": _artifact("a", records=0, query="g.E()")}
        control = {"a": _artifact("a", records=0)}
        out = health(model, control)
        assert out["zero_record_model"] == 1
        assert out["zero_record_control"] == 1
        assert out["retrieved_less_than_control"] == 0

    def test_retrieving_less_than_the_control_is_named_case_by_case(self):
        model = {"a": _artifact("a", records=2, query="g.E()")}
        control = {"a": _artifact("a", records=9)}
        out = health(model, control)
        assert out["retrieved_less_case_ids"] == ["a"]

    def test_retrieving_more_is_not_counted_as_a_loss(self):
        model = {"a": _artifact("a", records=9, query="g.E()")}
        control = {"a": _artifact("a", records=2)}
        assert health(model, control)["retrieved_less_than_control"] == 0

    def test_a_rate_exactly_at_the_threshold_is_still_viable(self):
        model = {str(i): _artifact(str(i), query=f"q{i}",
                                   reasons=["empty query"] if i == 0 else [])
                 for i in range(4)}
        control = {str(i): _artifact(str(i)) for i in range(4)}
        out = health(model, control)
        assert out["rejection_rate_over_drafts"] == 0.25
        assert out["viable_at_this_model_size"] is True

    def test_an_empty_run_is_not_viable_by_vacuum(self):
        assert health({}, {})["viable_at_this_model_size"] is False


class TestTheDenominator:
    def test_the_rate_divides_by_drafts_not_by_questions(self):
        """A rate above 1 is the arithmetic saying the denominator is wrong.

        One question can carry several sub-questions and therefore several
        drafts. Dividing by questions produced 1.22 the first time this ran.
        """
        model = {
            "a": {
                "id": "a",
                "evidence_volume": {"records": 0},
                "logic_flow": {"results": [{"traces": [
                    {"step": "gate", "reasons": ["empty query"], "detail": {"query": None}},
                    {"step": "gate", "reasons": ["empty query"], "detail": {"query": None}},
                    {"step": "gate", "reasons": [], "detail": {"query": "g.V()"}},
                ]}]},
            }
        }
        control = {"a": _artifact("a")}
        out = health(model, control)
        assert out["drafts_submitted_to_the_gate"] == 3
        assert out["empty_drafts"] == 2
        assert out["rejection_rate_over_drafts"] == round(2 / 3, 4)
        assert out["rejection_rate_over_drafts"] <= 1.0

    def test_a_draft_that_cleared_the_gate_and_crashed_did_not_work(self):
        model = {
            "a": {
                "id": "a",
                "evidence_volume": {"records": 0},
                "logic_flow": {"results": [{"traces": [
                    {"step": "gate", "reasons": [], "detail": {"query": "g.V()"}},
                    {"step": "execute", "reasons": ["597: No such property: params"], "detail": {}},
                ]}]},
            }
        }
        control = {"a": _artifact("a")}
        out = health(model, control)
        assert out["drafts_submitted_to_the_gate"] == 1
        assert out["rejection_rate_over_drafts"] == 0.0   # the gate passed it
        assert out["executed_but_errored"] == 1
        assert out["drafts_that_worked"] == 0             # but it did not work
