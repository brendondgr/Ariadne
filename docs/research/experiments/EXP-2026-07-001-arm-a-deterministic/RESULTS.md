# RESULTS — EXP-2026-07-001 Arm A — fully deterministic pipeline (planning, extraction, synthesis)

## 1. Headline

Correctness **0.9972** over 120 questions
(120 CORRECT / 0 PARTIAL / 0 INCORRECT),
with **0 hallucination(s)** across
0 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

This is the study's ceiling and its reproducible fallback: no model in planning, extraction, or synthesis, 120/120 CORRECT, zero hallucinations, and the whole catalogue in **1.6 seconds**.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9972 | 1 |
| `completeness` | 1.0000 | 1 |
| `faithfulness` | 0.9993 | 1 |
| `groundedness` | 1.0000 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 1.6 s |
| Evidence records | 1061 |
| Related neighbours | 839 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm A is the evidence that the deterministic path is not a fallback but the ceiling. Its 1.6 s wall clock against Arm B's 1,020 s is a 637x ratio, and it is byte-reproducible, which makes it the correct CI regression gate and the correct thing to run on stage.

The caution that belongs beside it: 120/120 on a catalogue co-authored with the templates that answer it is exactly the shape a coverage artifact would take. This number does not become a paper claim until the blind holdout reports.

## 5. Threats to validity

Shared across every arm of this study:

* **All 120 questions are anchored.** Every one names an entity or an id.
  Nothing here measures open-ended analyst questions, which is exactly where a
  template router is weakest.
* **The catalogue was co-authored with the system.** Each question ships an
  `expected_template`, and the questions were written commit-for-commit with the
  templates that answer them. There is **no holdout**. This is the single
  largest threat to the headline number and it is unresolved.
* **The gold set is small and fixed.** 120 questions, categories of 1–10
  members, so one case moves a category mean substantially.
* **No baseline exists.** Not one alternative system was implemented, so no arm
  here has ever been contrasted with a counterfactual.
* **The judge is a model.** Cross-model and evidence-grounded, but still an LLM,
  and its verdicts are not perfectly stable across runs. It occasionally
  penalised correct answers over citation metadata.
* **One run, one model, one day.** `n_runs: 1`, seeds unrecorded, and everything
  ran against one served model (`skynet` = Gemma 4 31B) whose quantisation and
  context window are unrecorded. Nothing generalises to other models without
  re-running.

## 6. What surprised us

That the fully deterministic path won outright. The system is documented and framed as agentic; the arm with no model anywhere in it is the most accurate and roughly 600x the fastest.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Run this arm blind on 30 held-out questions authored by someone else. Until then 0.9972 cannot be distinguished from a coverage artifact.
* Re-run with recorded seeds so the figure carries a variance.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm deterministic --root docs/evaluation/experiments/untruncated-fixed --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-fixed
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-fixed/deterministic/answers/`](../../../evaluation/experiments/untruncated-fixed/deterministic/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENT A-1 (2026-09-09) — Blind holdout has reported; provenance, supersession and figure attribution recorded

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` was recomputed from the 120 `*.judgment.json` and 120 answer files under the pointed-at directory and **reproduces exactly** (0.99725 / 1.0 / 0.999333 / 1.0 / 1.0; 120/0/0; 0 hallucinations; 1061 records / 839 related; wall 1.6 s). Nothing in the results table changes.

**What was wrong, and what is now correct.**

* **Stale prose — the holdout is no longer pending.** §4 (RESULTS.md:49, *"This number does not become a paper claim until the blind holdout reports"*) and §7 (RESULTS.md:82, *"Run this arm blind on 30 held-out questions"*) present the blind holdout as future work. It has reported: **EXP-2026-08-002** (2026-08-09) ran this arm on 30 blind questions and recorded `arm_a_blind_correctness` **0.689** against `arm_a_dev_correctness` 0.9972 (`arm_a_blind_minus_dev` −0.3082), with the drop concentrated in reverse-direction asks. `CLAIMS.md` C-001 is therefore `partial` and reads *"Never quote 0.9972 without 0.689 beside it."* The later judged re-runs quoted in C-001 (0.8367 blind under a calibrated grader in EXP-2026-08-007; 0.9467 on a fresh bank in EXP-2026-08-008) measure the **repaired** deterministic cascade, not the code this folder points at, and must not be attributed to this experiment. The current quotable pair for this experiment is **0.9972 (dev) / 0.689 (blind, EXP-2026-08-002)**. The body text above is left as written.
* **Supersession** (manifest.yaml:69): `supersedes: null` → `EXP-2026-07-010`. EXP-2026-07-010 (the pre-fix committed baseline, 0.8946 correctness) already carried `superseded_by: EXP-2026-07-001`; the link was one-way and the validator flagged it (`[link-one-way]` in validate-report-0). Both sides are now recorded. `related` gains `EXP-2026-07-010`, `EXP-2026-08-002` (the blind holdout) and `EXP-2026-08-007` (the judged follow-up).
* **`code.commit`** (manifest.yaml:27): `unknown` → `33e38ac1a393fb6e5a15d9b96863e84e12f4334e`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-fixed/deterministic`: a single commit, `33e38ac` (2026-07-26 14:31 −0400, *"Root-cause the regression: 3 defects fixed, deterministic arm 120/120 CORRECT"*), adds all 240 files. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-fixed/deterministic` → `sha256:5dacadb4…` (3395113 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("A", "EXP-2026-07-001", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for the July seven-arm study, Arms B–G. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
* **The 118 + 2 splice cannot be confirmed from git.** ISSUES 2026-07-26 says the 120/120 verdict count combines 118 pre-scan-fix judgments with 2 re-judged cases. All 120 judgment files entered git in that one commit and none was modified afterwards, so the splice is not visible in history and cannot be independently verified. Recorded in ISSUES 2026-09-09; the paper implication there (state that the verdicts are not from a single judge pass) stands.
