# RESULTS — EXP-2026-07-007 Arm G — generic primitives only, every hand-written template disabled

## 1. Headline

Correctness **0.6388** over 120 questions
(64 CORRECT / 14 PARTIAL / 42 INCORRECT),
with **7 hallucination(s)** across
7 answer(s). No hypothesis was registered, so nothing
survived or failed — this arm is one measured cell of the comparison.

The generic-primitives control. Disabling the hand-written templates costs **-0.3568** correctness — three times what LLM planning costs.

## 2. Results table

Generated from [`data/metrics.json`](data/metrics.json), which is itself derived
from the committed judgment files via
[`docs/plans/robustness/_overnight/numbers.json`](../../../plans/robustness/_overnight/numbers.json).

| Metric | Value | n |
|---|---|---|
| `correctness` **(primary)** | 0.6388 | 1 |
| `completeness` | 0.6802 | 1 |
| `faithfulness` | 0.9658 | 1 |
| `groundedness` | 0.9788 | 1 |
| `answer_coverage` | 0.8979 | 1 |

**`n = 1`, and `std` is null throughout.** This arm was run **once**. The numbers
are single-run point estimates, not means over seeds, and no variance is
recoverable from them. Anywhere this figure appears in a paper it must be
reported as such. See §5.

| Cost / volume | Value |
|---|---|
| Wall clock (120 questions) | 914.8 s |
| Evidence records | 252 |
| Related neighbours | 1749 |

## 3. Figures

No figure is generated in this folder. The study's cross-arm comparison figure
is promoted at [`../../figures/`](../../figures/) and generated from every arm's
`metrics.json` at once — a per-arm chart of a single arm would not say anything
the table above does not.

## 4. Interpretation

Arm G is the load-bearing result for the paper's positioning. Disabling every hand-written intent template and leaving only schema-driven primitives costs **-0.3568** correctness (G - F), three times the -0.1185 that LLM planning costs. The templates, not the planner, are where this system's accuracy lives.

**What Arm G is not:** it is not free-form LLM query generation. No LLM writes Cypher or Gremlin in any arm of this study. That experiment has never been run, and the literature contains no controlled head-to-head of a template library against free-form generation — which is precisely the gap this repository is positioned to fill. See `../../OPEN_QUESTIONS.md`.

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

The magnitude. Losing the templates costs three times what swapping in an LLM planner costs, which inverts the framing the repository had been carrying — the interesting engineering was assumed to be in the planner.

## 7. Follow-ups

Tracked in [`../../OPEN_QUESTIONS.md`](../../OPEN_QUESTIONS.md):

* Build the free-form text-to-Cypher/Gremlin baseline. Arm G is a generic-primitives control, not the LLM-writes-queries comparison the paper's positioning actually needs.
* Build the merged-single-graph baseline to test the federation claim against a counterfactual.

## 8. Reproduction

```bash
uv run main.py --dataset attack --graph neo4j
uv run main.py --dataset capec --graph gremlin
uv run python -m utils.evaluation.experiment_untruncated \
  --arm generic --root docs/evaluation/experiments/untruncated-generic --workers 4
uv run python -m utils.evaluation.summarize_untruncated --root docs/evaluation/experiments/untruncated-generic
```

Judging is a separate step and is **not** reproducible by a single command: it
runs 120 independent Sonnet 5 agents via the Workflow tool. The judgments this
arm's numbers derive from are committed under
[`docs/evaluation/experiments/untruncated-generic/generic/answers/`](../../../evaluation/experiments/untruncated-generic/generic/answers/),
hashed in [`data/POINTERS.md`](data/POINTERS.md).

---

## AMENDMENT A-1 (2026-09-09) — Arm G ran with the injected gold plan; its run date is unrecorded; C-003 is refuted and the arm is superseded by Arm H

Written during the 2026-09-09 record audit (batch b1). Every number in §1–§2 and in `data/metrics.json` reproduces exactly from the pointed-at artifacts (0.638833 / 0.680222 / 0.965833 / 0.97875 / 0.897859; 64/14/42; 7 hallucinations in 7 answers; 252 / 1749; wall 914.8 s), and G − F = 0.638833 − 0.995667 = −0.356834 → **−0.3568** recomputes. The measurement stands. What it measures, when it was measured, and what it supports were all recorded wrongly.

**1. The arm description is wrong: Arm G did not use the LLM planner.**

*Where:* manifest.yaml:16 (`purpose`, *"Plan: LLM planner"*), PROTOCOL.md:12 (*"plan: **LLM planner**"*), `docs/evaluation/experiments/README.md:27` (arm table, Plan column *"LLM planner"*) and `docs/evaluation/2026-07-26/README.md:37` (Plan column *"**LLM**"*). *What ran:* `utils/evaluation/experiment_untruncated.py:717` maps `"generic"` to `run_gold_loop_llm` (*"same driver; templates disabled via env"*). That driver (lines 580–622) builds `PlanningAgent(… llm_enabled=False)` wrapped in `_GoldPlanAgent` (lines 557–578), whose `plan()` returns the catalogue's authored plan, and stamps `"planner": "gold-plan (injected)"`. All **120 of 120** Arm G answer files carry `run_meta.planner == "gold-plan (injected)"` (counted 2026-09-09) — identical to Arm F; Arms B and E carry `"llm"`. So Arm G is **authored plan + generic primitives + facet-chasing loop + LLM writer over verified claims**. *Consequences:* (a) G − F holds the plan, the loop and the writer fixed and moves only the templates — a **cleaner single-variable contrast** than the record claims; the −0.3568 stands, its description changes. (b) `data/metrics.json` `llm_posture.planner: "true"` is the env flag (`PLANNER_LLM_ENABLED=true`) the harness overrides; a `llm_posture_note` field was added on 2026-09-09, no number changed. (c) The manifest `purpose` was corrected in place: *"Plan: LLM planner"* → *"Plan: authored gold replay (corrected 2026-09-09 …)"*. PROTOCOL.md:12 and the two README tables are left as written (append-only prose; the READMEs are outside this folder and are flagged for their owner).

**2. The run date is unrecorded; 2026-07-26 is unsupported.**

manifest.yaml:9–10 (`date_started` / `date_completed: 2026-07-26`) and INDEX.md:19 repeat the study date, but: the artifacts and the `generic` arm code first entered git in **`a509f63` on 2026-08-04 23:50 −0400** (*"Overnight (1/12): Commit the Arm G generic-only control code path and its 120-case artifacts"*); `docs/plans/robustness/01-overnight-safe-work.md` Task 1 lists `untruncated-generic/` as 241 **untracked** files; `docs/plans/robustness/_overnight/run-log.md` logs Task 1 at 2026-08-04T23:52; the Arm G rows in the README tables were added by `feb9298` (2026-08-04 23:57); and ISSUES 2026-07-26 itself says *"Arm G is a later run"*. No answer file, judgment file or the arm `manifest.json` carries a timestamp. What can be established: the run happened **after `9e34b87`** (2026-07-26 21:20, Arm F, which introduced the shared `run_gold_loop_llm` driver) **and before 2026-08-04 23:50**. Per the record contract the manifest dates are left as recorded (they cannot be replaced by an established value); a 2026-09-09 ISSUES entry records the bounds.

**3. The conclusion is refuted; the arm is superseded.**

§1 (RESULTS.md:11) and §4 (RESULTS.md:47, *"the load-bearing result for the paper's positioning … The templates, not the planner, are where this system's accuracy lives"*) are stale. `CLAIMS.md:190` marks **C-003 `refuted`, "REFUTED AND SUPERSEDED BY C-023 (2026-08-23)"**: *"The 3.0x ratio was measured against Arm G, a weaker generic arm that predates the schema-derived capabilities, and is not reproducible against Arm H."* The measurements that overturned it: **EXP-2026-08-001** (Arm H, 2026-08-09; lists this experiment under `baselines_compared`) rebuilt the generic path with three schema-derived capabilities and reached `gold_in_evidence` 1.0 where this arm's `answer_coverage` was 0.8979; **EXP-2026-08-007** judged Arm H at **0.8483** blind against the cascade's 0.8367 and states that *"the 3.0× ratio in the original claim came from Arm G, an earlier and weaker generic arm"*; EXP-2026-08-008 (fresh bank 0.9700 vs 0.9467), EXP-2026-08-010 (external recall 0.9953 vs 0.7170) and EXP-2026-08-011 are quoted in C-003/C-023 to the same effect. **The current figure** is C-023's: a schema-derived generic path matches the templates on correctness; what templates hold is precision on the schemas they were written for and provable abstention. **−0.3568 remains a valid measurement of *this* generic arm and is not quotable as the cost of removing templates.** Manifest changes: `status: complete` → **`superseded`**; `superseded_by: null` → **`EXP-2026-08-001`** (EXP-2026-08-001's matching `supersedes` is set by its owner); `related` gains `EXP-2026-08-001` and `EXP-2026-08-007`. `supports_claims: [C-003]` is left as recorded — the claim exists and is marked refuted there.

**4. Provenance, pointers, figure, model.**

* **`code.commit`** (manifest.yaml:29, line 27 before the `purpose` correction above): `unknown` → `a509f63d92edf273cc0305a553a67143c29540f5`. Established with `git log --diff-filter=A -- docs/evaluation/experiments/untruncated-generic/generic`: a single commit, `a509f63` (2026-08-04 23:50 −0400), adds all 240 files together with the arm's code path; nothing under the directory changed afterwards. This is the commit that put the artifacts on record — an **upper bound** on the code that produced them, not the run commit, which was never captured (ISSUES 2026-08-06 still applies; a 2026-09-09 ISSUES entry says so).
* **Pointers re-verified.** Both rows of `data/POINTERS.md` were re-hashed on 2026-09-09 with `uv run python -m utils.research_record.hashing`: `docs/evaluation/experiments/untruncated-generic/generic` → `sha256:de75c852…` (4878680 bytes, tree), unchanged; `docs/plans/robustness/_overnight/numbers.json` → `sha256:12a748f0…` (21403 bytes), unchanged. The directory still holds exactly 240 files (120 answers + 120 judgments); no `*.judgment*` sidecar has been added since the number was recorded, so no re-hash was needed.
* **Figure attribution.** `figures: []` is left as recorded: no figure lives in this folder. The promoted cross-arm figure `fig-arm-comparison` (`docs/research/figures/fig-arm-comparison.{svg,pdf}`) is generated by `docs/research/figures/sources/make_arm_comparison.py`, which reads this experiment's `data/metrics.json` (its arm row `("G", "EXP-2026-07-007", …)`, no number hardcoded), and `CLAIMS.md` attributes that figure to this experiment. Regenerate it from the figure source, not from this folder.
* **Model.** Manifest `llm.model: vllm/gemma-4-31b@unknown` is left as recorded: `docs/evaluation/README.md` §"The model behind `skynet`" gives **Gemma 4 31B** (dense, quantisation never recorded; operator statement of 2026-08-04) as the model behind the relay for "Arms B–G" — a statement that covers this arm by name even though its run date is only bounded (§2 above). If the run fell in the August window the README calls undetermined, the model is unknown; nothing in the artifacts distinguishes the two cases. `data/metrics.json` `llm_posture.model: "skynet"` is the relay alias copied from the run's env flags, not a model name; read it through the README table.
