# RESULTS — EXP-2026-07-004 Arm D — authored plan with an LLM writer reading verified claims

## 1. Headline

Correctness **0.9917** over 120 questions
(119 CORRECT / 0 PARTIAL / 1 INCORRECT),
with **1 hallucination(s)** across
1 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

Authored plan with the LLM writing over *verified claims* rather than raw evidence. The change that made an LLM writer nearly free.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9917 | 1 |
| `completeness` | 0.9958 | 1 |
| `faithfulness` | 0.9936 | 1 |
| `groundedness` | 0.9975 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 501.0 s |
| Evidence records | 1061 |
| Related neighbours | 839 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm D isolates the claims-narrator switch: the LLM writes prose over the verified claim set instead of re-reading raw evidence. Correctness 0.9917 with a single INCORRECT and one hallucination, against Arm C's 0.9690 with eight PARTIAL.

This is the change that made the accuracy-versus-readability trade disappear. Binding the narrator to verified claims removes its opportunity to re-interpret evidence, which is where Arm C's PARTIALs came from.

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

How much of the LLM writer's error was avoidable by changing what it reads rather than how it is prompted. Same model, same evidence upstream, eight PARTIALs to zero.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Determine whether the claims-narrator gain holds on a model other than Gemma 4 31B. One model, one day.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_llm --root docs/evaluation/experiments/untruncated-claimnarr --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-claimnarr
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-claimnarr/gold_llm/answers/`](../../../evaluation/experiments/untruncated-claimnarr/gold_llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENT A-1 (2026-09-09) — Provenance and figure attribution recorded

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` reproduces exactly from the pointed-at artifacts (0.991667 / 0.995833 / 0.993583 / 0.9975 / 1.0; 119/0/1; 1 hallucination in 1 answer; 1061 / 839; wall 501.0 s). No prose in this file has been overturned by a later experiment; the audit found no mismatch.

**What was wrong, and what is now correct.**

* **Arm code is shared with Arm C.** `data/metrics.json` records `arm_code: gold_llm`, the same runner as EXP-2026-07-003; the letter is determined by the root directory (`untruncated-claimnarr/` here, `untruncated-fixed/` for Arm C), as `docs/evaluation/experiments/README.md` documents. Stated here so the two `gold_llm` directories are never confused.
* **`code.commit`** (manifest.yaml:27): `unknown` → `37174425aa88656c5eea118591b8ae5aefc2f6aa`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-claimnarr/gold_llm`: a single commit, `3717442` (2026-07-26 19:34 −0400, *"Wire the retrieval loop to actually iterate, and measure it (Arm E)"*), adds all 240 files; the same commit carries Arm E's artifacts. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-claimnarr/gold_llm` → `sha256:4d853cbf…` (3437772 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("D", "EXP-2026-07-004", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for the July seven-arm study, Arms B–G. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
