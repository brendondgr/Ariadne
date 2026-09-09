# RESULTS — EXP-2026-07-003 Arm C — authored plan with an LLM writer reading raw evidence

## 1. Headline

Correctness **0.9690** over 120 questions
(110 CORRECT / 8 PARTIAL / 2 INCORRECT),
with **3 hallucination(s)** across
3 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The reference against which LLM planning is measured: authored plan, LLM writer reading raw evidence. Isolates the un-truncation change from the committed baseline.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9690 | 1 |
| `completeness` | 0.9672 | 1 |
| `faithfulness` | 0.9921 | 1 |
| `groundedness` | 0.9983 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 583.8 s |
| Evidence records | 1840 |
| Related neighbours | 839 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm C is the reference arm. Against the committed (truncated) baseline with an otherwise identical configuration, lifting the caps was positive on all four judged metrics — un-truncating retrieval was never the regression.

It is also the arm the notorious -0.196 figure was computed against, in an *earlier* judge run where it scored 0.9620. Post-fix it scores 0.9690, and B - C is **-0.1185**. Quote that, within this run. See `../../CLAIMS.md`.

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

That lifting the truncation caps was not free. Raising limits broke two things that other logic keyed off — the bounded-scan gold and the enumeration claim — which is a general lesson about caps as implicit contracts, not a quirk of this run.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Recompute the LLM-planning delta within a single judge run before it reaches a reviewer. Two figures (-0.196 and -0.1185) exist from different runs and only the second is reproducible from the standing table.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_llm --root docs/evaluation/experiments/untruncated-fixed --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-fixed
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-fixed/gold_llm/answers/`](../../../evaluation/experiments/untruncated-fixed/gold_llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENT A-1 (2026-09-09) — Provenance and figure attribution recorded

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` reproduces exactly from the pointed-at artifacts (0.969 / 0.967208 / 0.992083 / 0.998333 / 1.0; 110/8/2; 3 hallucinations in 3 answers; 1840 / 839; wall 583.8 s). No prose in this file has been overturned by a later experiment; the audit found no mismatch.

**What was wrong, and what is now correct.**

* **§4's baseline is named.** *"Against the committed (truncated) baseline … lifting the caps was positive on all four judged metrics"* checks against **EXP-2026-07-010** (0.8946 / 0.8952 / 0.9558 / 0.9575), the pre-fix committed baseline: this arm scores 0.9690 / 0.9672 / 0.9921 / 0.9983. `related` gains `EXP-2026-07-010` so the comparison is navigable; the supersession link itself belongs to EXP-2026-07-001, which carries it.
* **`code.commit`** (manifest.yaml:27): `unknown` → `9e6ac3457360c319b38e4dffa7bcbf29d878bafc`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-fixed/gold_llm`: 75 answer files were added in `33e38ac` (2026-07-26 14:31 −0400); the other 45 answers, all 120 judgment files and the arm `manifest.json` in `9e6ac34` (14:57 −0400), after which nothing under the directory changed. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-fixed/gold_llm` → `sha256:bac54b85…` (4065199 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("C", "EXP-2026-07-003", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for the July seven-arm study, Arms B–G. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
