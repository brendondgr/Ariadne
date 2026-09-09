# RESULTS — EXP-2026-07-002 Arm B — LLM planning with deterministic extraction and an LLM writer

## 1. Headline

Correctness **0.8505** over 120 questions
(92 CORRECT / 14 PARTIAL / 14 INCORRECT),
with **12 hallucination(s)** across
8 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The LLM-planned arm, and the study's central regression. Identical extraction and synthesis to Arm C — only the planner changes — for **-0.1185** correctness.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.8505 | 1 |
| `completeness` | 0.8692 | 1 |
| `faithfulness` | 0.9683 | 1 |
| `groundedness` | 0.9750 | 1 |
| `answer_coverage` | 0.8074 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 1019.7 s |
| Evidence records | 2814 |
| Related neighbours | 621 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm B minus Arm C is the study's cleanest contrast — same extraction, same synthesis, only the planner differs — and it is **-0.1185** correctness. Failure localisation shows *where*: only 2 of Arm B's 36 failures were faithfulness, and 26 of 36 were planning or retrieval. LLM answers here do not fail by making things up; they fail by asking the wrong question.

Arm B also retrieves 2,814 records to Arm F's 1,080 and surfaces 20% less of the gold. Precision in planning beat volume in retrieval throughout.

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

That the failures were not hallucinations. The intuition going in was that an LLM-planned arm fails by inventing facts; failure localisation showed 26 of 36 failures were planning or retrieval and only 2 were faithfulness.

The single largest cause was mechanical rather than cognitive: the planner emitted the plan-level join correctly but left each sub-question's own `join_key` null, and the router keys on the sub-question's field. Two representations of the same fact disagreed, and 19 of 36 failures followed.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Route on the sub-question's declared `entities` rather than surface phrasing, so single-source questions stop downgrading to `describe`.
* Raise or parallelise the stage deadline — 6 of 120 LLM-arm questions finish `partial` on the timeout.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm llm --root docs/evaluation/experiments/untruncated-fixed --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-fixed
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-fixed/llm/answers/`](../../../evaluation/experiments/untruncated-fixed/llm/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENTS

### A-1 (2026-08-31) — the 26-of-36 failure figure does not reproduce

This file states *"only 2 of Arm B's 36 failures were faithfulness, and 26 of 36
were planning or retrieval."* Re-running `utils/evaluation/failure_terminus.py`
over the same committed artifact directory
(`docs/evaluation/experiments/untruncated-fixed/llm`) gives **28** non-CORRECT of
120, not 36 — which is what this experiment's own `metrics.json` verdict counts
say (92 CORRECT + 14 PARTIAL + 14 INCORRECT) — distributed as:

| terminus | n |
|---|---|
| `incomplete_retrieval` | 11 |
| `projection_gap` | 7 |
| `unfaithful` | **4** |
| `pipeline_timeout` | 4 |
| `gold_cap_collision` | 2 |

**Quote 4 of 28, not 2 of 36.** The 36 is most likely an earlier judge run, the
same species as the figure cut in `C-018`. Nothing else in this experiment
changes: correctness 0.8505, the B−C delta of −0.1185, and the record counts are
all recomputed from the artifacts and stand.

**The correction strengthens rather than weakens the finding**, because the
reason the original framing was wrong is more interesting than the arithmetic —
see [`../../paper/sections/09-failure-localisation.md`](../../paper/sections/09-failure-localisation.md).
Comparing our `unfaithful` class against Leung et al.'s `Generation` stage
compares our narrowest category against their broadest. Mapped like-for-like,
Arm B's generation-stage share is **42.3%**, between their two reported settings
rather than opposed to them, and what survives is a distinction their taxonomy
cannot draw: within generation, **under-statement outnumbers fabrication 7 to 4**.

---

## AMENDMENT A-2 (2026-09-09) — Timeout count and the 19-of-36 figure do not reproduce; provenance recorded

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` reproduces exactly from the pointed-at artifacts (0.8505 / 0.86925 / 0.968333 / 0.975 / 0.807395; 92/14/14; 12 hallucinations in 8 answers; 2814 / 621; wall 1019.7 s), and re-running `uv run python -m utils.evaluation.failure_terminus --root docs/evaluation/experiments/untruncated-fixed --arms llm` on 2026-09-09 reproduces A-1's table exactly (28 non-CORRECT: incomplete_retrieval 11, projection_gap 7, unfaithful 4, pipeline_timeout 4, gold_cap_collision 2). A-1 stands.

**What was wrong, and what is now correct.**

* **"6 of 120 LLM-arm questions finish `partial` on the timeout"** (RESULTS.md:85; ISSUES.md:52) is not reproducible. Counting `run_meta.status` over the 120 answer files: **10** carry `"partial"` (all with `exit_code: 1`) — A-AST-01 (wall 120.1 s), A-AST-02 (72.3), A-NEG-02 (120.1), F-CTM-08 (120.8), F-CTT-05 (120.1), F-CTT-06 (120.1), F-PART-01 (116.0), F-PART-02 (59.9), F-PART-03 (136.3), F-PART-04 (40.2). Five of them sit at the ~120 s stage deadline; `failure_terminus` classes **4** as `pipeline_timeout` (F-CTM-08, F-CTT-05, F-CTT-06, F-PART-02), the others being caught by an earlier terminus. No definition yields 6. Quote **10 partial-status answers, of which 4 terminate as pipeline timeouts**; the qualitative point in §7 and in ISSUES (part of the deficit is a latency artifact) survives.
* **"19 of 36 failures followed"** (RESULTS.md:78) uses the 36 denominator that A-1 already corrected to 28, and the 19 is not covered by A-1. There is no `join_key`-null classifier in `failure_terminus.py`, and no per-case artifact field records that cause, so the 19 cannot be recomputed from the record. **Do not quote it.** The mechanism it describes (plan-level join set, sub-question `join_key` null) is documented in the 2026-07-26 commit messages (`9e6ac34`, *"a declared join never reached its sub-questions"*) and stands as a qualitative finding.
* **Body text still carries the superseded figures.** §4 (RESULTS.md:47) and §6 (RESULTS.md:76) still read *"only 2 of Arm B's 36 failures were faithfulness, and 26 of 36 were planning or retrieval"*. A-1 governs: **4 of 28** unfaithful; planning-or-retrieval = incomplete_retrieval 11 + projection_gap 7 = **18 of 28** (18 of 26 once the two `gold_cap_collision` cases are excluded, as `paper/sections/09-failure-localisation.md` does). The body is left as written per the append-only rule. `CLAIMS.md` C-016 (line 189) still opens with "26 of Arm B's 36 failures"; that file is outside this folder and is flagged for its owner.
* **`code.commit`** (manifest.yaml:27): `unknown` → `07e4de454f1bd6dfd778e567fc4f9f6a8caf2ae0`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-fixed/llm`: the 120 answer files, the arm `manifest.json` and 24 judgment files were added in `9e6ac34` (2026-07-26 14:57 −0400); the remaining 96 judgment files in `07e4de4` (15:03 −0400), after which nothing under the directory changed. `07e4de4` is recorded because it is the first commit at which the whole artifact set exists. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-fixed/llm` → `sha256:f098c959…` (4170434 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("B", "EXP-2026-07-002", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for the July seven-arm study, Arms B–G. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
