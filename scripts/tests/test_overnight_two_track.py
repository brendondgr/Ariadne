"""Cover for the orchestrator's failure behaviour, which is the point of it.

An overnight run is judged by what it does when something goes wrong at 3am, so
these test the refusals rather than the happy path: a prerequisite that did not
complete, a phase past the endpoint's deadline, and a restart.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from scripts import overnight_two_track as ot


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(ot, "STATE", tmp_path / "state.json")


def _state():
    return {"plan": "test", "phases": {}, "started": None}


def _phase(name, fn, **kw):
    return ot.Phase(name, "T", fn, cap_s=60, **kw)


class TestPhaseGating:
    def test_a_completed_phase_is_skipped_on_restart(self):
        calls = []
        state = _state()
        state["phases"]["p"] = {"status": "done"}
        ot.run_phase(state, _phase("p", lambda: calls.append(1) or {}))
        assert calls == [], "a done phase must not run again"

    def test_a_phase_whose_prerequisite_failed_is_not_run(self):
        state = _state()
        state["phases"]["a"] = {"status": "failed"}
        ot.run_phase(state, _phase("b", lambda: {"ran": True}, needs=("a",)))
        rec = state["phases"]["b"]
        assert rec["status"] == "not_run"
        assert "prerequisite" in rec["reason"]
        assert "detail" not in rec, "a skipped phase must not carry a figure"

    def test_a_prerequisite_that_was_itself_skipped_still_blocks(self):
        state = _state()
        state["phases"]["a"] = {"status": "not_run", "reason": "past deadline"}
        ot.run_phase(state, _phase("b", lambda: {"ran": True}, needs=("a",)))
        assert state["phases"]["b"]["status"] == "not_run"

    def test_past_the_endpoint_deadline_a_gemma_phase_does_not_start(self, monkeypatch):
        # The endpoint disappears at 09:00; starting a five-hour pass at 08:55
        # produces a partial figure that looks like a result.
        monkeypatch.setattr(ot, "GEMMA_DEADLINE", datetime.now() - timedelta(minutes=1))
        state = _state()
        state["phases"]["P0-preflight"] = {"status": "done"}
        ot.run_phase(state, _phase("g", lambda: {"ran": True},
                                   needs=("P0-preflight",), gemma_bound=True))
        assert state["phases"]["g"]["status"] == "not_run"
        assert "deadline" in state["phases"]["g"]["reason"]

    def test_a_crashing_phase_is_recorded_not_raised(self):
        state = _state()

        def boom():
            raise RuntimeError("relay went away")

        ot.run_phase(state, _phase("x", boom))
        rec = state["phases"]["x"]
        assert rec["status"] == "failed"
        assert "relay went away" in rec["detail"]["error"]

    def test_state_survives_a_restart(self):
        state = _state()
        ot.run_phase(state, _phase("ok", lambda: {"n": 7}))
        reloaded = ot.load_state()
        assert reloaded["phases"]["ok"]["status"] == "done"
        assert reloaded["phases"]["ok"]["detail"]["n"] == 7


class TestBudgetChoice:
    """The re-run takes the SMALLEST budget that returns a query.

    Not the largest that fits: a baseline nobody can afford to repeat is not a
    baseline either.
    """

    def test_picks_the_smallest_budget_that_produced_a_query(self):
        state = _state()
        state["phases"]["A1-budget-cost"] = {"status": "done", "detail": {"trials": [
            {"max_tokens": 8192, "query": None},
            {"max_tokens": 16384, "query": "MATCH (n) RETURN n"},
            {"max_tokens": 32768, "query": "MATCH (n) RETURN n"},
        ]}}
        assert ot._chosen_budget(state) == 16384

    def test_falls_back_to_the_arms_configured_value_when_nothing_returned(self):
        state = _state()
        state["phases"]["A1-budget-cost"] = {"status": "done", "detail": {"trials": [
            {"max_tokens": 8192, "query": None},
        ]}}
        assert ot._chosen_budget(state) == 16384

    def test_falls_back_when_the_probe_shape_is_unfamiliar(self):
        assert ot._chosen_budget(_state()) == 16384

    def test_reads_the_probes_real_nested_shape(self):
        """The regression. builder_budget_probe nests trials under each case.

        Reading detail["trials"] found nothing and fell back to 16384 while the
        probe had already shown 8192 producing a query -- so the 2026-09-04
        re-run ran 26% slower than it needed to and hit its cap at 203/284. A
        fallback that fires without saying so is the same failure mode as the
        import-time budget freeze it exists to avoid.
        """
        state = _state()
        state["phases"]["A1-budget-cost"] = {"status": "done", "detail": {"cases": [
            {"id": "c1", "trials": [
                {"budget": 8192, "produced_query": True, "content_chars": 245},
                {"budget": 16384, "produced_query": True, "content_chars": 221},
                {"budget": 32768, "produced_query": True, "content_chars": 246},
            ]},
        ]}}
        assert ot._chosen_budget(state) == 8192

    def test_a_budget_that_produced_nothing_is_not_chosen(self):
        state = _state()
        state["phases"]["A1-budget-cost"] = {"status": "done", "detail": {"cases": [
            {"trials": [
                {"budget": 8192, "produced_query": False, "content_chars": 0},
                {"budget": 32768, "produced_query": True, "content_chars": 246},
            ]},
        ]}}
        assert ot._chosen_budget(state) == 32768


class TestReport:
    def test_the_report_names_every_phase_that_did_not_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ot, "BANK_DIR", tmp_path)
        monkeypatch.setattr(ot, "POST_REPAIR", tmp_path / "absent")
        monkeypatch.setattr(ot, "LLM_FAIR", tmp_path / "absent2")
        reports = tmp_path / "docs/reports"
        reports.mkdir(parents=True)
        monkeypatch.setattr(ot, "REPO", tmp_path)
        state = _state()
        state["phases"] = {
            "A2-llm-query-rerun": {"status": "not_run", "reason": "capped at 2.5h"},
            "B1-gemma-regrade": {"status": "done"},
        }
        ot.rollup(state)
        text = (reports / "2026-09-04-overnight-report.md").read_text()
        assert "What did not run" in text
        assert "A2-llm-query-rerun" in text
        assert "capped at 2.5h" in text
        assert "holdout" in text.lower()

    def test_an_arm_with_no_answers_is_reported_as_not_run_not_as_zero(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(ot, "BANK_DIR", tmp_path)
        monkeypatch.setattr(ot, "POST_REPAIR", tmp_path / "absent")
        monkeypatch.setattr(ot, "LLM_FAIR", tmp_path / "absent2")
        (tmp_path / "docs/reports").mkdir(parents=True)
        monkeypatch.setattr(ot, "REPO", tmp_path)
        result = ot.rollup(_state())
        assert result["llm_query"] == {"status": "not_run"}
        saved = json.loads((tmp_path / "two-grader-judged.json").read_text())
        assert saved["deterministic"]["status"] == "not_run"
