# Robustness — parallel work plans (index)

Four self-contained briefs, written so separate agents could run them without
prior context. Each states its own scope, prohibitions and deliverables.

| Brief | Scope |
|---|---|
| [01-overnight-safe-work.md](01-overnight-safe-work.md) | Mechanical, unattended-safe tasks; created the `freeze/holdout-v1` tag |
| [02-holdout-question-generation.md](02-holdout-question-generation.md) | The blind holdout bank (normative), run against that tag |
| [04-holdout-execution-brief.md](04-holdout-execution-brief.md) | Operator brief fixing 02's open execution details |
| [05-holdout-execution-plan.md](05-holdout-execution-plan.md) | Implementation plan for executing 02 under 04's brief |

The parent plan these briefs cite (`branch-a-publication-readiness-plan.md`) was never written. `_overnight/` holds the artifacts Plan 01 produced (`derive_templates.py`, `numbers.json`, `questions.md`, `recompute.py`, `run-log.md`, `verification.md`); they are hash-pinned by eight experiment manifests under `docs/research/experiments/` and must not be moved or edited.
