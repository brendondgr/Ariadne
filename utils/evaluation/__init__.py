"""Component-level evaluation for Ariadne (Wk 11-13).

Deterministic scoring of the planner and the two query specialists against
snapshot-derived gold. The model drafts, deterministic code grades: no metric
in this package depends on an LLM judge, so component scores are reproducible.

Submodules:
    stats             shared percentile / binomial-CI / bootstrap-CI math
    component_report  assemble planner + specialist scores into one report
    run_component_eval  CLI entry point orchestrating every scorer
"""

from utils.evaluation.stats import (
    bootstrap_ci,
    percentile,
    percentiles,
    proportion,
    wilson_interval,
)

__all__ = [
    "percentile",
    "percentiles",
    "proportion",
    "wilson_interval",
    "bootstrap_ci",
]
