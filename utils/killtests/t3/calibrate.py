"""Conformal calibrators for entity grounding. Scores are ``s = 1 - p(gold)``.

Every calibrator returns a threshold ``Q``; a question's prediction set is
``{c : 1 - p(c) <= Q}``. Miscoverage is ``s_gold > Q``.

- :func:`split_quantile` — the ⌈(1−α)(n+1)⌉-th smallest score (split conformal);
  used for OnlySynth (all synthetic), Mondrian strata, and OnlyReal-m.
- :func:`spi_threshold` — SPI, Algorithm 1 of Bashari et al., arXiv 2505.13432
  (eq. 6, 7, 8, 11; transcribed from the paper's HTML on 2026-11-13).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

INF = float("inf")


def split_quantile(scores: Sequence[float], alpha: float) -> float:
    n = len(scores)
    if n == 0:
        return INF
    k = math.ceil((1 - alpha) * (n + 1))
    if k > n:
        return INF
    return sorted(scores)[k - 1]


def _log_comb(a: int, b: int) -> float:
    if b < 0 or b > a or a < 0:
        return -INF
    return math.lgamma(a + 1) - math.lgamma(b + 1) - math.lgamma(a - b + 1)


def _pmf(m: int, N: int, r: int) -> list[float]:
    """p_{m,N,r}(k) for k = 1..N+1 (index 0 unused)."""
    denom = _log_comb(N + m + 1, m + 1)
    out = [0.0]
    for k in range(1, N + 2):
        lv = _log_comb(k + r - 2, r - 1) + _log_comb(N + m - k - r + 2, m - r + 1) - denom
        out.append(math.exp(lv) if lv > -INF else 0.0)
    return out


def rank_bounds(m: int, N: int, beta: float) -> tuple[list[int], list[int]]:
    """R_r^- and R_r^+ for r = 1..m+1 (eq. 6). Index 0 unused."""
    rm, rp = [0], [0]
    for r in range(1, m + 2):
        p = _pmf(m, N, r)
        F = [0.0] * (N + 2)
        for t in range(1, N + 2):
            F[t] = F[t - 1] + p[t]
        lo = max((t for t in range(1, N + 2) if F[t - 1] <= beta / 2), default=1)
        hi = min((t for t in range(1, N + 2) if F[t] >= 1 - beta / 2), default=N + 1)
        rm.append(lo)
        rp.append(hi)
    return rm, rp


def spi_threshold(real: Sequence[float], synth: Sequence[float], alpha: float, beta: float = 0.4) -> float:
    """SPI's bound Q (Algorithm 1, step 6)."""
    m, N = len(real), len(synth)
    S = sorted(real) + [INF]          # S_(1..m), S_(m+1) = +inf
    St = sorted(synth) + [INF]        # S~_(1..N), S~_(N+1) = +inf
    kq = math.ceil((N + 1) * (1 - alpha))
    q_prime = St[kq] if kq < len(St) else INF   # S~_(kq + 1), 1-indexed -> St[kq]
    rm, rp = rank_bounds(m, N, beta)
    r_minus = max((r for r in range(1, m + 2) if rm[r] <= kq), default=0)
    r_plus = max((r for r in range(1, m + 2) if rp[r] <= kq), default=0)
    s_minus = S[r_minus - 1] if r_minus >= 1 else -INF
    s_plus = S[r_plus - 1] if r_plus >= 1 else -INF
    return max(min(q_prime, s_minus), s_plus)


def prediction_set(probs: dict[str, float], q: float) -> list[str]:
    return [c for c, p in probs.items() if 1 - p <= q]
