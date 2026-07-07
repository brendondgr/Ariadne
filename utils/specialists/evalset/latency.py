#!/usr/bin/env python3
"""Latency — percentile distribution, never the mean.

Latency is right-skewed, so the mean hides the tail; this reports p50/p95/p99
with bootstrap confidence intervals, the SRE/benchmarking standard. It is
**live** (executes against Neo4j/Gremlin) and follows the discipline the
proposal's method calls for:

* **n >= 200** paired runs per specialist (the catalogue repeated), so the
  percentiles are not millisecond noise.
* **warm-up discarded** — the first repetition of each question is the cold
  sample; steady-state percentiles come from the warm repetitions, and cold vs
  warm is reported separately.
* **segmented** — by specialist, by difficulty tier.
* **staged** — the per-run wall-clock is broken into draft+gate / execute /
  assess / normalize from the trace timings, so a slow tail is attributable to a
  stage, not blamed on "the specialist".
* the **p50/p99 gap** is reported as the tail signal.

Absolute numbers are environment-specific and are an artifact, not a regression
gate — the tests assert shape and ordering, not milliseconds.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass
from typing import Any

from utils.evaluation.stats import bootstrap_ci, percentile
from utils.specialists.contracts import SpecialistTask
from utils.specialists.evalset.compile_banks import (
    ATTACK_BANK_PATH,
    CAPEC_BANK_PATH,
    load_bank,
)
from utils.specialists.evalset.score_validity import build_specialists

BANK_PATHS = {"attack": ATTACK_BANK_PATH, "capec": CAPEC_BANK_PATH}
MIN_SAMPLES = 200
STAGES = ("gate_ms", "execute_ms", "assess_ms", "normalize_ms")


@dataclass
class Sample:
    id: str
    tier: str
    rep: int
    cold: bool
    total_ms: float
    gate_ms: float
    execute_ms: float
    assess_ms: float
    normalize_ms: float


def _stage_ms(traces: list[Any], step: str) -> float:
    return round(sum(float(t.detail.get("timing_ms", 0.0)) for t in traces if t.step == step), 3)


def measure(specialist: Any, questions: list[dict], reps: int, clock) -> list[Sample]:
    samples: list[Sample] = []
    for rep in range(reps):
        for q in questions:
            task = SpecialistTask.from_dict(q["task"])
            t0 = clock()
            result = specialist.run(task)
            wall = round((clock() - t0) * 1000, 3)
            samples.append(Sample(
                id=q["id"], tier=str(q.get("tier", "?")), rep=rep, cold=(rep == 0),
                total_ms=wall,
                gate_ms=_stage_ms(result.traces, "gate"),
                execute_ms=_stage_ms(result.traces, "execute"),
                assess_ms=_stage_ms(result.traces, "assess"),
                normalize_ms=_stage_ms(result.traces, "normalize"),
            ))
    return samples


def _pcts(values: list[float]) -> dict[str, Any]:
    """p50/p95/p99 point estimates with bootstrap CIs on p50 and p99."""
    if not values:
        return {"n": 0}
    p50 = percentile(values, 50)
    p95 = percentile(values, 95)
    p99 = percentile(values, 99)
    _, p50_lo, p50_hi = bootstrap_ci(values, lambda v: percentile(v, 50))
    _, p99_lo, p99_hi = bootstrap_ci(values, lambda v: percentile(v, 99))
    return {
        "n": len(values),
        "p50": round(p50, 3), "p50_ci": [round(p50_lo, 3), round(p50_hi, 3)],
        "p95": round(p95, 3),
        "p99": round(p99, 3), "p99_ci": [round(p99_lo, 3), round(p99_hi, 3)],
        "p50_p99_gap": round(p99 - p50, 3),
    }


def summarize(samples: list[Sample]) -> dict[str, Any]:
    """Shape the raw samples into the segmented, staged latency report."""
    warm = [s for s in samples if not s.cold]
    cold = [s for s in samples if s.cold]
    warm = warm or samples  # if only one rep, treat all as steady-state
    tiers = sorted({s.tier for s in warm})
    return {
        "samples": len(samples),
        "warm_samples": len(warm),
        "total_ms": _pcts([s.total_ms for s in warm]),
        "by_tier": {t: _pcts([s.total_ms for s in warm if s.tier == t]) for t in tiers},
        "by_stage": {stage: _pcts([getattr(s, stage) for s in warm]) for stage in STAGES},
        "cold_vs_warm": {
            "cold_p50": round(percentile([s.total_ms for s in cold], 50), 3) if cold else None,
            "warm_p50": round(percentile([s.total_ms for s in warm], 50), 3),
        },
    }


def run_latency(reps_per_specialist: dict[str, int] | None = None, clock=None) -> dict[str, Any]:
    """Full live latency report across both specialists (>= 200 samples each)."""
    clock = clock or _perf_clock
    specialists = build_specialists()
    out: dict[str, Any] = {}
    for source, specialist in specialists.items():
        questions = load_bank(BANK_PATHS[source])["questions"]
        if reps_per_specialist and source in reps_per_specialist:
            reps = reps_per_specialist[source]
        else:
            reps = math.ceil(MIN_SAMPLES / len(questions)) + 1  # +1 warm-up rep
        samples = measure(specialist, questions, reps, clock)
        out[source] = summarize(samples)
    return out


def _perf_clock() -> float:  # pragma: no cover - wall clock, not unit-tested
    import time
    return time.perf_counter()


def main() -> int:  # pragma: no cover - thin CLI wrapper
    print(json.dumps(run_latency(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
