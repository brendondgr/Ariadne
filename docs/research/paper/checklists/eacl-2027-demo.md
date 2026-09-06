# Checklist — EACL 2027 System Demonstrations

# 🛑 DROPPED — 2026-09-05, operator decision

**The demo track is not being pursued.** The target is a **full conference paper
or JMLR**. Kept for the record, not as a live to-do; nothing in it should be
worked on.

Why it was dropped: a demo track accepts a co-authored benchmark with no holdout
and rewards the artifact over the measurement. Since 2026-09-05 the project has
a **judged 288-question holdout under two grader families**, a **cross-family
re-grade of every judged claim**, and a **measured grader-calibration method** —
which is a measurement contribution the demo format cannot carry.

Live checklist: [`conference-full-paper.md`](conference-full-paper.md).

---

*Everything below is the original demo checklist, frozen.*

## Hard requirements — missing either is a desk reject

- [ ] **Screencast, ≤2.5 minutes.** Mandatory.
- [ ] **Live demo URL or installable package.** Mandatory.
- [ ] 6 pages + unlimited references
- [ ] Single-blind (author names **are** included)

## Evidence of validity — required

One of: user study, benchmark, case study, or usage statistics.

- [x] **Benchmark** — 120-question catalogue, seven arms, independently judged.
      [`../../INDEX.md`](../../INDEX.md)
- [ ] State plainly that the catalogue has **no holdout** and was co-authored
      with the templates. A demo track will accept this; concealing it is what
      damages credibility.

## Reproducibility fields — every one is already a manifest field

| Requirement | Where it lives | Ready? |
|---|---|---|
| Dataset description and access | [`../../datasets/DATASETS.md`](../../datasets/DATASETS.md) | ✅ |
| Hyperparameters and ranges searched | `manifest.yaml` → `llm`, per arm | 🟡 No search was performed; say so |
| Number of runs and seeds | `manifest.yaml` → `n_runs`, `seeds` | ⚠️ **n=1, seeds empty.** Must be stated |
| Metric definitions | Each `PROTOCOL.md` → Metrics | ✅ |
| Compute infrastructure | `manifest.yaml` → `compute`, `env/hardware.md` | 🟡 Partially unknown |
| Model identity and version | `manifest.yaml` → `llm.model` | 🟡 Gemma 4 31B; quantisation and context window unrecorded |

## Before submitting

- [ ] **LICENSE file added** — blocks any artifact link (see
      [`../venue-targets.md`](../venue-targets.md))
- [ ] MITRE attribution visible in the demo itself, not only in `NOTICE`
- [ ] Recompute the LLM-planning delta within one judge run; **do not write
      −0.196** (C-002 / C-018)
- [ ] Describe Arm G accurately as a *generic-primitives control*, **not** as a
      text-to-query baseline (D-004)
- [ ] Verify the CAPEC fixture is non-empty before recording the screencast
- [ ] Every number in the paper traces to an `EXP-` ID
