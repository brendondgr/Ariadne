"""Hermetic checks for the shared evaluation statistics.

Known-input assertions so the CI/percentile math is trustworthy before any
scorer relies on it. No DB, no LLM, no randomness beyond the seeded bootstrap.
"""

from __future__ import annotations

import math
import statistics

import pytest

from utils.evaluation.stats import (
    bootstrap_ci,
    percentile,
    percentiles,
    proportion,
    wilson_interval,
)


# --- percentiles -----------------------------------------------------------

def test_percentile_linear_interpolation_matches_type7() -> None:
    # 1..100: type-7 linear interpolation gives closed-form values.
    data = list(range(1, 101))
    assert percentile(data, 50) == pytest.approx(50.5)
    assert percentile(data, 95) == pytest.approx(95.05)
    assert percentile(data, 99) == pytest.approx(99.01)
    assert percentile(data, 0) == 1.0
    assert percentile(data, 100) == 100.0


def test_percentile_is_order_invariant() -> None:
    assert percentile([9, 1, 5, 3, 7], 50) == 5.0  # median of odd-length set


def test_percentile_single_value() -> None:
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 99) == 42.0


def test_percentiles_labels_and_values() -> None:
    data = list(range(1, 101))
    out = percentiles(data)
    assert set(out) == {"p50", "p95", "p99"}
    assert out["p50"] == pytest.approx(50.5)
    assert out["p99"] == pytest.approx(99.01)


def test_percentile_rejects_empty_and_out_of_range() -> None:
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile([1, 2, 3], 150)


# --- proportion & Wilson ---------------------------------------------------

def test_proportion_basic_and_empty() -> None:
    assert proportion(3, 4) == 0.75
    assert proportion(0, 0) == 0.0
    with pytest.raises(ValueError):
        proportion(5, 4)


def test_wilson_all_success_upper_is_one() -> None:
    point, low, high = wilson_interval(20, 20)
    assert point == 1.0
    assert high == 1.0            # ceiling behaves — the deterministic-builder case
    assert 0.0 < low < 1.0        # but the lower bound reflects finite n


def test_wilson_symmetric_midpoint() -> None:
    point, low, high = wilson_interval(50, 100)
    assert point == 0.5
    # Wilson 95% CI for 50/100 is ~[0.404, 0.596], symmetric about 0.5.
    assert low == pytest.approx(0.404, abs=0.005)
    assert high == pytest.approx(0.596, abs=0.005)
    assert (0.5 - low) == pytest.approx(high - 0.5, abs=1e-9)


def test_wilson_zero_n_is_no_evidence() -> None:
    assert wilson_interval(0, 0) == (0.0, 0.0, 1.0)


def test_wilson_point_within_interval() -> None:
    for x in (0, 1, 7, 13, 19, 20):
        point, low, high = wilson_interval(x, 20)
        assert low <= point <= high
        assert 0.0 <= low <= high <= 1.0


# --- bootstrap -------------------------------------------------------------

def test_bootstrap_ci_deterministic_for_seed() -> None:
    data = [float(i) for i in range(1, 51)]
    a = bootstrap_ci(data, statistics.median, seed=7)
    b = bootstrap_ci(data, statistics.median, seed=7)
    assert a == b                       # byte-reproducible
    c = bootstrap_ci(data, statistics.median, seed=8)
    assert c != a                       # different seed → different resample


def test_bootstrap_ci_brackets_observed_statistic() -> None:
    data = [float(i) for i in range(1, 101)]
    observed, low, high = bootstrap_ci(data, statistics.median)
    assert observed == pytest.approx(statistics.median(data))
    assert low <= observed <= high
    assert math.isfinite(low) and math.isfinite(high)


def test_bootstrap_ci_single_value_is_degenerate() -> None:
    assert bootstrap_ci([5.0], statistics.median) == (5.0, 5.0, 5.0)


def test_bootstrap_ci_rejects_empty() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci([], statistics.median)
