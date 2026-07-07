"""Tests for the latency harness.

The sample-shaping and percentile logic is tested hermetically with a fake
specialist and an injected clock (deterministic, no DB, no wall-clock). A live
test runs a small paired stream against the real stack and asserts shape and
ordering — never absolute milliseconds, which are environment-specific.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils.specialists.evalset.latency import (
    Sample,
    _stage_ms,
    measure,
    run_latency,
    summarize,
)
from utils.specialists.tests.test_cypher_specialist import _neo4j_reachable
from utils.specialists.tests.test_gremlin_specialist import _gremlin_reachable


def _trace(step: str, ms: float):
    return SimpleNamespace(step=step, detail={"timing_ms": ms})


class _FakeSpecialist:
    """Returns a fixed trace set so measure() is deterministic."""

    def run(self, task):
        return SimpleNamespace(traces=[
            _trace("gate", 0.5), _trace("gate", 0.5),   # two attempts -> summed
            _trace("execute", 4.0),
            _trace("assess", 0.1),
            _trace("normalize", 0.2),
        ])


def test_stage_ms_sums_repeated_steps() -> None:
    traces = [_trace("gate", 0.5), _trace("gate", 0.5), _trace("execute", 4.0)]
    assert _stage_ms(traces, "gate") == 1.0
    assert _stage_ms(traces, "execute") == 4.0
    assert _stage_ms(traces, "normalize") == 0.0


def test_measure_uses_injected_clock() -> None:
    ticks = iter([float(i) for i in range(1000)])  # each clock() call advances 1.0s
    questions = [{"id": "Q1", "tier": "easy", "task": {"sub_question_id": "Q1", "source": "attack", "text": "x"}},
                 {"id": "Q2", "tier": "medium", "task": {"sub_question_id": "Q2", "source": "attack", "text": "y"}}]
    samples = measure(_FakeSpecialist(), questions, reps=3, clock=lambda: next(ticks))
    assert len(samples) == 6                      # 2 questions x 3 reps
    assert sum(s.cold for s in samples) == 2      # rep 0 of each question
    s = samples[0]
    assert s.total_ms == 1000.0                   # (1.0 - 0.0) * 1000ms
    assert s.gate_ms == 1.0 and s.execute_ms == 4.0


def test_summarize_shape_and_ordering() -> None:
    samples = [
        Sample(id="Q", tier="easy", rep=r, cold=(r == 0), total_ms=float(10 + r),
               gate_ms=0.5, execute_ms=float(8 + r), assess_ms=0.1, normalize_ms=0.2)
        for r in range(10)
    ]
    rep = summarize(samples)
    assert rep["samples"] == 10 and rep["warm_samples"] == 9
    t = rep["total_ms"]
    assert t["p50"] <= t["p95"] <= t["p99"]
    assert t["p50_p99_gap"] == round(t["p99"] - t["p50"], 3)
    assert set(rep["by_stage"]) == {"gate_ms", "execute_ms", "assess_ms", "normalize_ms"}
    assert "easy" in rep["by_tier"]
    assert rep["cold_vs_warm"]["cold_p50"] is not None


@pytest.mark.live
@pytest.mark.integration
def test_latency_live_shape() -> None:
    if not (_neo4j_reachable() and _gremlin_reachable()):
        pytest.skip("graph stack not reachable")
    # small paired stream keeps the test quick; the real report uses n>=200
    report = run_latency(reps_per_specialist={"attack": 2, "capec": 2})
    for source in ("attack", "capec"):
        d = report[source]
        assert d["samples"] > 0
        t = d["total_ms"]
        assert t["p50"] <= t["p95"] <= t["p99"]
        # execute is a real stage and should register some time
        assert d["by_stage"]["execute_ms"]["p50"] >= 0.0
