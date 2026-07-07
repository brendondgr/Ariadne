"""Shared statistics for component evaluation — pure Python, no numpy.

Three families of estimate, each reported alongside its uncertainty so a single
point number is never over-read on a small corpus:

* ``percentile`` / ``percentiles`` — latency percentiles (p50/p95/p99) via the
  linear-interpolation method (numpy's default, a.k.a. type 7 / R-7). The mean is
  deliberately not offered: latency is right-skewed and the mean hides the tail.
* ``wilson_interval`` — the Wilson score interval for a binomial proportion
  (VA / EX pass rates). Preferred over the normal approximation because it stays
  inside [0, 1] and behaves at the ceiling (x == n), which is exactly where a
  deterministic query builder lives.
* ``bootstrap_ci`` — a percentile-bootstrap confidence interval for an arbitrary
  statistic (used for latency p50/p99), seeded so it is byte-reproducible.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence

__all__ = [
    "percentile",
    "percentiles",
    "proportion",
    "wilson_interval",
    "bootstrap_ci",
]


def percentile(values: Sequence[float], p: float) -> float:
    """The p-th percentile (0 <= p <= 100) by linear interpolation (type 7).

    Matches ``numpy.percentile(..., method="linear")`` so the numbers are
    recognisable to reviewers. Raises on empty input — an empty latency sample
    is a harness bug, not a zero.
    """
    if not values:
        raise ValueError("percentile() requires at least one value")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"percentile p must be in [0, 100], got {p}")
    ordered = sorted(values)
    n = len(ordered)
    if n == 1:
        return float(ordered[0])
    rank = (n - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(ordered[int(rank)])
    frac = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * frac)


def percentiles(
    values: Sequence[float], ps: Sequence[float] = (50.0, 95.0, 99.0)
) -> dict[str, float]:
    """Several percentiles at once, keyed ``"p50"``/``"p95"``/``"p99"``."""
    ordered = sorted(values)
    out: dict[str, float] = {}
    for p in ps:
        # p renders as an int label when whole (p95, not p95.0).
        label = f"p{int(p)}" if float(p).is_integer() else f"p{p}"
        out[label] = percentile(ordered, p)
    return out


def proportion(successes: int, n: int) -> float:
    """Point estimate of a success rate; 0.0 for an empty denominator."""
    if n < 0 or successes < 0 or successes > n:
        raise ValueError(f"invalid proportion {successes}/{n}")
    return successes / n if n else 0.0


def wilson_interval(
    successes: int, n: int, *, z: float = 1.96
) -> tuple[float, float, float]:
    """Wilson score interval for a binomial proportion.

    Returns ``(point, low, high)`` with the point estimate and the two-sided
    interval (default z=1.96 ≈ 95%). For n == 0 returns ``(0.0, 0.0, 1.0)`` —
    "no evidence" rather than a false certainty.
    """
    if n < 0 or successes < 0 or successes > n:
        raise ValueError(f"invalid proportion {successes}/{n}")
    if n == 0:
        return (0.0, 0.0, 1.0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / denom
    # The observed p is always inside the Wilson interval by construction; the
    # min/max guards it against floating-point drift at the ceiling (x == n),
    # where center+margin lands at 0.99999999… instead of an exact 1.0.
    low = max(0.0, min(center - margin, p))
    high = min(1.0, max(center + margin, p))
    return (p, low, high)


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float],
    *,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 1729,
) -> tuple[float, float, float]:
    """Percentile-bootstrap CI for ``statistic`` over ``values``.

    Returns ``(observed, low, high)``. Deterministic for a fixed ``seed`` so the
    reported interval is reproducible run to run. Resampling is with replacement.
    """
    if not values:
        raise ValueError("bootstrap_ci() requires at least one value")
    observed = float(statistic(values))
    if len(values) == 1:
        return (observed, observed, observed)
    rng = random.Random(seed)
    pool = list(values)
    n = len(pool)
    estimates: list[float] = []
    for _ in range(n_resamples):
        sample = [pool[rng.randrange(n)] for _ in range(n)]
        estimates.append(float(statistic(sample)))
    estimates.sort()
    alpha = (1.0 - confidence) / 2.0
    low = percentile(estimates, alpha * 100.0)
    high = percentile(estimates, (1.0 - alpha) * 100.0)
    return (observed, low, high)
