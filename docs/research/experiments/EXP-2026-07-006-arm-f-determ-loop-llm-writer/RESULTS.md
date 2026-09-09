# RESULTS — EXP-2026-07-006 Arm F — authored plan, facet-chasing loop, LLM writer over verified claims

## 1. Headline

Correctness **0.9957** over 120 questions
(119 CORRECT / 1 PARTIAL / 0 INCORRECT),
with **3 hallucination(s)** across
3 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The recommended demo configuration: deterministic ceiling accuracy with readable analyst prose, and the *least* evidence retrieved of any LLM arm.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.9957 | 1 |
| `completeness` | 0.9990 | 1 |
| `faithfulness` | 0.9960 | 1 |
| `groundedness` | 0.9992 | 1 |
| `answer_coverage` | 1.0000 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 533.4 s |
| Evidence records | 1080 |
| Related neighbours | 866 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm F is the recommended demo configuration and the study's most useful result. It scores 0.9957 against the deterministic ceiling's 0.9972 — a 0.0015 gap — with zero INCORRECT, full gold coverage, and readable prose instead of a claim table.

It also retrieves the least evidence of any LLM arm (1,080 records) while scoring the highest. The accuracy-versus-readability trade is not real, once the narrator is bound to verified claims.

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

That the best LLM arm retrieves the *least* evidence of any LLM arm and still achieves full gold coverage. Everything in this study pointed the same way: precision in planning beats volume in retrieval, every time.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Narrator count discipline: the single remaining PARTIAL (F-CTM-01) recomputed a count and said 'five techniques' where the evidence held six.
* Decide the loop explicitly before any demo. The live `.env` pins `ORCH_MAX_HOPS=1` and leaves `ORCH_CHASE_FACETS` unset, so the app as configured does **not** do what this arm measures.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm gold_loop_llm --root docs/evaluation/experiments/untruncated-goldloop --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-goldloop
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-goldloop/gold_loop_llm/answers/`](../../../evaluation/experiments/untruncated-goldloop/gold_loop_llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENT A-1 (2026-09-09) — Blind holdout has reported; the 0.0015 gap is 0.0016; planner flag explained; provenance recorded

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` reproduces exactly from the pointed-at artifacts (0.995667 / 0.999 / 0.996 / 0.999167 / 1.0; 119/1/0; 3 hallucinations in 3 answers; 1080 / 866; wall 533.4 s), and F-CTM-01 is confirmed as the single PARTIAL verdict. Nothing in the results table changes.

**What was wrong, and what is now correct.**

* **Stale prose — "the recommended demo configuration" (§1, RESULTS.md:11; §4, RESULTS.md:47) predates the blind holdout.** **EXP-2026-08-002** (2026-08-09) ran this arm on 30 blind questions: `arm_f_blind_correctness` **0.7083** against `arm_f_dev_correctness` 0.9957 (`arm_f_blind_minus_dev` −0.2874). **EXP-2026-08-007** (the judged generation-2 comparison, calibrated grader) then measured Arm F at **0.9157** blind (25/5/0) and 0.9852 on the catalogue against the repaired cascade's 0.8367 / 0.9839, and its RESULTS states that Arm F's catalogue lead is inside the interval, that the comparison is not cost-fair, and that Arm F's blind advantage is a coverage effect. The current quotable pair for *this* experiment is **0.9957 (dev) / 0.7083 (blind, EXP-2026-08-002)**; the 0.9157 belongs to EXP-2026-08-007's re-run, not to these artifacts. Whether Arm F is "recommended" is a decision recorded in `DECISIONS.md`, not a finding of this folder. Body text left as written; `related` gains `EXP-2026-08-002` and `EXP-2026-08-007`.
* **"a 0.0015 gap" (§4, RESULTS.md:47) is the difference of two rounded values.** From the 6-decimal values in both manifests, 0.997250 − 0.995667 = **0.001583 → 0.0016**; 0.0015 is 0.9972 − 0.9957. Quote **0.0016**. `CLAIMS.md` C-005 and C-020 repeat 0.0015; that file is outside this folder and is flagged for its owner.
* **`data/metrics.json` `llm_posture.planner: "true"` is the env flag, not what ran.** The harness overlay sets `PLANNER_LLM_ENABLED=true` for this arm, but the `gold_loop_llm` runner (`utils/evaluation/experiment_untruncated.py:580–622`) builds `PlanningAgent(llm_enabled=False)` wrapped in `_GoldPlanAgent` (lines 557–578), whose `plan()` returns the catalogue's authored plan; every one of the 120 answer files carries `run_meta.planner == "gold-plan (injected)"` (counted 2026-09-09). The prose ("authored plan") is right; the flag is misleading. A `llm_posture_note` field stating this was added to `data/metrics.json` on 2026-09-09; no number in that file changed.
* **`code.commit`** (manifest.yaml:27): `unknown` → `9e34b878eab44d5489bae989e7d1acefad2312ce`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-goldloop/gold_loop_llm`: a single commit, `9e34b87` (2026-07-26 21:20 −0400, *"Arm F: deterministic extractor + LLM agent-loop synthesizer — 119/120, 0 INCORRECT"*), adds all 240 files. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-goldloop/gold_loop_llm` → `sha256:1ae34664…` (3618202 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("F", "EXP-2026-07-006", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for the July seven-arm study, Arms B–G. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
